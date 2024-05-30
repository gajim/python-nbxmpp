# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Attention(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_attention,
                ns=Namespace.ATTENTION,
                priority=15,
            ),
        ]

    def _process_message_attention(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        attention = stanza.getTag("attention", namespace=Namespace.ATTENTION)
        if attention is None:
            return

        if properties.is_mam_message:
            return

        if properties.is_carbon_message and properties.carbon.is_sent:
            return

        if stanza.getTag("delay", namespace=Namespace.DELAY2) is not None:
            return

        properties.attention = True
