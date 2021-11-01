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

from __future__ import annotations

import typing

import logging
import re
import time
import inspect
from pathlib import Path
from importlib import import_module
from xml.parsers.expat import ExpatError

from gi.repository import GLib

from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.exceptions import InvalidFrom
from nbxmpp.exceptions import InvalidJid
from nbxmpp.exceptions import InvalidStanza
from nbxmpp.builder import Iq
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.misc import unwrap_carbon
from nbxmpp.modules.misc import unwrap_mam
from nbxmpp.stream_parser import StreamParser
from nbxmpp.util import get_child_namespaces, get_properties_struct
from nbxmpp.util import get_invalid_xml_regex
from nbxmpp.util import is_websocket_close
from nbxmpp.util import is_websocket_stream_error
from nbxmpp.util import Observable
from nbxmpp.util import LogAdapter

if typing.TYPE_CHECKING:
    from nbxmpp.client import Client


log = logging.getLogger('nbxmpp.dispatcher')


class StanzaDispatcher(Observable):
    """
    Dispatches stanzas to handlers

    Signals:
        before-dispatch
        parsing-error
        stream-end

    """

    def __init__(self, client: Client):
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

        self.invalid_chars_re = get_invalid_xml_regex()

        self._register_namespace('unknown')
        self._register_namespace(Namespace.STREAMS)
        self._register_namespace(Namespace.CLIENT)
        self._register_protocol('iq')
        self._register_protocol('presence')
        self._register_protocol('message')

        self._load_modules()

    def _get_module_namespace(self, path: Path) -> str:
        new_path = path.as_posix().rsplit('/modules/', maxsplit=1)[1]
        return new_path.replace('.py', '').replace('/', '.')

    def _load_modules(self):
        path = Path(__file__).parent / 'modules'
        for module_path in path.glob('**/*.py'):
            if module_path.name.startswith('__'):
                continue

            module_namespace = self._get_module_namespace(module_path)
            module = import_module(f'.modules.{module_namespace}', 
                                   package='nbxmpp')

            for _, test_class in inspect.getmembers(module, inspect.isclass):

                if test_class is BaseModule:
                    continue

                if BaseModule not in inspect.getmro(test_class):
                    continue

                module_name = test_class.__name__
                self._modules[module_name] = test_class(self._client)

        for instance in self._modules.values():
            for handler in instance.handlers:
                self.register_handler(handler)

    def set_dispatch_callback(self, callback):
        self._log.info('Set dispatch callback: %s', callback)
        self._dispatch_callback = callback

    def get_module(self, name):
        return self._modules[name]

    def reset_parser(self):
        if self._parser is not None:
            self._parser.destroy()
        self._parser = StreamParser(self.dispatch)

    def replace_non_character(self, data):
        return re.sub(self.invalid_chars_re, '\ufffd', data)

    def process_data(self, data):
        # Parse incoming data

        data = self.replace_non_character(data)

        if self._client.is_websocket:
            stanza = Node(node=data)
            if is_websocket_stream_error(stanza):
                for tag in stanza.get_children():
                    name = tag.localname
                    if (name != 'text' and
                            tag.namespace == Namespace.XMPP_STREAMS):
                        self._websocket_stream_error = name

            elif is_websocket_close(stanza):
                self._log.info('Stream <close> received')
                self.notify('stream-end', self._websocket_stream_error)
                return

            self.dispatch(stanza)
            return

        try:
            self._parser.feed(data)
        except (ExpatError, ValueError) as error:
            self._log.error('XML parsing error: %s', error)
            self.notify('parsing-error', str(error))
            return

        # end stream:stream tag received
        if self._parser.is_stream_end():
            self._log.info('End of stream: %s', self._parser.get_stream_error())
            self.notify('stream-end', self._parser.get_stream_error())
            return

    def _register_namespace(self, xmlns):
        """
        Setup handler structure for namespace
        """
        self._log.debug('Register namespace "%s"', xmlns)
        self._handlers[xmlns] = {}
        self._register_protocol('error', xmlns=xmlns)
        self._register_protocol('unknown', xmlns=xmlns)
        self._register_protocol('default', xmlns=xmlns)

    def _register_protocol(self, tag_name, xmlns=None):
        """
        Register protocol for top level tag names
        """
        if xmlns is None:
            xmlns = Namespace.CLIENT
        self._log.debug('Register protocol "%s (%s)"', tag_name, xmlns)
        self._handlers[xmlns][tag_name] = {'default': []}

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
            self._register_protocol(handler.name, xmlns)

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
        if stanza.get('type') in ('get', 'set'):
            self._client.send_stanza(Error(stanza, ERR_FEATURE_NOT_IMPLEMENTED))

    def dispatch(self, stanza):
        self.notify('before-dispatch', stanza)

        if self._dispatch_callback is not None:
            self._dispatch_callback(stanza)
            return

        # Count stanza
        self._client._smacks.count_incoming(stanza.localname)

        name = stanza.localname
        xmlns = stanza.namespace

        if xmlns not in self._handlers:
            self._log.warning('Unknown namespace: %s', xmlns)
            xmlns = 'unknown'

        if name not in self._handlers[xmlns]:
            self._log.warning('Unknown stanza: %s', stanza)
            name = 'unknown'

        own_jid = self._client.get_bound_jid()
        properties = get_properties_struct(name, own_jid)

        if name == 'iq':
            if stanza.get_from() is None and own_jid is not None:
                stanza.set_from(own_jid.bare)

        if name == 'message':
            # https://tools.ietf.org/html/rfc6120#section-8.1.1.1
            # If the stanza does not include a 'to' address then the client MUST
            # treat it as if the 'to' address were included with a value of the
            # client's full JID.

            to = stanza.get_to()
            if to is None:
                stanza.set_to(own_jid)

            elif not to.bare_match(own_jid):
                self._log.warning('Message addressed to someone else: %s',
                                  stanza)
                return

            if stanza.get_from() is None:
                stanza.set_from(own_jid.bare)

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

        typ = stanza.get('type')
        if name == 'message' and not typ:
            typ = 'normal'
        elif not typ:
            typ = ''

        stanza.props = get_child_namespaces(stanza)
        self._log.debug('type: %s, properties: %s', typ, stanza.props)

        # Process callbacks
        _id = stanza.get('id')
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
