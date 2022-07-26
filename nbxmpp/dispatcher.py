# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import logging
import re
import time
from xml.parsers.expat import ExpatError

from gi.repository import GLib

from nbxmpp.simplexml import NodeBuilder
from nbxmpp.simplexml import Node
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import InvalidFrom
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import InvalidStanza
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Presence
from nbxmpp.protocol import Message
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import Error
from nbxmpp.protocol import StreamErrorNode
from nbxmpp.protocol import ERR_FEATURE_NOT_IMPLEMENTED
from nbxmpp.modules.eme import EME
from nbxmpp.modules.http_auth import HTTPAuth
from nbxmpp.modules.presence import BasePresence
from nbxmpp.modules.message import BaseMessage
from nbxmpp.modules.iq import BaseIq
from nbxmpp.modules.nickname import Nickname
from nbxmpp.modules.delay import Delay
from nbxmpp.modules.muc import MUC
from nbxmpp.modules.muc.moderation import Moderation
from nbxmpp.modules.idle import Idle
from nbxmpp.modules.pgplegacy import PGPLegacy
from nbxmpp.modules.vcard_avatar import VCardAvatar
from nbxmpp.modules.captcha import Captcha
from nbxmpp.modules.entity_caps import EntityCaps
from nbxmpp.modules.blocking import Blocking
from nbxmpp.modules.pubsub import PubSub
from nbxmpp.modules.activity import Activity
from nbxmpp.modules.tune import Tune
from nbxmpp.modules.mood import Mood
from nbxmpp.modules.location import Location
from nbxmpp.modules.user_avatar import UserAvatar
from nbxmpp.modules.bookmarks.private_bookmarks import PrivateBookmarks
from nbxmpp.modules.bookmarks.pep_bookmarks import PEPBookmarks
from nbxmpp.modules.bookmarks.native_bookmarks import NativeBookmarks
from nbxmpp.modules.openpgp import OpenPGP
from nbxmpp.modules.omemo import OMEMO
from nbxmpp.modules.annotations import Annotations
from nbxmpp.modules.muclumbus import Muclumbus
from nbxmpp.modules.software_version import SoftwareVersion
from nbxmpp.modules.adhoc import AdHoc
from nbxmpp.modules.ibb import IBB
from nbxmpp.modules.discovery import Discovery
from nbxmpp.modules.chat_markers import ChatMarkers
from nbxmpp.modules.receipts import Receipts
from nbxmpp.modules.oob import OOB
from nbxmpp.modules.correction import Correction
from nbxmpp.modules.attention import Attention
from nbxmpp.modules.security_labels import SecurityLabels
from nbxmpp.modules.chatstates import Chatstates
from nbxmpp.modules.register import Register
from nbxmpp.modules.http_upload import HTTPUpload
from nbxmpp.modules.mam import MAM
from nbxmpp.modules.vcard_temp import VCardTemp
from nbxmpp.modules.vcard4 import VCard4
from nbxmpp.modules.ping import Ping
from nbxmpp.modules.delimiter import Delimiter
from nbxmpp.modules.roster import Roster
from nbxmpp.modules.last_activity import LastActivity
from nbxmpp.modules.entity_time import EntityTime
from nbxmpp.modules.misc import unwrap_carbon
from nbxmpp.modules.misc import unwrap_mam
from nbxmpp.util import get_properties_struct
from nbxmpp.util import get_invalid_xml_regex
from nbxmpp.util import is_websocket_close
from nbxmpp.util import is_websocket_stream_error
from nbxmpp.util import Observable
from nbxmpp.util import LogAdapter


log = logging.getLogger('nbxmpp.dispatcher')


