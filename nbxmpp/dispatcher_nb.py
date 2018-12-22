##   dispatcher_nb.py
##       based on dispatcher.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.


"""
Main xmpp decision making logic. Provides library with methods to assign
different handlers to different XMPP stanzas and namespaces
"""

import sys
import locale
import re
import uuid
import logging
import inspect
from xml.parsers.expat import ExpatError

from nbxmpp.simplexml import NodeBuilder
from nbxmpp.plugin import PlugIn
from nbxmpp.protocol import NS_STREAMS
from nbxmpp.protocol import NS_HTTP_BIND
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import InvalidFrom
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Presence
from nbxmpp.protocol import Message
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import Node
from nbxmpp.protocol import Error
from nbxmpp.protocol import ERR_FEATURE_NOT_IMPLEMENTED
from nbxmpp.modules.eme import EME
from nbxmpp.modules.http_auth import HTTPAuth
from nbxmpp.modules.presence import BasePresence
from nbxmpp.modules.message import BaseMessage
from nbxmpp.modules.nickname import Nickname
from nbxmpp.modules.muc import MUC
from nbxmpp.misc import unwrap_carbon
from nbxmpp.util import get_properties_struct


log = logging.getLogger('nbxmpp.dispatcher_nb')

#: default timeout to wait for response for our id
DEFAULT_TIMEOUT_SECONDS = 25

XML_DECLARATION = '<?xml version=\'1.0\'?>'

# FIXME: ugly
class Dispatcher:
    """
    Why is this here - I needed to redefine Dispatcher for BOSH and easiest way
    was to inherit original Dispatcher (now renamed to XMPPDispatcher). Trouble
    is that reference used to access dispatcher instance is in Client attribute
    named by __class__.__name__ of the dispatcher instance .. long story short:

    I wrote following to avoid changing each client.Dispatcher.whatever() in xmpp

    If having two kinds of dispatcher will go well, I will rewrite the dispatcher
    references in other scripts
    """

    def PlugIn(self, client_obj, after_SASL=False, old_features=None):
        if client_obj.protocol_type == 'XMPP':
            XMPPDispatcher().PlugIn(client_obj)
        elif client_obj.protocol_type == 'BOSH':
            BOSHDispatcher().PlugIn(client_obj, after_SASL, old_features)
        else:
            assert False # should never be reached

    @classmethod
    def get_instance(cls, *args, **kwargs):
        """
        Factory Method for object creation

        Use this instead of directly initializing the class in order to make
        unit testing much easier.
        """
        return cls(*args, **kwargs)


