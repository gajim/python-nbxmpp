# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload
from typing import TYPE_CHECKING

import logging
import re
import time
from collections.abc import Callable
from xml.parsers.expat import ExpatError

from gi.repository import GLib

from nbxmpp.exceptions import StanzaDecrypted
from nbxmpp.modules.activity import Activity
from nbxmpp.modules.adhoc import AdHoc
from nbxmpp.modules.annotations import Annotations
from nbxmpp.modules.attention import Attention
from nbxmpp.modules.blocking import Blocking
from nbxmpp.modules.bookmarks.native_bookmarks import NativeBookmarks
from nbxmpp.modules.bookmarks.pep_bookmarks import PEPBookmarks
from nbxmpp.modules.bookmarks.private_bookmarks import PrivateBookmarks
from nbxmpp.modules.captcha import Captcha
from nbxmpp.modules.chat_markers import ChatMarkers
from nbxmpp.modules.chatstates import Chatstates
from nbxmpp.modules.correction import Correction
from nbxmpp.modules.delay import Delay
from nbxmpp.modules.delimiter import Delimiter
from nbxmpp.modules.discovery import Discovery
from nbxmpp.modules.eme import EME
from nbxmpp.modules.entity_caps import EntityCaps
from nbxmpp.modules.entity_time import EntityTime
from nbxmpp.modules.http_auth import HTTPAuth
from nbxmpp.modules.http_upload import HTTPUpload
from nbxmpp.modules.ibb import IBB
from nbxmpp.modules.idle import Idle
from nbxmpp.modules.iq import BaseIq
from nbxmpp.modules.last_activity import LastActivity
from nbxmpp.modules.location import Location
from nbxmpp.modules.mam import MAM
from nbxmpp.modules.mds import MDS
from nbxmpp.modules.message import BaseMessage
from nbxmpp.modules.misc import unwrap_carbon
from nbxmpp.modules.misc import unwrap_mam
from nbxmpp.modules.mood import Mood
from nbxmpp.modules.muc import MUC
from nbxmpp.modules.muc.hats import Hats
from nbxmpp.modules.muc.moderation import Moderation
from nbxmpp.modules.muclumbus import Muclumbus
from nbxmpp.modules.nickname import Nickname
from nbxmpp.modules.omemo import OMEMO
from nbxmpp.modules.oob import OOB
from nbxmpp.modules.openpgp import OpenPGP
from nbxmpp.modules.pgplegacy import PGPLegacy
from nbxmpp.modules.ping import Ping
from nbxmpp.modules.presence import BasePresence
from nbxmpp.modules.pubsub import PubSub
from nbxmpp.modules.reactions import Reactions
from nbxmpp.modules.receipts import Receipts
from nbxmpp.modules.register import Register
from nbxmpp.modules.replies import Replies
from nbxmpp.modules.retraction import Retraction
from nbxmpp.modules.roster import Roster
from nbxmpp.modules.security_labels import SecurityLabels
from nbxmpp.modules.software_version import SoftwareVersion
from nbxmpp.modules.tune import Tune
from nbxmpp.modules.user_avatar import UserAvatar
from nbxmpp.modules.vcard4 import VCard4
from nbxmpp.modules.vcard_avatar import VCardAvatar
from nbxmpp.modules.vcard_temp import VCardTemp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_FEATURE_NOT_IMPLEMENTED
from nbxmpp.protocol import Error
from nbxmpp.protocol import InvalidFrom
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import InvalidStanza
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Presence
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import StreamErrorNode
from nbxmpp.simplexml import Node
from nbxmpp.simplexml import NodeBuilder
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import get_invalid_xml_regex
from nbxmpp.util import get_properties_struct
from nbxmpp.util import is_websocket_close
from nbxmpp.util import is_websocket_stream_error
from nbxmpp.util import LogAdapter
from nbxmpp.util import Observable

if TYPE_CHECKING:
    from nbxmpp.client import Client

log = logging.getLogger("nbxmpp.dispatcher")

