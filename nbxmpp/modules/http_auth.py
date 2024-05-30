# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Message
from nbxmpp.structs import HTTPAuthData
from nbxmpp.structs import IqProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class HTTPAuth(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)
        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_http_auth,
                ns=Namespace.HTTP_AUTH,
                priority=40,
            ),
            StanzaHandler(
                name="iq",
                callback=self._process_http_auth,
                typ="get",
                ns=Namespace.HTTP_AUTH,
                priority=40,
            ),
        ]

    def _process_http_auth(
        self,
        _client: Client,
        stanza: Iq | Message,
        properties: IqProperties | MessageProperties,
    ) -> None:
        confirm = stanza.getTag("confirm", namespace=Namespace.HTTP_AUTH)
        if confirm is None:
            return

        attrs = confirm.getAttrs()
        body = stanza.getTagData("body")
        id_ = attrs.get("id")
        method = attrs.get("method")
        url = attrs.get("url")
        properties.http_auth = HTTPAuthData(id_, method, url, body)
        self._log.info("HTTPAuth received: %s %s %s %s", id_, method, url, body)