class XMPPDispatcher(PlugIn):
    """
    Handles XMPP stream and is the first who takes control over a fresh stanza

    Is plugged into NonBlockingClient but can be replugged to restart handled
    stream headers (used by SASL f.e.).
    """

    def __init__(self):
        PlugIn.__init__(self)
        self.handlers = {}
        self._modules = {}
        self._expected = {}
        self._defaultHandler = None
        self._pendingExceptions = []
        self._eventHandler = None
        self._cycleHandlers = []
        self._exported_methods=[self.RegisterHandler, self.RegisterDefaultHandler,
                self.RegisterEventHandler, self.UnregisterCycleHandler,
                self.RegisterCycleHandler, self.RegisterHandlerOnce,
                self.UnregisterHandler, self.RegisterProtocol,
                self.SendAndWaitForResponse, self.SendAndCallForResponse,
                self.getAnID, self.Event, self.send]

        # \ufddo -> \ufdef range
        c = '\ufdd0'
        r = c
        while c < '\ufdef':
            c = chr(ord(c) + 1)
            r += '|' + c

        # \ufffe-\uffff, \u1fffe-\u1ffff, ..., \u10fffe-\u10ffff
        c = '\ufffe'
        r += '|' + c
        r += '|' + chr(ord(c) + 1)
        while c < '\U0010fffe':
            c = chr(ord(c) + 0x10000)
            r += '|' + c
            r += '|' + chr(ord(c) + 1)

        self.invalid_chars_re = re.compile(r)

    def getAnID(self):
        return str(uuid.uuid4())

    def dumpHandlers(self):
        """
        Return set of user-registered callbacks in it's internal format. Used
        within the library to carry user handlers set over Dispatcher replugins
        """
        return self.handlers

    def restoreHandlers(self, handlers):
        """
        Restore user-registered callbacks structure from dump previously obtained
        via dumpHandlers. Used within the library to carry user handlers set over
        Dispatcher replugins.
        """
        self.handlers = handlers

    def _register_modules(self):
        self._modules['BasePresence'] = BasePresence(self._owner)
        self._modules['BaseMessage'] = BaseMessage(self._owner)
        self._modules['EME'] = EME(self._owner)
        self._modules['HTTPAuth'] = HTTPAuth(self._owner)
        self._modules['Nickname'] = Nickname(self._owner)
        self._modules['MUC'] = MUC(self._owner)

        for instance in self._modules.values():
            for handler in instance.handlers:
                self.RegisterHandler(*handler)

    def _init(self):
        """
        Register default namespaces/protocols/handlers. Used internally
        """
        # FIXME: inject dependencies, do not rely that they are defined by our
        # owner
        self.RegisterNamespace('unknown')
        self.RegisterNamespace(NS_STREAMS)
        self.RegisterNamespace(self._owner.defaultNamespace)
        self.RegisterProtocol('iq', Iq)
        self.RegisterProtocol('presence', Presence)
        self.RegisterProtocol('message', Message)
        self.RegisterDefaultHandler(self.returnStanzaHandler)
        self.RegisterEventHandler(self._owner._caller._event_dispatcher)
        self._register_modules()
        self.on_responses = {}

    def plugin(self, owner):
        """
        Plug the Dispatcher instance into Client class instance and send initial
        stream header. Used internally
        """
        self._init()
        self._owner.lastErrNode = None
        self._owner.lastErr = None
        self._owner.lastErrCode = None
        if hasattr(self._owner, 'StreamInit'):
            self._owner.StreamInit()
        else:
            self.StreamInit()

    def plugout(self):
        """
        Prepare instance to be destructed
        """
        self._modules = {}
        self.Stream.dispatch = None
        self.Stream.features = None
        self.Stream.destroy()
        self._owner = None
        self.Stream = None

    def StreamInit(self):
        """
        Send an initial stream header
        """
        self._owner.Connection.sendqueue = []
        self.Stream = NodeBuilder()
        self.Stream.dispatch = self.dispatch
        self.Stream._dispatch_depth = 2
        self.Stream.stream_header_received = self._check_stream_start
        self.Stream.features = None
        self._metastream = Node('stream:stream')
        self._metastream.setNamespace(self._owner.Namespace)
        self._metastream.setAttr('version', '1.0')
        self._metastream.setAttr('xmlns:stream', NS_STREAMS)
        self._metastream.setAttr('to', self._owner.Server)
        if locale.getdefaultlocale()[0]:
            self._metastream.setAttr('xml:lang',
                    locale.getdefaultlocale()[0].split('_')[0])
        self._owner.send("%s%s>" % (XML_DECLARATION, str(self._metastream)[:-2]))

    def _check_stream_start(self, ns, tag, attrs):
        if ns != NS_STREAMS or tag!='stream':
            raise ValueError('Incorrect stream start: (%s,%s). Terminating.'
                    % (tag, ns))

    def replace_non_character(self, data):
        return re.sub(self.invalid_chars_re, '\ufffd', data)

    def ProcessNonBlocking(self, data):
        """
        Check incoming stream for data waiting

        :param data: data received from transports/IO sockets
        :return:
                1) length of processed data if some data were processed;
                2) '0' string if no data were processed but link is alive;
                3) 0 (zero) if underlying connection is closed.
        """
        # FIXME:
        # When an error occurs we disconnect the transport directly. Client's
        # disconnect method will never be called.
        # Is this intended?
        # also look at transports start_disconnect()
        data = self.replace_non_character(data)
        for handler in self._cycleHandlers:
            handler(self)
        if len(self._pendingExceptions) > 0:
            _pendingException = self._pendingExceptions.pop()
            sys.excepthook(*_pendingException)
            return
        try:
            self.Stream.Parse(data)
            # end stream:stream tag received
            if self.Stream and self.Stream.has_received_endtag():
                self._owner.disconnect(self.Stream.streamError)
                return 0
        except ExpatError as error:
            log.error('Invalid XML received from server. Forcing disconnect.')
            log.error(error)
            self._owner.Connection.disconnect()
            return 0
        except ValueError as e:
            log.debug('ValueError: %s' % str(e))
            self._owner.Connection.pollend()
            return 0
        if len(self._pendingExceptions) > 0:
            _pendingException = self._pendingExceptions.pop()
            sys.excepthook(*_pendingException)
            return
        if len(data) == 0:
            return '0'
        return len(data)

    def RegisterNamespace(self, xmlns, order='info'):
        """
        Create internal structures for newly registered namespace

        You can register handlers for this namespace afterwards. By default
        one namespace is already registered
        (jabber:client or jabber:component:accept depending on context.
        """
        log.debug('Registering namespace "%s"' % xmlns)
        self.handlers[xmlns] = {}
        self.RegisterProtocol('unknown', Protocol, xmlns=xmlns)
        self.RegisterProtocol('default', Protocol, xmlns=xmlns)

    def RegisterProtocol(self, tag_name, proto, xmlns=None, order='info'):
        """
        Used to declare some top-level stanza name to dispatcher

        Needed to start registering handlers for such stanzas. Iq, message and
        presence protocols are registered by default.
        """
        if not xmlns:
            xmlns = self._owner.defaultNamespace
        log.debug('Registering protocol "%s" as %s(%s)', tag_name, proto, xmlns)
        self.handlers[xmlns][tag_name] = {'type': proto, 'default': []}

    def RegisterNamespaceHandler(self, xmlns, handler, typ='', ns='', system=0):
        """
        Register handler for processing all stanzas for specified namespace
        """
        self.RegisterHandler('default', handler, typ, ns, xmlns, system)

    def RegisterHandler(self, name, handler, typ='', ns='', xmlns=None,
                        system=False, priority=50):
        """
        Register user callback as stanzas handler of declared type

        Callback arguments:
        dispatcher instance (for replying), incoming return of previous handlers.
        The callback must raise xmpp.NodeProcessed just before return if it wants
        to prevent other callbacks to be called with the same stanza as argument
        _and_, more     importantly     library from returning stanza to sender with error set.

        :param name: name of stanza. F.e. "iq".
        :param handler: user callback.
        :param typ: value of stanza's "type" attribute. If not specified any
                value will match
        :param ns: namespace of child that stanza must contain.
        :param xmlns: xml namespace
        :param system: call handler even if NodeProcessed Exception were raised
                       already.
        :param priority: The priority of the handler, higher get called later
        """
        if not xmlns:
            xmlns = self._owner.defaultNamespace

        if not typ and not ns:
            typ = 'default'

        log.debug(
            'Registering handler %s for "%s" type->%s ns->%s(%s) priority->%s',
            handler, name, typ, ns, xmlns, priority)

        if xmlns not in self.handlers:
            self.RegisterNamespace(xmlns, 'warn')
        if name not in self.handlers[xmlns]:
            self.RegisterProtocol(name, Protocol, xmlns, 'warn')

        specific = typ + ns
        if specific not in self.handlers[xmlns][name]:
            self.handlers[xmlns][name][specific] = []

        self.handlers[xmlns][name][specific].append(
            {'func': handler,
             'system': system,
             'priority': priority,
             'specific': specific})

    def RegisterHandlerOnce(self, name, handler, typ='', ns='', xmlns=None,
                            system=0):
        """
        Unregister handler after first call (not implemented yet)
        """
        # FIXME Drop or implement
        if not xmlns:
            xmlns = self._owner.defaultNamespace
        self.RegisterHandler(name, handler, typ, ns, xmlns, system)

    def UnregisterHandler(self, name, handler, typ='', ns='', xmlns=None):
        """
        Unregister handler. "typ" and "ns" must be specified exactly the same as
        with registering.
        """
        if not xmlns:
            xmlns = self._owner.defaultNamespace
        if not typ and not ns:
            typ = 'default'
        if xmlns not in self.handlers:
            return
        if name not in self.handlers[xmlns]:
            return

        specific = typ + ns
        if specific not in self.handlers[xmlns][name]:
            return
        for handler_dict in self.handlers[xmlns][name][specific]:
            if handler_dict['func'] == handler:
                try:
                    self.handlers[xmlns][name][specific].remove(handler_dict)
                    log.debug(
                        'Unregister handler %s for "%s" type->%s ns->%s(%s)',
                        handler, name, typ, ns, xmlns)
                except ValueError:
                    log.warning(
                        'Unregister failed: %s for "%s" type->%s ns->%s(%s)',
                        handler, name, typ, ns, xmlns)
                    pass

    def RegisterDefaultHandler(self, handler):
        """
        Specify the handler that will be used if no NodeProcessed exception were
        raised. This is returnStanzaHandler by default.
        """
        self._defaultHandler = handler

    def RegisterEventHandler(self, handler):
        """
        Register handler that will process events. F.e. "FILERECEIVED" event. See
        common/connection: _event_dispatcher()
        """
        self._eventHandler = handler

    def returnStanzaHandler(self, conn, stanza):
        """
        Return stanza back to the sender with <feature-not-implemented/> error
        set
        """
        if stanza.getType() in ('get', 'set'):
            conn._owner.send(Error(stanza, ERR_FEATURE_NOT_IMPLEMENTED))

    def RegisterCycleHandler(self, handler):
        """
        Register handler that will be called on every Dispatcher.Process() call
        """
        if handler not in self._cycleHandlers:
            self._cycleHandlers.append(handler)

    def UnregisterCycleHandler(self, handler):
        """
        Unregister handler that will be called on every Dispatcher.Process() call
        """
        if handler in self._cycleHandlers:
            self._cycleHandlers.remove(handler)

    def Event(self, realm, event, data=None):
        """
        Raise some event

        :param realm: scope of event. Usually a namespace.
        :param event: the event itself. F.e. "SUCCESSFUL SEND".
        :param data: data that comes along with event. Depends on event.
        """
        if self._eventHandler:
            self._eventHandler(realm, event, data)
        else:
            log.warning('Received unhandled event: %s' % event)

    def dispatch(self, stanza, session=None):
        """
        Main procedure that performs XMPP stanza recognition and calling
        apppropriate handlers for it. Called by simplexml
        """

        self.Event('', 'STANZA RECEIVED', stanza)

        if not session:
            session = self
        session.Stream._mini_dom = None

        # Count stanza
        self._owner.Smacks.count_incoming(stanza.getName())

        name = stanza.getName()
        if name == 'features':
            self._owner.got_features = True
            session.Stream.features = stanza
        elif name == 'error':
            if stanza.getTag('see-other-host'):
                self._owner.got_see_other_host = stanza

        xmlns = stanza.getNamespace()

        if xmlns not in self.handlers:
            log.warning('Unknown namespace: %s', xmlns)
            xmlns = 'unknown'
        # features stanza has been handled before
        if name not in self.handlers[xmlns]:
            if name not in ('features', 'stream'):
                log.warning('Unknown stanza: %s', stanza)
            else:
                log.debug('Got %s / %s stanza', xmlns, name)
            name = 'unknown'
        else:
            log.debug('Got %s / %s stanza', xmlns, name)

        # Convert simplexml to Protocol object
        stanza = self.handlers[xmlns][name]['type'](node=stanza)

        properties = get_properties_struct(name)
        if name == 'message':
            # https://tools.ietf.org/html/rfc6120#section-8.1.1.1
            # If the stanza does not include a 'to' address then the client MUST
            # treat it as if the 'to' address were included with a value of the
            # client's full JID.

            own_jid = self._owner.get_bound_jid()
            to = stanza.getTo()
            if to is None:
                stanza.setTo(own_jid)
            elif not to.bareMatch(own_jid):
                log.warning('Message addressed to someone else: %s', stanza)
                return

            try:
                stanza, properties.carbon_type = unwrap_carbon(stanza, own_jid)
            except InvalidFrom as exc:
                log.warning(exc)
                return
            except NodeProcessed as exc:
                log.info(exc)
                return

        typ = stanza.getType()
        if name == 'message' and not typ:
            typ = 'normal'
        elif not typ:
            typ = ''

        stanza.props = stanza.getProperties()
        log.debug('type: %s, properties: %s', typ, stanza.props)

        _id = stanza.getID()
        processed = False
        if _id in session._expected:
            if isinstance(session._expected[_id], tuple):
                cb, args = session._expected[_id]
                log.debug('Expected stanza arrived. Callback %s(%s) found',
                          cb, args)
                try:
                    cb(session, stanza, **args)
                except NodeProcessed:
                    pass
                except Exception:
                    raise
            else:
                log.debug('Expected stanza arrived')
                session._expected[_id] = stanza
            processed = True

        # Gather specifics depending on stanza properties
        specifics = ['default']
        if typ and typ in self.handlers[xmlns][name]:
            specifics.append(typ)
        for prop in stanza.props:
            if prop in self.handlers[xmlns][name]:
                specifics.append(prop)
            if typ and typ + prop in self.handlers[xmlns][name]:
                specifics.append(typ + prop)

        # Create the handler chain
        chain = []
        chain += self.handlers[xmlns]['default']['default']
        for specific in specifics:
            chain += self.handlers[xmlns][name][specific]

        # Sort chain with priority
        chain.sort(key=lambda x: x['priority'])

        for handler in chain:
            if not processed or handler['system']:
                try:
                    log.info('Call handler: %s', handler['func'].__qualname__)
                    # Backwards compatibility until all handlers support
                    # properties
                    signature = inspect.signature(handler['func'])
                    if 'properties' in signature.parameters:
                        handler['func'](session, stanza, properties)
                    else:
                        handler['func'](session, stanza)
                except NodeProcessed:
                    processed = True
                except Exception:
                    self._pendingExceptions.insert(0, sys.exc_info())
                    return

        # Stanza was not processed call default handler
        if not processed and self._defaultHandler:
            self._defaultHandler(session, stanza)

    def _WaitForData(self, data):
        """
        Internal wrapper around ProcessNonBlocking. Will check for
        """
        if data is None:
            return
        res = self.ProcessNonBlocking(data)
        # 0 result indicates that we have closed the connection, e.g.
        # we have released dispatcher, so self._owner has no methods
        if not res:
            return
        for (_id, _iq) in list(self._expected.items()):
            if _iq is None:
                # If the expected Stanza would have arrived, ProcessNonBlocking
                # would have placed the reply stanza in there
                continue
            if _id in self.on_responses:
                if len(self._expected) == 1:
                    self._owner.onreceive(None)
                resp, args = self.on_responses[_id]
                del self.on_responses[_id]
                if args is None:
                    resp(_iq)
                else:
                    resp(self._owner, _iq, **args)
                del self._expected[_id]

    def SendAndWaitForResponse(self, stanza, timeout=None, func=None, args=None):
        """
        Send stanza and wait for recipient's response to it. Will call transports
        on_timeout callback if response is not retrieved in time

        Be aware: Only timeout of latest call of SendAndWait is active.
        """
        if timeout is None:
            timeout = DEFAULT_TIMEOUT_SECONDS
        _waitid = self.send(stanza)
        if func:
            self.on_responses[_waitid] = (func, args)
        if timeout:
            self._owner.set_timeout(timeout)
        self._owner.onreceive(self._WaitForData)
        self._expected[_waitid] = None
        return _waitid

    def SendAndCallForResponse(self, stanza, func=None, args=None):
        """
        Put stanza on the wire and call back when recipient replies. Additional
        callback arguments can be specified in args
        """
        self.SendAndWaitForResponse(stanza, 0, func, args)

    def send(self, stanza, now=False):
        """
        Wrap transports send method when plugged into NonBlockingClient. Makes
        sure stanzas get ID and from tag.
        """
        ID = None
        if type(stanza) != str:
            if isinstance(stanza, Protocol):
                ID = stanza.getID()
                if ID is None:
                    stanza.setID(self.getAnID())
                    ID = stanza.getID()
                if self._owner._registered_name and not stanza.getAttr('from'):
                    stanza.setAttr('from', self._owner._registered_name)

        self._owner.Connection.send(stanza, now)

        # If no ID then it is a whitespace
        if hasattr(self._owner, 'Smacks') and ID:
            self._owner.Smacks.save_in_queue(stanza)

        return ID