NBXMPPModuleNameT = Literal[
    "Activity",
    "Activity",
    "AdHoc",
    "Annotations",
    "Attention",
    "BasePresence",
    "BaseMessage",
    "BaseIq",
    "Blocking",
    "Captcha",
    "ChatMarkers",
    "Chatstates",
    "Correction",
    "Delay",
    "Delimiter",
    "Discovery",
    "EME",
    "EntityCaps",
    "EntityTime",
    "Hats",
    "HTTPAuth",
    "HTTPUpload",
    "IBB",
    "Idle",
    "LastActivity",
    "Location",
    "MAM",
    "MDS",
    "Moderation",
    "Mood",
    "MUC",
    "Muclumbus",
    "NativeBookmarks",
    "Nickname",
    "OMEMO",
    "OOB",
    "OpenPGP",
    "PEPBookmarks",
    "PGPLegacy",
    "Ping",
    "PrivateBookmarks",
    "PubSub",
    "Reactions",
    "Receipts",
    "Register",
    "Replies",
    "Retraction",
    "Roster",
    "SecurityLabels",
    "SoftwareVersion",
    "Tune",
    "UserAvatar",
    "VCardAvatar",
    "VCardTemp",
    "VCard4",
]
NBXMPPModuleT = (
    Activity
    | AdHoc
    | Annotations
    | Attention
    | BasePresence
    | BaseMessage
    | BaseIq
    | Blocking
    | Captcha
    | ChatMarkers
    | Chatstates
    | Correction
    | Delay
    | Delimiter
    | Discovery
    | EME
    | EntityCaps
    | EntityTime
    | Hats
    | HTTPAuth
    | HTTPUpload
    | IBB
    | Idle
    | LastActivity
    | Location
    | MAM
    | MDS
    | Moderation
    | Mood
    | MUC
    | Muclumbus
    | NativeBookmarks
    | Nickname
    | OMEMO
    | OOB
    | OpenPGP
    | PEPBookmarks
    | PGPLegacy
    | Ping
    | PrivateBookmarks
    | PubSub
    | Reactions
    | Receipts
    | Register
    | Replies
    | Retraction
    | Roster
    | SecurityLabels
    | SoftwareVersion
    | Tune
    | UserAvatar
    | VCardAvatar
    | VCardTemp
    | VCard4
)


