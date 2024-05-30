# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Literal
from typing import TYPE_CHECKING

from nbxmpp.const import PresenceShow
from nbxmpp.const import PresenceType
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import log_calls
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_BAD_REQUEST
from nbxmpp.protocol import Error as ErrorStanza
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Presence
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import error_factory

if TYPE_CHECKING:
    from nbxmpp.client import Client


class BasePresence(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="presence", callback=self._process_presence_base, priority=10
            ),
        ]

    def _process_presence_base(
        self, _client: Client, stanza: Presence, properties: PresenceProperties
    ) -> None:
        properties.type = self._parse_type(stanza)
        properties.priority = self._parse_priority(stanza)
        properties.show = self._parse_show(stanza)
        properties.jid = stanza.getFrom()
        properties.id = stanza.getID()
        properties.status = stanza.getStatus()

        if properties.type.is_error:
            properties.error = error_factory(stanza)

        own_jid = self._client.get_bound_jid()
        properties.self_presence = own_jid == properties.jid
        properties.self_bare = properties.jid.bare_match(own_jid)

    def _parse_priority(self, stanza: Presence) -> int:
        priority = stanza.getPriority()
        if priority is None:
            return 0

        try:
            priority = int(priority)
        except Exception:
            self._log.warning("Invalid priority value: %s", priority)
            self._log.warning(stanza)
            return 0

        if priority not in range(-129, 128):
            self._log.warning("Invalid priority value: %s", priority)
            self._log.warning(stanza)
            return 0

        return priority

    def _parse_type(self, stanza: Presence) -> PresenceType:
        type_ = stanza.getType()
        try:
            return PresenceType(type_)
        except ValueError:
            self._log.warning("Presence with invalid type received")
            self._log.warning(stanza)
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

    def _parse_show(self, stanza: Presence) -> PresenceShow:
        show = stanza.getShow()
        if show is None:
            return PresenceShow.ONLINE
        try:
            return PresenceShow(stanza.getShow())
        except ValueError:
            self._log.warning("Presence with invalid show")
            self._log.warning(stanza)
            return PresenceShow.ONLINE

    @log_calls
    def unsubscribe(self, jid: JID) -> None:
        self.send(jid=jid, typ="unsubscribe")

    @log_calls
    def unsubscribed(self, jid: JID) -> None:
        self.send(jid=jid, typ="unsubscribed")

    @log_calls
    def subscribed(self, jid: JID) -> None:
        self.send(jid=jid, typ="subscribed")

    @log_calls
    def subscribe(
        self, jid: JID, status: str | None = None, nick: str | None = None
    ) -> None:
        self.send(jid=jid, typ="subscribe", status=status, nick=nick)

    def send(
        self,
        jid: JID | None = None,
        typ: str | None = None,
        priority: int | None = None,
        show: Literal["chat", "away", "xa", "dnd"] | None = None,
        status: str | None = None,
        nick: str | None = None,
        caps: dict[str, str] | None = None,
        idle_time=None,
        signed=None,
        muc: bool = False,
        muc_history=None,
        muc_password: str | None = None,
        extend=None,
    ) -> None:

        if show is not None and show not in ("chat", "away", "xa", "dnd"):
            raise ValueError("Invalid show value: %s" % show)

        presence = Presence(jid, typ, priority, show, status)
        if nick is not None:
            nick_tag = presence.setTag("nick", namespace=Namespace.NICK)
            nick_tag.setData(nick)

        if idle_time is not None:
            idle_node = presence.setTag("idle", namespace=Namespace.IDLE)
            idle_node.setAttr("since", idle_time)

        if caps is not None and typ != "unavailable":
            presence.setTag("c", namespace=Namespace.CAPS, attrs=caps)

        if signed is not None:
            presence.setTag(Namespace.SIGNED + " x").setData(signed)

        if muc or muc_history is not None or muc_password is not None:
            muc_x = presence.setTag(Namespace.MUC + " x")
            if muc_history is not None:
                muc_x.setTag("history", muc_history)

            if muc_password is not None:
                muc_x.setTagData("password", muc_password)

        if extend is not None:
            for node in extend:
                presence.addChild(node=node)

        self._client.send_stanza(presence)