class BOSHDispatcher(XMPPDispatcher):

    def PlugIn(self, owner, after_SASL=False, old_features=None):
        self.old_features = old_features
        self.after_SASL = after_SASL
        XMPPDispatcher.PlugIn(self, owner)

    def StreamInit(self):
        """
        Send an initial stream header
        """
        self.Stream = NodeBuilder()
        self.Stream.dispatch = self.dispatch
        self.Stream._dispatch_depth = 2
        self.Stream.stream_header_received = self._check_stream_start
        self.Stream.features = self.old_features

        self._metastream = Node('stream:stream')
        self._metastream.setNamespace(self._owner.Namespace)
        self._metastream.setAttr('version', '1.0')
        self._metastream.setAttr('xmlns:stream', NS_STREAMS)
        self._metastream.setAttr('to', self._owner.Server)
        if locale.getdefaultlocale()[0]:
            self._metastream.setAttr('xml:lang',
                    locale.getdefaultlocale()[0].split('_')[0])

        self.restart = True
        self._owner.Connection.send_init(after_SASL=self.after_SASL)

    def StreamTerminate(self):
        """
        Send a stream terminator
        """
        self._owner.Connection.send_terminator()

    def ProcessNonBlocking(self, data=None):
        if self.restart:
            fromstream = self._metastream
            fromstream.setAttr('from', fromstream.getAttr('to'))
            fromstream.delAttr('to')
            data = '%s%s>%s' % (XML_DECLARATION, str(fromstream)[:-2], data)
            self.restart = False
        return XMPPDispatcher.ProcessNonBlocking(self, data)

    def dispatch(self, stanza, session=None):
        if stanza.getName() == 'body' and stanza.getNamespace() == NS_HTTP_BIND:

            stanza_attrs = stanza.getAttrs()
            if 'authid' in stanza_attrs:
                # should be only in init response
                # auth module expects id of stream in document attributes
                self.Stream._document_attrs['id'] = stanza_attrs['authid']
            self._owner.Connection.handle_body_attrs(stanza_attrs)

            children = stanza.getChildren()
            if children:
                for child in children:
                    # if child doesn't have any ns specified, simplexml (or expat)
                    # thinks it's of parent's (BOSH body) namespace, so we have to
                    # rewrite it to jabber:client
                    if child.getNamespace() == NS_HTTP_BIND:
                        child.setNamespace(self._owner.defaultNamespace)
                    XMPPDispatcher.dispatch(self, child, session)
        else:
            XMPPDispatcher.dispatch(self, stanza, session)