class StanzaDispatcher(Observable):
    """
    Dispatches stanzas to handlers

    Signals:
        before-dispatch
        parsing-error
        stream-end

    """

    def __init__(self, client: Client) -> None:
        Observable.__init__(self, log)
        self._client = client
        self._modules: dict[str, NBXMPPModuleT] = {}
        self._parser: NodeBuilder | None = None
        self._websocket_stream_error: str | None = None

        self._log = LogAdapter(log, {"context": client.log_context})

        self._handlers: dict[str, dict[str, dict[str, Any]]] = {}

        self._id_callbacks: dict[str, tuple[Callable[..., Any], float | None, Any]] = {}
        self._dispatch_callback: Callable[..., Any] | None = None
        self._timeout_id: int | None = None

        self._stanza_types = {
            "iq": Iq,
            "message": Message,
            "presence": Presence,
            "error": StreamErrorNode,
        }

        self.invalid_chars_re = get_invalid_xml_regex()

        self._register_namespace("unknown")
        self._register_namespace(Namespace.STREAMS)
        self._register_namespace(Namespace.CLIENT)
        self._register_protocol("iq", Iq)
        self._register_protocol("presence", Presence)
        self._register_protocol("message", Message)

        self._register_modules()

    def set_dispatch_callback(self, callback: Callable[..., Any]) -> None:
        self._log.info("Set dispatch callback: %s", callback)
        self._dispatch_callback = callback

    @overload
    def get_module(self, name: Literal["Activity"]) -> Activity: ...
    @overload
    def get_module(self, name: Literal["AdHoc"]) -> AdHoc: ...
    @overload
    def get_module(self, name: Literal["Annotations"]) -> Annotations: ...
    @overload
    def get_module(self, name: Literal["Attention"]) -> Attention: ...
    @overload
    def get_module(self, name: Literal["Blocking"]) -> Blocking: ...
    @overload
    def get_module(self, name: Literal["NativeBookmarks"]) -> NativeBookmarks: ...
    @overload
    def get_module(self, name: Literal["PEPBookmarks"]) -> PEPBookmarks: ...
    @overload
    def get_module(self, name: Literal["PrivateBookmarks"]) -> PrivateBookmarks: ...
    @overload
    def get_module(self, name: Literal["Captcha"]) -> Captcha: ...
    @overload
    def get_module(self, name: Literal["ChatMarkers"]) -> ChatMarkers: ...
    @overload
    def get_module(self, name: Literal["Chatstates"]) -> Chatstates: ...
    @overload
    def get_module(self, name: Literal["Correction"]) -> Correction: ...
    @overload
    def get_module(self, name: Literal["Delay"]) -> Delay: ...
    @overload
    def get_module(self, name: Literal["Delimiter"]) -> Delimiter: ...
    @overload
    def get_module(self, name: Literal["Discovery"]) -> Discovery: ...
    @overload
    def get_module(self, name: Literal["EME"]) -> EME: ...
    @overload
    def get_module(self, name: Literal["EntityCaps"]) -> EntityCaps: ...
    @overload
    def get_module(self, name: Literal["EntityTime"]) -> EntityTime: ...
    @overload
    def get_module(self, name: Literal["Hats"]) -> Hats: ...
    @overload
    def get_module(self, name: Literal["HTTPAuth"]) -> HTTPAuth: ...
    @overload
    def get_module(self, name: Literal["HTTPUpload"]) -> HTTPUpload: ...
    @overload
    def get_module(self, name: Literal["IBB"]) -> IBB: ...
    @overload
    def get_module(self, name: Literal["Idle"]) -> Idle: ...
    @overload
    def get_module(self, name: Literal["BaseIq"]) -> BaseIq: ...
    @overload
    def get_module(self, name: Literal["LastActivity"]) -> LastActivity: ...
    @overload
    def get_module(self, name: Literal["Location"]) -> Location: ...
    @overload
    def get_module(self, name: Literal["MAM"]) -> MAM: ...
    @overload
    def get_module(self, name: Literal["MDS"]) -> MDS: ...
    @overload
    def get_module(self, name: Literal["BaseMessage"]) -> BaseMessage: ...
    @overload
    def get_module(self, name: Literal["Mood"]) -> Mood: ...
    @overload
    def get_module(self, name: Literal["MUC"]) -> MUC: ...
    @overload
    def get_module(self, name: Literal["Moderation"]) -> Moderation: ...
    @overload
    def get_module(self, name: Literal["Muclumbus"]) -> Muclumbus: ...
    @overload
    def get_module(self, name: Literal["Nickname"]) -> Nickname: ...
    @overload
    def get_module(self, name: Literal["OMEMO"]) -> OMEMO: ...
    @overload
    def get_module(self, name: Literal["OOB"]) -> OOB: ...
    @overload
    def get_module(self, name: Literal["OpenPGP"]) -> OpenPGP: ...
    @overload
    def get_module(self, name: Literal["PGPLegacy"]) -> PGPLegacy: ...
    @overload
    def get_module(self, name: Literal["Ping"]) -> Ping: ...
    @overload
    def get_module(self, name: Literal["BasePresence"]) -> BasePresence: ...
    @overload
    def get_module(self, name: Literal["PubSub"]) -> PubSub: ...
    @overload
    def get_module(self, name: Literal["Reactions"]) -> Reactions: ...
    @overload
    def get_module(self, name: Literal["Receipts"]) -> Receipts: ...
    @overload
    def get_module(self, name: Literal["Register"]) -> Register: ...
    @overload
    def get_module(self, name: Literal["Replies"]) -> Replies: ...
    @overload
    def get_module(self, name: Literal["Retraction"]) -> Retraction: ...
    @overload
    def get_module(self, name: Literal["Roster"]) -> Roster: ...
    @overload
    def get_module(self, name: Literal["SecurityLabels"]) -> SecurityLabels: ...
    @overload
    def get_module(self, name: Literal["SoftwareVersion"]) -> SoftwareVersion: ...
    @overload
    def get_module(self, name: Literal["Tune"]) -> Tune: ...
    @overload
    def get_module(self, name: Literal["UserAvatar"]) -> UserAvatar: ...
    @overload
    def get_module(self, name: Literal["VCard4"]) -> VCard4: ...
    @overload
    def get_module(self, name: Literal["VCardAvatar"]) -> VCardAvatar: ...
    @overload
    def get_module(self, name: Literal["VCardTemp"]) -> VCardTemp: ...

    def get_module(self, name: NBXMPPModuleNameT) -> NBXMPPModuleT:
        return self._modules[name]

    def _register_modules(self):
        assert self._client is not None
        self._modules["Activity"] = Activity(self._client)
        self._modules["AdHoc"] = AdHoc(self._client)
        self._modules["Annotations"] = Annotations(self._client)
        self._modules["Attention"] = Attention(self._client)
        self._modules["BasePresence"] = BasePresence(self._client)
        self._modules["BaseMessage"] = BaseMessage(self._client)
        self._modules["BaseIq"] = BaseIq(self._client)
        self._modules["Blocking"] = Blocking(self._client)
        self._modules["Captcha"] = Captcha(self._client)
        self._modules["ChatMarkers"] = ChatMarkers(self._client)
        self._modules["Chatstates"] = Chatstates(self._client)
        self._modules["Correction"] = Correction(self._client)
        self._modules["Delay"] = Delay(self._client)
        self._modules["Delimiter"] = Delimiter(self._client)
        self._modules["Discovery"] = Discovery(self._client)
        self._modules["EME"] = EME(self._client)
        self._modules["EntityCaps"] = EntityCaps(self._client)
        self._modules["EntityTime"] = EntityTime(self._client)
        self._modules["Hats"] = Hats(self._client)
        self._modules["HTTPAuth"] = HTTPAuth(self._client)
        self._modules["HTTPUpload"] = HTTPUpload(self._client)
        self._modules["IBB"] = IBB(self._client)
        self._modules["Idle"] = Idle(self._client)
        self._modules["LastActivity"] = LastActivity(self._client)
        self._modules["Location"] = Location(self._client)
        self._modules["MAM"] = MAM(self._client)
        self._modules["MDS"] = MDS(self._client)
        self._modules["Moderation"] = Moderation(self._client)
        self._modules["Mood"] = Mood(self._client)
        self._modules["MUC"] = MUC(self._client)
        self._modules["Muclumbus"] = Muclumbus(self._client)
        self._modules["NativeBookmarks"] = NativeBookmarks(self._client)
        self._modules["Nickname"] = Nickname(self._client)
        self._modules["OMEMO"] = OMEMO(self._client)
        self._modules["OOB"] = OOB(self._client)
        self._modules["OpenPGP"] = OpenPGP(self._client)
        self._modules["PEPBookmarks"] = PEPBookmarks(self._client)
        self._modules["PGPLegacy"] = PGPLegacy(self._client)
        self._modules["Ping"] = Ping(self._client)
        self._modules["PrivateBookmarks"] = PrivateBookmarks(self._client)
        self._modules["PubSub"] = PubSub(self._client)
        self._modules["Reactions"] = Reactions(self._client)
        self._modules["Receipts"] = Receipts(self._client)
        self._modules["Register"] = Register(self._client)
        self._modules["Replies"] = Replies(self._client)
        self._modules["Retraction"] = Retraction(self._client)
        self._modules["Roster"] = Roster(self._client)
        self._modules["SecurityLabels"] = SecurityLabels(self._client)
        self._modules["SoftwareVersion"] = SoftwareVersion(self._client)
        self._modules["Tune"] = Tune(self._client)
        self._modules["UserAvatar"] = UserAvatar(self._client)
        self._modules["VCardAvatar"] = VCardAvatar(self._client)
        self._modules["VCardTemp"] = VCardTemp(self._client)
        self._modules["VCard4"] = VCard4(self._client)

        for instance in self._modules.values():
            for handler in instance.handlers:
                self.register_handler(handler)

    def reset_parser(self) -> None:
        if self._parser is not None:
            self._parser.dispatch = None
            self._parser.destroy()
            self._parser = None

        self._parser = NodeBuilder(dispatch_depth=2, finished=False)
        self._parser.dispatch = self.dispatch

    def replace_non_character(self, data: str) -> str:
        return re.sub(self.invalid_chars_re, "\ufffd", data)

    def process_data(self, data: str) -> None:
        # Parse incoming data

        data = self.replace_non_character(data)

        if self._client.is_websocket:
            stanza = Node(node=data)
            if is_websocket_stream_error(stanza):
                for tag in stanza.getChildren():
                    name = tag.getName()
                    if name != "text" and tag.getNamespace() == Namespace.XMPP_STREAMS:
                        self._websocket_stream_error = name

            elif is_websocket_close(stanza):
                self._log.info("Stream <close> received")
                self.notify("stream-end", self._websocket_stream_error)
                return

            self.dispatch(stanza)
            return

        try:
            self._parser.Parse(data)
        except (ExpatError, ValueError) as error:
            self._log.error("XML parsing error: %s", error)
            self.notify("parsing-error", str(error))
            return

        # end stream:stream tag received
        if self._parser.has_received_endtag():
            self._log.info("End of stream: %s", self._parser.stream_error)
            self.notify("stream-end", self._parser.stream_error)
            return

    def _register_namespace(self, xmlns: str) -> None:
        """
        Setup handler structure for namespace
        """
        self._log.debug('Register namespace "%s"', xmlns)
        self._handlers[xmlns] = {}
        self._register_protocol("error", Protocol, xmlns=xmlns)
        self._register_protocol("unknown", Protocol, xmlns=xmlns)
        self._register_protocol("default", Protocol, xmlns=xmlns)

    def _register_protocol(
        self, tag_name: str, protocol: Any, xmlns: str | None = None
    ) -> None:
        """
        Register protocol for top level tag names
        """
        if xmlns is None:
            xmlns = Namespace.CLIENT
        self._log.debug('Register protocol "%s (%s)" as %s', tag_name, xmlns, protocol)
        self._handlers[xmlns][tag_name] = {"type": protocol, "default": []}

    def register_handler(self, handler: StanzaHandler) -> None:
        """
        Register handler
        """

        xmlns = handler.xmlns or Namespace.CLIENT

        typ = handler.typ
        if not typ and not handler.ns:
            typ = "default"

        self._log.debug(
            'Register handler %s for "%s" type->%s ns->%s(%s) priority->%s',
            handler.callback,
            handler.name,
            typ,
            handler.ns,
            xmlns,
            handler.priority,
        )

        if xmlns not in self._handlers:
            self._register_namespace(xmlns)
        if handler.name not in self._handlers[xmlns]:
            self._register_protocol(handler.name, Protocol, xmlns)

        specific = typ + handler.ns
        if specific not in self._handlers[xmlns][handler.name]:
            self._handlers[xmlns][handler.name][specific] = []

        self._handlers[xmlns][handler.name][specific].append(
            {
                "func": handler.callback,
                "priority": handler.priority,
                "specific": specific,
            }
        )

    def unregister_handler(self, handler: StanzaHandler) -> None:
        """
        Unregister handler
        """

        xmlns = handler.xmlns or Namespace.CLIENT

        typ = handler.typ
        if not typ and not handler.ns:
            typ = "default"

        specific = typ + handler.ns
        try:
            self._handlers[xmlns][handler.name][specific]
        except KeyError:
            return

        for handler_dict in self._handlers[xmlns][handler.name][specific]:
            if handler_dict["func"] != handler.callback:
                continue

            try:
                self._handlers[xmlns][handler.name][specific].remove(handler_dict)
            except ValueError:
                self._log.warning(
                    'Unregister failed: %s for "%s" type->%s ns->%s(%s)',
                    handler.callback,
                    handler.name,
                    typ,
                    handler.ns,
                    xmlns,
                )
            else:
                self._log.debug(
                    'Unregister handler %s for "%s" type->%s ns->%s(%s)',
                    handler.callback,
                    handler.name,
                    typ,
                    handler.ns,
                    xmlns,
                )

    def _default_handler(self, stanza: Protocol) -> None:
        """
        Return stanza back to the sender with <feature-not-implemented/> error
        """
        if stanza.getType() in ("get", "set"):
            self._client.send_stanza(Error(stanza, ERR_FEATURE_NOT_IMPLEMENTED))

    def dispatch(self, stanza: Protocol) -> None:
        self.notify("before-dispatch", stanza)

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
            self._log.warning("Unknown namespace: %s", xmlns)
            xmlns = "unknown"

        if name not in self._handlers[xmlns]:
            self._log.warning("Unknown stanza: %s", stanza)
            name = "unknown"

        # Convert simplexml to Protocol object
        try:
            stanza = self._handlers[xmlns][name]["type"](node=stanza)
        except InvalidJid:
            self._log.warning("Invalid JID, ignoring stanza")
            self._log.warning(stanza)
            return

        own_jid = self._client.get_bound_jid()
        properties = get_properties_struct(name, own_jid)

        if name == "iq":
            if stanza.getFrom() is None and own_jid is not None:
                stanza.setFrom(own_jid.bare)

        if name == "message":
            # https://tools.ietf.org/html/rfc6120#section-8.1.1.1
            # If the stanza does not include a 'to' address then the client MUST
            # treat it as if the 'to' address were included with a value of the
            # client's full JID.

            to = stanza.getTo()
            if to is None:
                stanza.setTo(own_jid)

            elif not to.bare_match(own_jid):
                self._log.warning("Message addressed to someone else: %s", stanza)
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
            if name == "message":
                typ = "normal"
            elif name == "presence":
                typ = "available"
            else:
                typ = ""

        # Process callbacks
        _id = stanza.getID()
        func, _timeout, user_data = self._id_callbacks.pop(_id, (None, None, {}))
        if user_data is None:
            user_data = {}

        if func is not None:
            try:
                func(self._client, stanza, **user_data)
            except Exception:
                self._log.exception("Error while handling stanza")
            return

        props = stanza.getProperties()
        self._log.debug("type: %s, properties: %s", typ, props)

        chain = self._build_handler_chain(xmlns, name, typ, props)

        try:
            self._execute_handler_chain(chain, stanza, properties)
        except StanzaDecrypted:
            props = stanza.getProperties()
            self._log.debug("type: %s, properties after decryption: %s", typ, props)
            chain = self._build_handler_chain(
                xmlns, name, typ, props, after_decryption=True
            )
            self._execute_handler_chain(chain, stanza, properties)

    def _build_handler_chain(
        self,
        xmlns: str,
        name: str,
        typ: str,
        props: Any,
        *,
        after_decryption: bool = False,
    ) -> list[dict[str, Any]]:

        # Gather specifics depending on stanza properties
        specifics = ["default"]
        if typ and typ in self._handlers[xmlns][name]:
            specifics.append(typ)

        for prop in props:
            if prop in self._handlers[xmlns][name]:
                specifics.append(prop)

            if typ and typ + prop in self._handlers[xmlns][name]:
                specifics.append(typ + prop)

        # Create the handler chain
        chain: list[dict[str, Any]] = []
        chain += self._handlers[xmlns]["default"]["default"]
        for specific in specifics:
            chain += self._handlers[xmlns][name][specific]

        # Sort chain with priority
        chain.sort(key=lambda x: x["priority"])

        if after_decryption:
            # Filter everything out which was executed before decryption
            # so it is not executed again
            chain = list(filter(lambda x: x["priority"] > 9, chain))

        return chain

    def _execute_handler_chain(
        self, chain: Any, stanza: Protocol, properties: Any
    ) -> None:

        for handler in chain:
            self._log.info("Call handler: %s", handler["func"].__qualname__)
            try:
                handler["func"](self._client, stanza, properties)
            except NodeProcessed:
                return
            except StanzaDecrypted:
                raise
            except Exception:
                self._log.exception("Handler exception:")
                return

        # Stanza was not processed call default handler
        self._default_handler(stanza)

    def add_callback_for_id(
        self, id_: str, func: Callable[..., Any], timeout: float | None, user_data: Any
    ) -> None:
        if timeout is not None and self._timeout_id is None:
            self._log.info("Add timeout check")
            self._timeout_id = GLib.timeout_add_seconds(1, self._timeout_check)
            timeout = time.monotonic() + timeout
        self._id_callbacks[id_] = (func, timeout, user_data)

    def _timeout_check(self) -> bool:
        self._log.info("Run timeout check")
        timeouts: dict[str, tuple[Callable[..., Any], float | None, Any]] = {}
        for id_, data in self._id_callbacks.items():
            if data[1] is not None:
                timeouts[id_] = data

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
        self._client = None
        self._modules = {}
        self._parser = None
        self.clear_iq_callbacks()
        self._dispatch_callback = None
        self._handlers.clear()
        self._remove_timeout_source()
        self.remove_subscriptions()
