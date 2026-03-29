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
from typing import Any
from typing import Literal

import inspect
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from xml.parsers.expat import ExpatError

from gi.repository import GLib

from nbxmpp.jid import JID
from nbxmpp.modules.base import BaseModule
from nbxmpp.parser import BaseParser
from nbxmpp.parser import get_stream_parser
from nbxmpp.structs import BaseHandler
from nbxmpp.structs import IqProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import Properties
from nbxmpp.util import get_child_namespaces
from nbxmpp.util import LogAdapter
from nbxmpp.util import Observable

from . import elements
from . import exceptions

if typing.TYPE_CHECKING:
    from nbxmpp.client import Client


IdCallbackDictT = dict[
    str, tuple[Callable[..., Any], float | None, dict[str, Any] | None]
]

TimeoutDictT = dict[str, tuple[Callable[..., Any], float, dict[str, Any] | None]]
PhaseT = Literal["preparation", "decryption", "stanza"]

log = logging.getLogger("nbxmpp.dispatcher")


class Dispatcher(Observable):
    """
    Dispatches XMPP stream elements to handlers

    Signals:
        before-dispatch
        iq-not-processed
        parsing-error
        stream-start
        stream-end
    """

    def __init__(self, client: Client):
        Observable.__init__(self, log)
        self._client = client
        self._modules: dict[str, BaseModule] = {}
        self._parser: BaseParser | None = None
        self._websocket_stream_error = None

        self._log = LogAdapter(log, {"context": client.log_context})

        self._handlers: dict[str, dict[str, dict[str, list[BaseHandler]]]] = (
            defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )

        self._id_callbacks: IdCallbackDictT = {}
        self._dispatch_callback = None
        self._timeout_id = None

        self._account_jid: JID | None = None

        self._load_modules()

    def _load_modules(self) -> None:
        path = Path(__file__).parent / "modules"
        for module_path in path.glob("**/*.py"):
            if module_path.name.startswith("__"):
                continue

            new_path = module_path.as_posix().rsplit("/modules/", maxsplit=1)[1]
            module_namespace = new_path.replace(".py", "").replace("/", ".")
            module = import_module(f".modules.{module_namespace}", package="nbxmpp")

            for _, xep_module in inspect.getmembers(module, inspect.isclass):
                if xep_module is BaseModule:
                    continue

                if BaseModule not in inspect.getmro(xep_module):
                    continue

                module_name = xep_module.__name__
                self._modules[module_name] = xep_module(self._client)

        for instance in self._modules.values():
            for handler in instance.handlers:
                self.register_handler(handler)

    def set_dispatch_callback(self, callback: Callable[[elements.Base], Any]):
        self._log.info("Set dispatch callback: %s", callback)
        self._dispatch_callback = callback

    def get_module(self, name: str) -> BaseModule:
        return self._modules[name]

    def reset_parser(self):
        if self._parser is not None:
            self._parser.destroy()

        self._parser = get_stream_parser(
            self._client.is_websocket, self._client.log_context
        )

        self._parser.subscribe("stream-start", self._on_stream_start)
        self._parser.subscribe("stream-end", self._on_stream_end)
        self._parser.subscribe("element", self._on_element)

    def process_data(self, data: str) -> None:
        assert self._parser is not None
        # if self._client.is_websocket:
        #     stanza = Node(node=data)
        #     if is_websocket_stream_error(stanza):
        #         for tag in stanza.get_children():
        #             name = tag.localname
        #             if (name != 'text' and
        #                     tag.namespace == Namespace.XMPP_STREAMS):
        #                 self._websocket_stream_error = name

        try:
            self._parser.feed(data)
        except (ExpatError, ValueError) as error:
            self._log.error("XML parsing error: %s", error)
            self.notify("parsing-error", str(error))
            return

    def register_handler(self, handler: BaseHandler) -> None:
        self._log.debug("Register handler: %s", handler)

        phase, toplevel, specific = handler.get_details()
        self._handlers[phase][toplevel][specific].append(handler)

    def unregister_handler(self, handler: BaseHandler) -> None:
        self._log.debug("Unregister handler: %s", handler)

        phase, toplevel, specific = handler.get_details()

        try:
            self._handlers[phase][toplevel][specific].remove(handler)
        except ValueError:
            self._log.warning("Failed to remove handler: %s", handler)

    def _on_stream_start(
        self, _parser: BaseParser, _signal_name: str, element: elements.Base
    ) -> None:
        self.notify("stream-start", element)

    def _on_stream_end(
        self, _parser: BaseParser, _signal_name: str, element: elements.Base
    ) -> None:
        self._log.info("End of stream: %s", element)
        # TODO, get real error
        self.notify("stream-end", "error")

    def _on_element(
        self, _parser: BaseParser, _signal_name: str, element: elements.Base
    ) -> None:
        self._dispatch(element)

    def _dispatch(self, element: elements.Base) -> None:
        self.notify("before-dispatch", element)

        match element:
            case elements.Nonza():
                pass

            case elements.Presence():
                properties = PresenceProperties()

            case elements.Iq():
                properties = IqProperties()

            case elements.Message():
                properties = MessageProperties()

            case _:
                self._log.warning("Unknown element received")
                self._log.warning(element)
                return

        if self._dispatch_callback is not None:
            self._dispatch_callback(element)
            return

        assert not isinstance(element, elements.Nonza)

        if not self._dispatch_phase("preparation", element, properties):
            return

        if not self._dispatch_phase("decryption", element, properties):
            return

        if isinstance(element, elements.Iq):
            if not self._dispatch_iq_with_callback(element, properties):
                return

        if not self._dispatch_phase("stanza", element, properties):
            return

        self._default_handler(element)

    def _dispatch_phase(
        self, phase: PhaseT, element: elements.Stanza, properties: Properties
    ) -> bool:
        handlers = self._generate_handler_chain(phase, element)

        for handler in handlers:
            self._log.debug(
                "Call handler: %s / %s", phase, handler.callback.__qualname__
            )
            try:
                handler.callback(self._client, element, properties)
            except exceptions.NodeProcessed:
                return False
            except Exception:
                self._log.exception("Handler exception:")
                return False

        return True

    def _dispatch_iq_with_callback(self, element: elements.Iq, properties) -> bool:
        callback_data = self._get_iq_callback_data(element)
        if callback_data is None:
            return True

        func, user_data = callback_data

        try:
            func(self._client, element, properties, **user_data)
        except Exception:
            self._log.exception("Error while handling element")
        return False

    def _default_handler(self, element: elements.Stanza) -> None:
        if not isinstance(element, elements.Iq):
            return

        if element.get("type") in ("get", "set"):
            self.notify("iq-not-processed", element)

    def _make_specifics(self, phase: PhaseT, element: elements.Base) -> set[str]:
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

        type_value = element.get("type") or "*"

        specifics = {"{*}*", "{%s}*" % type_value}

        if phase == "preparation":
            return specifics

        namespaces = get_child_namespaces(element)
        for namespace in namespaces:
            specifics.add("{*}%s" % namespace)
            specifics.add("{%s}%s" % (type_value, namespace))

        return specifics

    def _generate_handler_chain(
        self, phase: PhaseT, element: elements.Base
    ) -> list[BaseHandler]:
        specifics = self._make_specifics(phase, element)

        chain: list[BaseHandler] = []
        for specific in specifics:
            chain += self._handlers[phase][element.tag][specific]

        chain.sort(key=lambda handler: handler.priority)

        return chain

    def _get_iq_callback_data(
        self, element: elements.Iq
    ) -> tuple[Callable[..., Any], dict[str, Any]] | None:
        if element.localname != "iq":
            return None

        id_ = element.get("id")
        if id_ is None:
            return None

        callback_data = self._id_callbacks.pop(id_, None)
        if callback_data is None:
            return None

        func, _, user_data = callback_data
        if user_data is None:
            user_data = {}

        return func, user_data

    def add_callback_for_id(
        self,
        id_: str,
        func: Callable[..., Any],
        timeout: float | None = None,
        user_data: dict[str, Any] | None = None,
    ) -> None:
        if timeout is not None and self._timeout_id is None:
            self._log.info("Add timeout check")
            self._timeout_id = GLib.timeout_add_seconds(1, self._timeout_check)
            timeout = time.monotonic() + timeout
        self._id_callbacks[id_] = (func, timeout, user_data)

    def _timeout_check(self) -> bool:
        self._log.info("Run timeout check")
        timeouts: TimeoutDictT = {}
        for id_, data in self._id_callbacks.items():
            func, timeout, user_data = data
            if timeout is not None:
                timeouts[id_] = (func, timeout, user_data)

        if not timeouts:
            self._log.info("Remove timeout check, no timeouts scheduled")
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

    def _remove_timeout_source(self) -> None:
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def remove_iq_callback(self, id_: str) -> None:
        self._id_callbacks.pop(id_, None)

    def clear_iq_callbacks(self) -> None:
        self._log.info("Clear IQ callbacks")
        self._id_callbacks.clear()

    def cleanup(self) -> None:
        del self._client
        self._modules = {}

        if self._parser is not None:
            self._parser.destroy()
        self._parser = None

        self.clear_iq_callbacks()
        self._dispatch_callback = None
        self._handlers.clear()
        self._remove_timeout_source()
        self.remove_subscriptions()
