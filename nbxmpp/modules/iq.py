# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import IqType
from nbxmpp.modules.base import BaseModule
from nbxmpp.structs import IqProperties
from nbxmpp.structs import PreparationHandler
from nbxmpp.util import error_factory

from .. import elements
from .. import exceptions

if TYPE_CHECKING:
    from nbxmpp.client import Client


class BaseIq(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            PreparationHandler(
                name="iq", callback=self._process_message_preparation, priority=10
            ),
        ]

    def _process_iq_preparation(
        self, _client: Client, element: elements.Iq, properties: IqProperties
    ) -> None:
        if jid := self._client.get_bound_jid():
            if element.get_from() is None:
                element.set_from(jid.new_as_bare())

        try:
            properties.type = IqType(element.get("type"))
        except ValueError:
            self._log.warning("Message with invalid type: %s", element.get("type"))
            self._log.warning(element)
            # TODO
            # self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise exceptions.NodeProcessed

        # Todo: Add more IQ validation

        properties.jid = element.get_from()
        properties.id = element.get("id")

        childs = element.iterchildren()
        for child in childs:
            if child.tag != "error":
                properties.payload = child
                break

        properties.query = element.get_query()

        if properties.type.is_error:
            properties.error = error_factory(element)
