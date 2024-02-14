from nbxmpp.modules.date_and_time import parse_datetime

from nbxmpp import Namespace, Node
from nbxmpp.structs import StanzaHandler, MessageProperties, RetractionData

from nbxmpp.modules.base import BaseModule


class Retraction(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name='message',
                callback=self._process_message,
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=20,
            ),
            StanzaHandler(
                name='message',
                callback=self._process_message_retracted_tombstone,
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=20,
            ),
        ]

    def _process_message(
        self, _client, stanza: Node, properties: MessageProperties
    ) -> None:
        retraction = stanza.getTag(
            'retract', namespace=Namespace.MESSAGE_RETRACT_1
        )

        if retraction is None:
            return

        retracted_id = retraction.getAttr('id')

        if retracted_id is None:
            self._log.warning('<retract> without retracted message id')
            return

        properties.retraction = RetractionData(
            id=retracted_id, is_tombstone=False, timestamp=None
        )

    def _process_message_retracted_tombstone(
        self, _client, stanza: Node, properties: MessageProperties
    ) -> None:
        if not properties.is_mam_message:
            return

        retracted = stanza.getTag(
            'retracted', namespace=Namespace.MESSAGE_RETRACT_1
        )

        if retracted is None:
            return

        retracted_stamp = retracted.getAttr('stamp')

        properties.retraction = RetractionData(
            id=None,
            is_tombstone=True,
            timestamp=parse_datetime(
                retracted_stamp, check_utc=True, convert='utc', epoch=True
            ),
        )
