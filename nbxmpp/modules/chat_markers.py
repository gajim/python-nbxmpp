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
from nbxmpp.structs import ChatMarker
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class ChatMarkers(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_marker,
                ns=Namespace.CHATMARKERS,
                priority=15,
            ),
        ]

    def _process_message_marker(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        type_ = stanza.getTag("received", namespace=Namespace.CHATMARKERS)
        if type_ is None:
            type_ = stanza.getTag("displayed", namespace=Namespace.CHATMARKERS)
            if type_ is None:
                type_ = stanza.getTag("acknowledged", namespace=Namespace.CHATMARKERS)
                if type_ is None:
                    return

        name = type_.getName()
        id_ = type_.getAttr("id")
        if id_ is None:
            self._log.warning("Chatmarker without id")
            self._log.warning(stanza)
            return

        properties.marker = ChatMarker(name, id_)