class StanzaDispatcher(Observable):
    """
    Dispatches stanzas to handlers

    Signals:
        before-dispatch
        parsing-error
        stream-end

    """

    def __init__(self, client):
        Observable.__init__(self, log)
        self._client = client
        self._modules = {}
        self._parser = None
        self._websocket_stream_error = None

        self._log = LogAdapter(log, {'context': client.log_context})

        self._handlers = {}

        self._id_callbacks = {}
        self._dispatch_callback = None
        self._timeout_id = None

        self._stanza_types = {
            'iq': Iq,
            'message': Message,
            'presence': Presence,
            'error': StreamErrorNode,
        }

        self.invalid_chars_re = get_invalid_xml_regex()

        self._register_namespace('unknown')
        self._register_namespace(Namespace.STREAMS)
        self._register_namespace(Namespace.CLIENT)
        self._register_protocol('iq', Iq)
        self._register_protocol('presence', Presence)
        self._register_protocol('message', Message)

        self._register_modules()

    def set_dispatch_callback(self, callback):
        self._log.info('Set dispatch callback: %s', callback)
        self._dispatch_callback = callback

    def get_module(self, name):
        return self._modules[name]

    def _register_modules(self):
        self._modules['BasePresence'] = BasePresence(self._client)
        self._modules['BaseMessage'] = BaseMessage(self._client)
        self._modules['BaseIq'] = BaseIq(self._client)
        self._modules['EME'] = EME(self._client)
        self._modules['HTTPAuth'] = HTTPAuth(self._client)
        self._modules['Nickname'] = Nickname(self._client)
        self._modules['MUC'] = MUC(self._client)
        self._modules['Moderation'] = Moderation(self._client)
        self._modules['Delay'] = Delay(self._client)
        self._modules['Captcha'] = Captcha(self._client)
        self._modules['Idle'] = Idle(self._client)
        self._modules['PGPLegacy'] = PGPLegacy(self._client)
        self._modules['VCardAvatar'] = VCardAvatar(self._client)
        self._modules['EntityCaps'] = EntityCaps(self._client)
        self._modules['Blocking'] = Blocking(self._client)
        self._modules['PubSub'] = PubSub(self._client)
        self._modules['Mood'] = Mood(self._client)
        self._modules['Activity'] = Activity(self._client)
        self._modules['Tune'] = Tune(self._client)
        self._modules['Location'] = Location(self._client)
        self._modules['UserAvatar'] = UserAvatar(self._client)
        self._modules['PrivateBookmarks'] = PrivateBookmarks(self._client)
        self._modules['PEPBookmarks'] = PEPBookmarks(self._client)
        self._modules['NativeBookmarks'] = NativeBookmarks(self._client)
        self._modules['OpenPGP'] = OpenPGP(self._client)
        self._modules['OMEMO'] = OMEMO(self._client)
        self._modules['Annotations'] = Annotations(self._client)
        self._modules['Muclumbus'] = Muclumbus(self._client)
        self._modules['SoftwareVersion'] = SoftwareVersion(self._client)
        self._modules['AdHoc'] = AdHoc(self._client)
        self._modules['IBB'] = IBB(self._client)
        self._modules['Discovery'] = Discovery(self._client)
        self._modules['ChatMarkers'] = ChatMarkers(self._client)
        self._modules['Receipts'] = Receipts(self._client)
        self._modules['OOB'] = OOB(self._client)
        self._modules['Correction'] = Correction(self._client)
        self._modules['Attention'] = Attention(self._client)
        self._modules['SecurityLabels'] = SecurityLabels(self._client)
        self._modules['Chatstates'] = Chatstates(self._client)
        self._modules['Register'] = Register(self._client)
        self._modules['HTTPUpload'] = HTTPUpload(self._client)
        self._modules['MAM'] = MAM(self._client)
        self._modules['VCardTemp'] = VCardTemp(self._client)
        self._modules['VCard4'] = VCard4(self._client)
        self._modules['Ping'] = Ping(self._client)
        self._modules['Delimiter'] = Delimiter(self._client)
        self._modules['Roster'] = Roster(self._client)
        self._modules['LastActivity'] = LastActivity(self._client)
        self._modules['EntityTime'] = EntityTime(self._client)

        for instance in self._modules.values():
            for handler in instance.handlers:
                self.register_handler(handler)

    def reset_parser(self):
        if self._parser is not None:
            self._parser.dispatch = None
            self._parser.destroy()
            self._parser = None

        self._parser = NodeBuilder(dispatch_depth=2,
                                   finished=False)
        self._parser.dispatch = self.dispatch

    def replace_non_character(self, data):
        return re.sub(self.invalid_chars_re, '\ufffd', data)

    def process_data(self, data):
        # Parse incoming data

        data = self.replace_non_character(data)

        if self._client.is_websocket:
            stanza = Node(node=data)
            if is_websocket_stream_error(stanza):
                for tag in stanza.getChildren():
                    name = tag.getName()
                    if (name != 'text' and
                            tag.getNamespace() == Namespace.XMPP_STREAMS):
                        self._websocket_stream_error = name

            elif is_websocket_close(stanza):
                self._log.info('Stream <close> received')
                self.notify('stream-end', self._websocket_stream_error)
                return

            self.dispatch(stanza)
            return

        try:
            self._parser.Parse(data)
        except (ExpatError, ValueError) as error:
            self._log.error('XML parsing error: %s', error)
            self.notify('parsing-error', str(error))
            return

        # end stream:stream tag received
        if self._parser.has_received_endtag():
            self._log.info('End of stream: %s', self._parser.streamError)
            self.notify('stream-end', self._parser.streamError)
            return

    def _register_namespace(self, xmlns):
        """
        Setup handler structure for namespace
        """
        self._log.debug('Register namespace "%s"', xmlns)
        self._handlers[xmlns] = {}
        self._register_protocol('error', Protocol, xmlns=xmlns)
        self._register_protocol('unknown', Protocol, xmlns=xmlns)
        self._register_protocol('default', Protocol, xmlns=xmlns)

    def _register_protocol(self, tag_name, protocol, xmlns=None):
        """
        Register protocol for top level tag names
        """
        if xmlns is None:
            xmlns = Namespace.CLIENT
        self._log.debug('Register protocol "%s (%s)" as %s',
                        tag_name, xmlns, protocol)
        self._handlers[xmlns][tag_name] = {'type': protocol, 'default': []}

    def register_handler(self, handler):
        """
        Register handler
        """

        xmlns = handler.xmlns or Namespace.CLIENT

        typ = handler.typ
        if not typ and not handler.ns:
            typ = 'default'

        self._log.debug(
            'Register handler %s for "%s" type->%s ns->%s(%s) priority->%s',
            handler.callback, handler.name, typ, handler.ns,
            xmlns, handler.priority
        )

        if xmlns not in self._handlers:
            self._register_namespace(xmlns)
        if handler.name not in self._handlers[xmlns]:
            self._register_protocol(handler.name, Protocol, xmlns)

        specific = typ + handler.ns
        if specific not in self._handlers[xmlns][handler.name]:
            self._handlers[xmlns][handler.name][specific] = []

        self._handlers[xmlns][handler.name][specific].append(
            {'func': handler.callback,
             'priority': handler.priority,
             'specific': specific})

    def unregister_handler(self, handler):
        """
        Unregister handler
        """

        xmlns = handler.xmlns or Namespace.CLIENT

        typ = handler.typ
        if not typ and not handler.ns:
            typ = 'default'

        specific = typ + handler.ns
        try:
            self._handlers[xmlns][handler.name][specific]
        except KeyError:
            return

        for handler_dict in self._handlers[xmlns][handler.name][specific]:
            if handler_dict['func'] != handler.callback:
                continue

            try:
                self._handlers[xmlns][handler.name][specific].remove(
                    handler_dict)
            except ValueError:
                self._log.warning(
                    'Unregister failed: %s for "%s" type->%s ns->%s(%s)',
                    handler.callback, handler.name, typ, handler.ns, xmlns)
            else:
                self._log.debug(
                    'Unregister handler %s for "%s" type->%s ns->%s(%s)',
                    handler.callback, handler.name, typ, handler.ns, xmlns)

    def _default_handler(self, stanza):
        """
        Return stanza back to the sender with <feature-not-implemented/> error
        """
        if stanza.getType() in ('get', 'set'):
            self._client.send_stanza(Error(stanza, ERR_FEATURE_NOT_IMPLEMENTED))

    def dispatch(self, stanza):
        self.notify('before-dispatch', stanza)

        if self._dispatch_callback is not None:
            name = stanza.getName()
            protocol_class = self._stanza_types.get(name)
            if protocol_class is not None:
                stanza = protocol_class(node=stanza)
            self._dispatch_callback(stanza)
            return

        # Count stanza
        self._client._smacks.count_incoming(stanza.getName())

        name = stanza.getName()
        xmlns = stanza.getNamespace()

        if xmlns not in self._handlers:
            self._log.warning('Unknown namespace: %s', xmlns)
            xmlns = 'unknown'

        if name not in self._handlers[xmlns]:
            self._log.warning('Unknown stanza: %s', stanza)
            name = 'unknown'

        # Convert simplexml to Protocol object
        try:
            stanza = self._handlers[xmlns][name]['type'](node=stanza)
        except InvalidJid:
            self._log.warning('Invalid JID, ignoring stanza')
            self._log.warning(stanza)
            return

        own_jid = self._client.get_bound_jid()
        properties = get_properties_struct(name, own_jid)

        if name == 'iq':
            if stanza.getFrom() is None and own_jid is not None:
                stanza.setFrom(own_jid.bare)

        if name == 'message':
            # https://tools.ietf.org/html/rfc6120#section-8.1.1.1
            # If the stanza does not include a 'to' address then the client MUST
            # treat it as if the 'to' address were included with a value of the
            # client's full JID.

            to = stanza.getTo()
            if to is None:
                stanza.setTo(own_jid)

            elif not to.bare_match(own_jid):
                self._log.warning('Message addressed to someone else: %s',
                                  stanza)
                return

            if stanza.getFrom() is None:
                stanza.setFrom(own_jid.bare)

            # Unwrap carbon
            try:
                stanza, properties.carbon = unwrap_carbon(stanza, own_jid)
            except (InvalidFrom, InvalidJid) as exc:
                self._log.warning(exc)
                self._log.warning(stanza)
                return
            except NodeProcessed as exc:
                self._log.info(exc)
                return

            # Unwrap mam
            try:
                stanza, properties.mam = unwrap_mam(stanza, own_jid)
            except (InvalidStanza, InvalidJid) as exc:
                self._log.warning(exc)
                self._log.warning(stanza)
                return

        typ = stanza.getType()
        if not typ:
            if name == 'message':
                typ = 'normal'
            elif name == 'presence':
                typ = 'available'
            else:
                typ = ''

        stanza.props = stanza.getProperties()
        self._log.debug('type: %s, properties: %s', typ, stanza.props)

        # Process callbacks
        _id = stanza.getID()
        func, _timeout, user_data = self._id_callbacks.pop(
            _id, (None, None, {}))
        if user_data is None:
            user_data = {}

        if func is not None:
            try:
                func(self._client, stanza, **user_data)
            except Exception:
                self._log.exception('Error while handling stanza')
            return

        # Gather specifics depending on stanza properties
        specifics = ['default']
        if typ and typ in self._handlers[xmlns][name]:
            specifics.append(typ)
        for prop in stanza.props:
            if prop in self._handlers[xmlns][name]:
                specifics.append(prop)
            if typ and typ + prop in self._handlers[xmlns][name]:
                specifics.append(typ + prop)

        # Create the handler chain
        chain = []
        chain += self._handlers[xmlns]['default']['default']
        for specific in specifics:
            chain += self._handlers[xmlns][name][specific]

        # Sort chain with priority
        chain.sort(key=lambda x: x['priority'])

        for handler in chain:
            self._log.info('Call handler: %s', handler['func'].__qualname__)
            try:
                handler['func'](self._client, stanza, properties)
            except NodeProcessed:
                return
            except Exception:
                self._log.exception('Handler exception:')
                return

        # Stanza was not processed call default handler
        self._default_handler(stanza)

    def add_callback_for_id(self, id_, func, timeout, user_data):
        if timeout is not None and self._timeout_id is None:
            self._log.info('Add timeout check')
            self._timeout_id = GLib.timeout_add_seconds(
                1, self._timeout_check)
            timeout = time.monotonic() + timeout
        self._id_callbacks[id_] = (func, timeout, user_data)

    def _timeout_check(self):
        self._log.info('Run timeout check')
        timeouts = {}
        for id_, data in self._id_callbacks.items():
            if data[1] is not None:
                timeouts[id_] = data

        if not timeouts:
            self._log.info('Remove timeout check, no timeouts scheduled')
            self._timeout_id = None
            return False

        for id_, data in timeouts.items():
            func, timeout, user_data = data

            if user_data is None:
                user_data = {}

            if timeout < time.monotonic():
                self._id_callbacks.pop(id_)
                func(self._client, None, **user_data)
        return True

    def _remove_timeout_source(self):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def remove_iq_callback(self, id_):
        self._id_callbacks.pop(id_, None)

    def clear_iq_callbacks(self):
        self._log.info('Clear IQ callbacks')
        self._id_callbacks.clear()

    def cleanup(self):
        self._client = None
        self._modules = {}
        self._parser = None
        self.clear_iq_callbacks()
        self._dispatch_callback = None
        self._handlers.clear()
        self._remove_timeout_source()
        self.remove_subscriptions()
