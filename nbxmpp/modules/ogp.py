# Copyright (C) 2022 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from dataclasses import fields

from nbxmpp import Node
from nbxmpp.modules.base import BaseModule
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import OpenGraphData
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client
    from nbxmpp.protocol import Message


class OpenGraph(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_opengraph,
                ns=Namespace.RDF,
                priority=15,
            ),
        ]

    def _process_message_opengraph(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        for desc in stanza.getTags("Description", namespace=Namespace.RDF):
            about = desc.getAttr("about") or desc.getNamespacedAttr(
                "about", Namespace.RDF
            )
            if about:
                properties.open_graph[about] = self._process_description(desc)

    @staticmethod
    def _process_description(description: Node) -> OpenGraphData:
        data = OpenGraphData()
        for field in fields(OpenGraphData):
            tag = field.name
            node = description.getTag(tag, namespace=Namespace.OPEN_GRAPH)
            if node is not None:
                setattr(data, tag, node.getData())
        return data
