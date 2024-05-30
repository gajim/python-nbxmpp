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
from nbxmpp.structs import EMEData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class EME(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_eme,
                ns=Namespace.EME,
                priority=40,
            )
        ]

    def _process_eme(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        encryption = stanza.getTag("encryption", namespace=Namespace.EME)
        if encryption is None:
            return

        name = encryption.getAttr("name")
        namespace = encryption.getAttr("namespace")
        if namespace is None:
            self._log.warning("No namespace on message")
            return

        properties.eme = EMEData(name=name, namespace=namespace)
        self._log.info("Found data: %s", properties.eme)
