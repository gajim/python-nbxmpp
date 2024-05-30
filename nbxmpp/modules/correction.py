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
from nbxmpp.structs import CorrectionData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Correction(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_correction,
                ns=Namespace.CORRECT,
                priority=15,
            ),
        ]

    def _process_message_correction(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        replace = stanza.getTag("replace", namespace=Namespace.CORRECT)
        if replace is None:
            return

        id_ = replace.getAttr("id")
        if id_ is None:
            self._log.warning("Correcton without id attribute")
            self._log.warning(stanza)
            return

        if stanza.getID() == id_:
            self._log.warning("correcton id == message id")
            self._log.warning(stanza)
            return

        properties.correction = CorrectionData(id_)
