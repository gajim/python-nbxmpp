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
from nbxmpp.structs import OOBData
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class OOB(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_oob,
                ns=Namespace.X_OOB,
                priority=15,
            ),
        ]

    def _process_message_oob(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        oob = stanza.getTag("x", namespace=Namespace.X_OOB)
        if oob is None:
            return

        url = oob.getTagData("url")
        if url is None:
            self._log.warning("OOB data without url")
            self._log.warning(stanza)
            return

        desc = oob.getTagData("desc")
        properties.oob = OOBData(url, desc)
