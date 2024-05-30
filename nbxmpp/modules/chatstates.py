# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import Chatstate
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Chatstates(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_chatstate,
                ns=Namespace.CHATSTATES,
                priority=15,
            ),
        ]

    def _process_message_chatstate(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        try:
            chatstate = parse_chatstate(stanza)
        except ValueError as error:
            self._log.warning("Invalid chatstate: %s", error)
            self._log.warning(stanza)
            return

        if chatstate is None:
            return

        if properties.is_mam_message:
            return

        properties.chatstate = chatstate


def parse_chatstate(stanza: Message) -> Chatstate | None:
    children = stanza.getChildren()
    for child in children:
        if child.getNamespace() == Namespace.CHATSTATES:
            return Chatstate(child.getName())
    return None
