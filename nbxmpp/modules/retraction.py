from __future__ import annotations

from typing import TYPE_CHECKING

import datetime as dt

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
                callback=self._process_message_retraction,
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=20,
            ),
        ]

    def _process_message_retraction(
        self, _client: Client, stanza: Node, properties: MessageProperties
    ) -> None:

        retract, is_tombstone = _get_retract_element(stanza, properties)
        if retract is None:
            return

        retract_id = retract.getAttr("id")
        if not retract_id:
            self._log.warning("<retract> without id")
            self._log.warning(stanza)
            return

        timestamp = _parse_retraction_timestamp(retract, is_tombstone, properties)

        properties.retraction = RetractionData(
            id=retract_id, is_tombstone=is_tombstone, timestamp=timestamp
        )


def _get_retract_element(
    element: Node, properties: MessageProperties
) -> tuple[Node | None, bool]:
    """
    returns a tuple
        Node and a boolean value which signals if it is a tombstone
    """

    retract = element.getTag("retract", namespace=Namespace.MESSAGE_RETRACT_1)
    if retract is not None:
        return retract, False

    if not properties.is_mam_message:
        return None, False

    retracted = element.getTag("retracted", namespace=Namespace.MESSAGE_RETRACT_1)
    if retracted is not None:
        return retracted, True

    return None, False


def _parse_retraction_timestamp(
    retract: Node, is_tombstone: bool, properties: MessageProperties
) -> dt.datetime:

    if is_tombstone:
        stamp_attr = retract.getAttr("stamp")
        stamp = parse_datetime(stamp_attr, check_utc=True, convert="utc")
        if stamp is not None:
            assert isinstance(stamp, dt.datetime)
            return stamp

    if properties.is_mam_message:
        assert properties.mam is not None
        stamp = properties.mam.timestamp
    else:
        stamp = properties.timestamp

    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
