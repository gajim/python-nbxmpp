# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

# XEP-0461: Message Replies

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import ReplyData
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Replies(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message,
                ns=Namespace.REPLY,
                priority=15,
            )
        ]

    def _process_message(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:

        reply = stanza.getTag("reply", namespace=Namespace.REPLY)
        if reply is None:
            return

        to = reply.getAttr("to")
        if to is None:
            self._log.warning('Received reply without "to" attribute')
            return

        try:
            reply_to = JID.from_string(to)
        except Exception:
            self._log.warning("Invalid jid on reply element: %s", to)
            return

        reply_to_id = reply.getAttr("id")
        if reply_to_id is None:
            self._log.warning('Received reply without "id"')
            return

        properties.reply_data = ReplyData(to=reply_to, id=reply_to_id)
