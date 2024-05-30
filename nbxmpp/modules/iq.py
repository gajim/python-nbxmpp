# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import IqType
from nbxmpp.modules.base import BaseModule
from nbxmpp.protocol import ERR_BAD_REQUEST
from nbxmpp.protocol import Error as ErrorStanza
from nbxmpp.protocol import Iq
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import error_factory

if TYPE_CHECKING:
    from nbxmpp.client import Client


class BaseIq(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name="iq", callback=self._process_iq_base, priority=10),
        ]

    def _process_iq_base(
        self, _client: Client, stanza: Iq, properties: IqProperties
    ) -> None:
        try:
            properties.type = IqType(stanza.getType())
        except ValueError:
            self._log.warning("Message with invalid type: %s", stanza.getType())
            self._log.warning(stanza)
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        properties.jid = stanza.getFrom()
        properties.id = stanza.getID()

        childs = stanza.getChildren()
        for child in childs:
            if child.getName() != "error":
                properties.payload = child
                break

        properties.query = stanza.getQuery()

        if properties.type.is_error:
            properties.error = error_factory(stanza)
