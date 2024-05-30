# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import isMucPM
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import ReceiptData
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import generate_id

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Receipts(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_receipt,
                ns=Namespace.RECEIPTS,
                priority=15,
            ),
        ]

    def _process_message_receipt(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        request = stanza.getTag("request", namespace=Namespace.RECEIPTS)
        if request is not None:
            properties.receipt = ReceiptData(request.getName())
            return

        received = stanza.getTag("received", namespace=Namespace.RECEIPTS)
        if received is not None:
            id_ = received.getAttr("id")
            if id_ is None:
                self._log.warning("Receipt without id attr")
                self._log.warning(stanza)
                return

            properties.receipt = ReceiptData(received.getName(), id_)


def build_receipt(stanza: Message | Any) -> Message:
    if not isinstance(stanza, Message):
        raise ValueError("Stanza type must be protocol.Message")

    if stanza.getType() == "error":
        raise ValueError("Receipt can not be generated for type error messages")

    if stanza.getID() is None:
        raise ValueError("Receipt can not be generated for messages without id")

    if stanza.getTag("received", namespace=Namespace.RECEIPTS) is not None:
        raise ValueError("Receipt can not be generated for receipts")

    is_muc_pm = isMucPM(stanza)

    jid = stanza.getFrom()
    typ = stanza.getType()
    if typ == "groupchat" or not is_muc_pm:
        jid = jid.new_as_bare()

    message = Message(to=jid, typ=typ)
    if is_muc_pm:
        message.setTag("x", namespace=Namespace.MUC_USER)
    message_id = generate_id()
    message.setID(message_id)
    message.setReceiptReceived(stanza.getID())
    message.setHint("store")
    message.setOriginID(message_id)
    return message
