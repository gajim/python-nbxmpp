# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import TYPE_CHECKING

import logging
import time

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import ERR_ITEM_NOT_FOUND
from nbxmpp.protocol import ErrorNode
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import DiscoIdentity
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import DiscoItem
from nbxmpp.structs import DiscoItems
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client

log = logging.getLogger("nbxmpp.m.discovery")


class Discovery(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="iq",
                callback=self._process_disco_info,
                typ="get",
                ns=Namespace.DISCO_INFO,
                priority=90,
            ),
        ]

    @staticmethod
    def _process_disco_info(
        client: Client, stanza: Iq, _properties: IqProperties
    ) -> None:
        iq = stanza.buildReply("error")
        iq.addChild(node=ErrorNode(ERR_ITEM_NOT_FOUND))
        client.send_stanza(iq)
        raise NodeProcessed

    @iq_request_task
    def disco_info(self, jid: JID | str, node: str | None = None):
        _task = yield

        response = yield get_disco_request(Namespace.DISCO_INFO, jid, node)
        if response.isError():
            raise StanzaError(response)
        yield parse_disco_info(response)

    @iq_request_task
    def disco_items(self, jid: JID | str, node: str | None = None):
        _task = yield

        response = yield get_disco_request(Namespace.DISCO_ITEMS, jid, node)
        if response.isError():
            raise StanzaError(response)
        yield parse_disco_items(response)


def parse_disco_info(stanza: Iq, timestamp: float | None = None) -> DiscoInfo:
    identities: list[DiscoIdentity] = []
    features: list[str] = []
    dataforms = []

    if timestamp is None:
        timestamp = time.time()

    query = stanza.getQuery()
    for node in query.getTags("identity"):
        attrs = node.getAttrs()
        try:
            identities.append(
                DiscoIdentity(
                    category=attrs["category"],
                    type=attrs["type"],
                    name=attrs.get("name"),
                    lang=attrs.get("xml:lang"),
                )
            )
        except Exception:
            raise MalformedStanzaError("invalid attributes", stanza)

    for node in query.getTags("feature"):
        try:
            features.append(node.getAttr("var"))
        except Exception:
            raise MalformedStanzaError("invalid attributes", stanza)

    for node in query.getTags("x", namespace=Namespace.DATA):
        dataforms.append(extend_form(node))

    return DiscoInfo(
        stanza=stanza,
        identities=identities,
        features=features,
        dataforms=dataforms,
        timestamp=timestamp,
    )


def parse_disco_items(stanza: Iq) -> DiscoItems:
    items: list[DiscoItem] = []

    query = stanza.getQuery()
    for node in query.getTags("item"):
        attrs = node.getAttrs()
        try:
            items.append(
                DiscoItem(
                    jid=attrs["jid"], name=attrs.get("name"), node=attrs.get("node")
                )
            )
        except Exception:
            raise MalformedStanzaError("invalid attributes", stanza)

    return DiscoItems(jid=stanza.getFrom(), node=query.getAttr("node"), items=items)


def get_disco_request(namespace: str, jid: str, node: str | None = None) -> Iq:
    iq = Iq("get", to=jid, queryNS=namespace)
    if node:
        iq.getQuery().setAttr("node", node)
    return iq
