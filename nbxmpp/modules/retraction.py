from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp import Namespace
from nbxmpp import Node
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import RetractionData
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Retraction(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message,
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=20,
            ),
            StanzaHandler(
                name="message",
                callback=self._process_message_retracted_tombstone,
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=20,
            ),
        ]

    def _process_message(
        self, _client: Client, stanza: Node, properties: MessageProperties
    ) -> None:
        retraction = stanza.getTag("retract", namespace=Namespace.MESSAGE_RETRACT_1)

        if retraction is None:
            return

        retracted_id = retraction.getAttr("id")

        if retracted_id is None:
            self._log.warning("<retract> without id")
            return

        properties.retraction = RetractionData(
            id=retracted_id, is_tombstone=False, timestamp=None
        )

    def _process_message_retracted_tombstone(
        self, _client: Client, stanza: Node, properties: MessageProperties
    ) -> None:
        if not properties.is_mam_message:
            return

        retracted = stanza.getTag("retracted", namespace=Namespace.MESSAGE_RETRACT_1)

        if retracted is None:
            return

        retracted_id = retracted.getAttr("id")

        if retracted_id is None:
            self._log.warning("<retracted> without id")
            return

        retracted_stamp = retracted.getAttr("stamp")

        properties.retraction = RetractionData(
            id=retracted_id,
            is_tombstone=True,
            timestamp=parse_datetime(
                retracted_stamp, check_utc=True, convert="utc", epoch=True
            ),
        )
