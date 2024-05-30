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
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Presence
from nbxmpp.structs import DiscoIdentity
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import EntityCapsData
from nbxmpp.structs import IqProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import compute_caps_hash

if TYPE_CHECKING:
    from nbxmpp.client import Client


class EntityCaps(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="presence",
                callback=self._process_entity_caps,
                ns=Namespace.CAPS,
                priority=15,
            ),
            StanzaHandler(
                name="iq",
                callback=self._process_disco_info,
                typ="get",
                ns=Namespace.DISCO_INFO,
                priority=20,
            ),
        ]

        self._identities = []
        self._features = []

        self._uri: str | None = None
        self._node: str | None = None
        self._caps: DiscoInfo | None = None
        self._caps_hash: str | None = None

    def _process_disco_info(
        self, client: Client, stanza: Iq, _properties: IqProperties
    ) -> None:
        if self._caps is None:
            return

        node = stanza.getQuerynode()
        if node is not None:
            if self._node != node:
                return

        iq = stanza.buildReply("result")
        if node is not None:
            iq.setQuerynode(node)

        query = iq.getQuery()
        for identity in self._caps.identities:
            query.addChild(node=identity.get_node())

        for feature in self._caps.features:
            query.addChild("feature", attrs={"var": feature})

        self._log.info("Respond with disco info")
        client.send_stanza(iq)
        raise NodeProcessed

    def _process_entity_caps(
        self, _client: Client, stanza: Presence, properties: PresenceProperties
    ) -> None:
        caps = stanza.getTag("c", namespace=Namespace.CAPS)
        if caps is None:
            return

        hash_algo = caps.getAttr("hash")
        if hash_algo != "sha-1":
            self._log.warning("Unsupported hashing algorithm used: %s", hash_algo)
            self._log.warning(stanza)
            return

        node = caps.getAttr("node")
        if not node:
            self._log.warning("node attribute missing")
            self._log.warning(stanza)
            return

        ver = caps.getAttr("ver")
        if not ver:
            self._log.warning("ver attribute missing")
            self._log.warning(stanza)
            return

        properties.entity_caps = EntityCapsData(hash=hash_algo, node=node, ver=ver)

    @property
    def caps(self) -> EntityCapsData | None:
        if self._caps is None:
            return None

        assert self._uri is not None
        assert self._caps_hash is not None
        return EntityCapsData(hash="sha-1", node=self._uri, ver=self._caps_hash)

    def set_caps(
        self, identities: list[DiscoIdentity], features: list[str], uri: str
    ) -> None:
        self._uri = uri
        self._caps = DiscoInfo(None, identities, features, [])
        self._caps_hash = compute_caps_hash(self._caps, compare=False)
        self._node = "%s#%s" % (uri, self._caps_hash)
