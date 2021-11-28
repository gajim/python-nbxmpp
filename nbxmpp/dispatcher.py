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
from collections import defaultdict

import typing
from typing import Any, Callable, Optional

import logging
import re
import time
import inspect
from pathlib import Path
from importlib import import_module
from xml.parsers.expat import ExpatError
from functools import singledispatchmethod

from gi.repository import GLib
from nbxmpp.const import ErrorCondition, ErrorType

from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.exceptions import InvalidFrom
from nbxmpp.exceptions import InvalidJid
from nbxmpp.exceptions import InvalidStanza
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.misc import unwrap_carbon
from nbxmpp.modules.misc import unwrap_mam
from nbxmpp.stream_parser import StreamParser
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import IqProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import Properties
from nbxmpp.util import get_child_namespaces
from nbxmpp.util import get_invalid_xml_regex
from nbxmpp.util import is_websocket_close
from nbxmpp.util import is_websocket_stream_error
from nbxmpp.util import Observable
from nbxmpp.util import LogAdapter
from nbxmpp import types

if typing.TYPE_CHECKING:
    from nbxmpp.client import Client


IdCallbackDictT = dict[str, tuple[Callable[..., Any],
                                  Optional[float],
                                  Optional[dict[str, Any]]]]

TimeoutDictT = dict[str, tuple[Callable[..., Any],
                               float,
                               Optional[dict[str, Any]]]]

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

        self._handlers: dict[str, dict[str, list[StanzaHandler]]] = defaultdict(lambda: defaultdict(list))

        self._id_callbacks: IdCallbackDictT = {}
        self._dispatch_callback = None
        self._timeout_id = None

        self.invalid_chars_re = get_invalid_xml_regex()

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
        self._parser = StreamParser(self.prepare_dispatch)

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

    def register_handler(self, handler: StanzaHandler):

        self._log.debug('Register handler: %s', handler)

        toplevel = handler.get_toplevel()
        specific = handler.get_specific()

        self._handlers[toplevel][specific].append(handler)


    def unregister_handler(self, handler: StanzaHandler):


        self._log.debug('Unregister handler: %s', handler)

        toplevel = handler.get_toplevel()
        specific = handler.get_specific()

        try:
            self._handlers[toplevel][specific].remove(handler)
        except ValueError:
            self._log.warning('Failed to remove handler: %s', handler)


    def _default_handler(self, stanza: types.Stanza):
        if stanza.localname != 'iq':
            return

        if stanza.get('type') in ('get', 'set'):
            self._client.send_stanza(
                stanza.make_error(
                    ErrorType.CANCEL,
                    ErrorCondition.FEATURE_NOT_IMPLEMENTED,
                    Namespace.XMPP_STANZAS))

    @singledispatchmethod
    def prepare_dispatch(self, element):
        self._dispatch(element, Properties())

    @prepare_dispatch.register
    def _(self, element: types.Presence):
        own_jid = self._client.get_bound_jid()
        properties = PresenceProperties(own_jid)

        self._dispatch(element, properties)

    @prepare_dispatch.register
    def _(self, element: types.Iq):
        own_jid = self._client.get_bound_jid()
        if own_jid is None:
            # Check if this is even possible, iq without bound JID
            return

        if element.get_from() is None:
            element.set_from(own_jid.bare)

        properties = IqProperties(own_jid)

        self._dispatch(element, properties)

    @prepare_dispatch.register
    def _(self, element: types.Message):
        # set defaul type attr
        if element.get('type') is None:
            element.set('type', 'normal')

        # https://tools.ietf.org/html/rfc6120#section-8.1.1.1
        # If the stanza does not include a 'to' address then the client MUST
        # treat it as if the 'to' address were included with a value of the
        # client's full JID.

        own_jid = self._client.get_bound_jid()

        to = element.get_to()
        if to is None:
            element.set_to(own_jid)

        elif not to.bare_match(own_jid):
            self._log.warning('Message addressed to someone else: %s',
                              element)
            return

        if element.get_from() is None:
            element.set_from(own_jid.bare)

        properties = MessageProperties(own_jid)

        # Unwrap carbon
        try:
            element, properties.carbon = unwrap_carbon(element, own_jid)
        except (InvalidFrom, InvalidJid) as exc:
            self._log.warning(exc)
            self._log.warning(element)
            return
        except NodeProcessed as exc:
            self._log.info(exc)
            return

        # Unwrap mam
        try:
            element, properties.mam = unwrap_mam(element, own_jid)
        except (InvalidStanza, InvalidJid) as exc:
            self._log.warning(exc)
            self._log.warning(element)
            return

        self._dispatch(element, properties)

    def _dispatch(self, element: types.Base, properties: Any):
        self.notify('before-dispatch', element)

        if self._dispatch_callback is not None:
            self._dispatch_callback(element)
            return

        # Count stanza
        self._client._smacks.count_incoming(element.localname)

        callback_data = self._get_iq_callback_data(element)
        if callback_data is not None:
            func, user_data = callback_data

            try:
                func(self._client, element, **user_data)
            except Exception:
                self._log.exception('Error while handling element')
            return

        handlers = self._generate_handler_chain(element)

        for handler in handlers:
            self._log.debug('Call handler: %s', handler.callback.__qualname__)
            try:
                handler.callback(self._client, element, properties)
            except NodeProcessed:
                return
            except Exception:
                self._log.exception('Handler exception:')
                return

        # Element was not processed call default handler
        self._default_handler(element)

    def _make_specifics(self, element: types.Base) -> set[str]:
        # Example:
        #
        # <message type="error">
        #   <extension xmlns="my:extension:1"/>
        # </message>
        #
        # specifics = [
        #     '{*}*',                   handlers catch on toplevel (message)
        #     '{error}*',               handlers catch only on type
        #     '{*}my:extension:1'       handlers catch only on namespace
        #     '{error}my:extension:1'   handlers catch on type and namespace
        # ]
        #
        # Code depends on sets deduplicating automatically

        type_value = element.get('type') or '*'

        specifics = {
            '{*}*',
            '{%s}*' % type_value
        }

        namespaces = get_child_namespaces(element)
        for namespace in namespaces:
            specifics.add('{*}%s' % namespace)
            specifics.add('{%s}%s' % (type_value, namespace))

        return specifics

    def _generate_handler_chain(self,
                                element: types.Base) -> list[StanzaHandler]:

        specifics = self._make_specifics(element)

        chain: list[StanzaHandler] = []
        for specific in specifics:
            chain += self._handlers[element.tag][specific]

        chain.sort(key=lambda handler: handler.priority)

        return chain

    def _get_iq_callback_data(self, element: types.Base) -> Optional[tuple[Callable[..., Any], dict[str, Any]]]:
        if element.localname != 'iq':
            return None

        id_ = element.get('id')
        if id_ is None:
            return None

        callback_data = self._id_callbacks.pop(id_, None)
        if callback_data is None:
            return None

        func, _, user_data = callback_data
        if user_data is None:
            user_data = {}

        return func, user_data

    def add_callback_for_id(self,
                            id_: str,
                            func: Callable[..., Any],
                            timeout: Optional[float] = None,
                            user_data: Optional[dict[str, Any]] = None):

        if timeout is not None and self._timeout_id is None:
            self._log.info('Add timeout check')
            self._timeout_id = GLib.timeout_add_seconds(1, self._timeout_check)
            timeout = time.monotonic() + timeout
        self._id_callbacks[id_] = (func, timeout, user_data)

    def _timeout_check(self):
        self._log.info('Run timeout check')
        timeouts: TimeoutDictT = {}
        for id_, data in self._id_callbacks.items():
            func, timeout, user_data = data
            if timeout is not None:
                timeouts[id_] = (func, timeout, user_data)

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

    def remove_iq_callback(self, id_: str):
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
