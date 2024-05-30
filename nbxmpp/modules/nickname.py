# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import PresenceType
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import Node
from nbxmpp.protocol import Presence
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Nickname(BaseModule):

    _depends = {"publish": "PubSub"}

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_pubsub_nickname,
                ns=Namespace.PUBSUB_EVENT,
                priority=16,
            ),
            StanzaHandler(
                name="message",
                callback=self._process_nickname,
                ns=Namespace.NICK,
                priority=40,
            ),
            StanzaHandler(
                name="presence",
                callback=self._process_nickname,
                ns=Namespace.NICK,
                priority=40,
            ),
        ]

    def _process_nickname(
        self,
        _client: Client,
        stanza: Message | Presence,
        properties: MessageProperties | PresenceProperties,
    ) -> None:
        if stanza.getName() == "message":
            properties.nickname = self._parse_nickname(stanza)

        elif stanza.getName() == "presence":
            # the nickname MUST NOT be included in presence broadcasts
            # (i.e., <presence/> stanzas with no 'type' attribute or
            # of type "unavailable").
            # Usage is not recommended in MUC, but it is a workaround
            # to allow code points forbidden in resource parts in nicknames.
            if not properties.from_muc and properties.type in (
                PresenceType.AVAILABLE,
                PresenceType.UNAVAILABLE,
            ):
                return
            properties.nickname = self._parse_nickname(stanza)

    def _process_pubsub_nickname(
        self, _client: Client, _stanza: Message, properties: MessageProperties
    ) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.NICK:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        nick = self._parse_nickname(item)
        if nick is None:
            self._log.info("Received nickname: %s - nickname removed", properties.jid)
            return

        self._log.info("Received nickname: %s - %s", properties.jid, nick)
        properties.pubsub_event = properties.pubsub_event._replace(data=nick)

    @staticmethod
    def _parse_nickname(stanza: Node) -> str | None:
        nickname = stanza.getTag("nick", namespace=Namespace.NICK)
        if nickname is None:
            return None
        return nickname.getData() or None

    @iq_request_task
    def set_nickname(self, nickname: str | None, public: bool = False):
        task = yield

        access_model = "open" if public else "presence"

        options = {
            "pubsub#persist_items": "true",
            "pubsub#access_model": access_model,
        }

        item = Node("nick", {"xmlns": Namespace.NICK})
        if nickname is not None:
            item.addData(nickname)

        result = yield self.publish(
            Namespace.NICK,
            item,
            id_="current",
            options=options,
            force_node_options=True,
        )

        yield finalize(task, result)

    @iq_request_task
    def set_access_model(self, public: bool):
        task = yield

        access_model = "open" if public else "presence"

        result = yield self._client.get_module("PubSub").set_access_model(
            Namespace.NICK, access_model
        )

        yield finalize(task, result)
