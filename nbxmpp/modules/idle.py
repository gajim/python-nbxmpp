# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Presence
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Idle(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="presence",
                callback=self._process_idle,
                ns=Namespace.IDLE,
                priority=15,
            )
        ]

    def _process_idle(
        self, _client: Client, stanza: Presence, properties: PresenceProperties
    ) -> None:
        idle_tag = stanza.getTag("idle", namespace=Namespace.IDLE)
        if idle_tag is None:
            return

        since = idle_tag.getAttr("since")
        if since is None:
            self._log.warning("No since attr in idle node")
            self._log.warning(stanza)
            return

        timestamp = parse_datetime(since, convert="utc", epoch=True)
        if timestamp is None:
            self._log.warning("Invalid timestamp received: %s", since)
            self._log.warning(stanza)

        properties.idle_timestamp = timestamp
