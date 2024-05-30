# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

# XEP-0425: Message Moderation
from __future__ import annotations

from typing import TYPE_CHECKING

import datetime as dt

from nbxmpp import JID
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.simplexml import Node
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import ModerationData
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Moderation(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_moderation_0_message,
                typ="groupchat",
                ns=Namespace.FASTEN,
                priority=20,
            ),
            StanzaHandler(
                name="message",
                callback=self._process_moderation_0_tombstone_message,
                typ="groupchat",
                ns=Namespace.MESSAGE_MODERATE,
                priority=20,
            ),
            StanzaHandler(
                name="message",
                callback=self._process_moderation_1_message,
                typ="groupchat",
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=20,
            ),
        ]

    @iq_request_task
    def send_moderation_request(
        self,
        namespace: str,
        muc_jid: JID,
        stanza_id: str,
        reason: str | None = None,
    ):
        _task = yield

        if namespace == Namespace.MESSAGE_MODERATE:
            response = yield _make_moderation_request_0(muc_jid, stanza_id, reason)
        else:
            response = yield _make_moderation_request_1(muc_jid, stanza_id, reason)

        yield process_response(response)

    def _process_moderation_1_message(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:

        retract, is_tombstone = _get_retract_element(stanza, properties)
        if retract is None:
            return

        stamp = _parse_moderation_timestamp(retract, is_tombstone, properties)

        moderated = retract.getTag("moderated", namespace=Namespace.MESSAGE_MODERATE_1)
        if moderated is None:
            return

        try:
            by = _parse_by_attr(moderated)
        except ValueError as error:
            self._log.warning("Unable to determine by attribute: %s", error)
            by = None

        occupant_id = moderated.getTagAttr(
            "occupant-id", "id", namespace=Namespace.OCCUPANT_ID
        )

        if is_tombstone:
            stanza_id = properties.mam.id
        else:
            stanza_id = retract.getAttr("id")

        if stanza_id is None:
            self._log.warning("Unable to determine stanza-id")
            self._log.warning(stanza)
            raise NodeProcessed

        properties.moderation = ModerationData(
            stanza_id=stanza_id,
            by=by,
            reason=retract.getTagData("reason"),
            stamp=stamp,
            is_tombstone=is_tombstone,
            occupant_id=occupant_id,
        )

    def _process_moderation_0_tombstone_message(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:

        if not properties.is_mam_message:
            return

        moderated = stanza.getTag("moderated", namespace=Namespace.MESSAGE_MODERATE)
        if moderated is None:
            return

        properties.moderation = self._parse_moderated_0(
            moderated, properties, properties.mam.id
        )

    def _process_moderation_0_message(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:

        if not properties.jid.is_bare:
            return

        apply_to = stanza.getTag("apply-to", namespace=Namespace.FASTEN)
        if apply_to is None:
            return

        moderated = apply_to.getTag("moderated", namespace=Namespace.MESSAGE_MODERATE)
        if moderated is None:
            return

        stanza_id = apply_to.getAttr("id")
        if stanza_id is None:
            self._log.warning("apply-to element without stanza-id")
            self._log.warning(stanza)
            raise NodeProcessed

        properties.moderation = self._parse_moderated_0(
            moderated, properties, stanza_id
        )

    def _parse_moderated_0(
        self, moderated: Node, properties: MessageProperties, stanza_id: str
    ) -> ModerationData | None:

        retract, is_tombstone = _get_retract_element(moderated, properties)
        if retract is None:
            self._log.warning("Failed to find <retract/ed> element")
            return None

        try:
            by = _parse_by_attr(moderated)
        except ValueError as error:
            self._log.warning(error)
            by = None

        stamp = _parse_moderation_timestamp(retract, is_tombstone, properties)

        occupant_id = moderated.getTagAttr(
            "occupant-id", "id", namespace=Namespace.OCCUPANT_ID
        )

        return ModerationData(
            stanza_id=stanza_id,
            by=by,
            occupant_id=occupant_id,
            reason=moderated.getTagData("reason"),
            stamp=stamp,
            is_tombstone=is_tombstone,
        )


def _get_retract_element(
    element: Node, properties: MessageProperties
) -> tuple[Node | None, bool]:
    """
    returns a tuple
        Node and a boolean value which signals if it is a tombstone
    """

    retract = element.getTag("retract", namespace=Namespace.MESSAGE_RETRACT)
    if retract is not None:
        return retract, False

    retract = element.getTag("retract", namespace=Namespace.MESSAGE_RETRACT_1)
    if retract is not None:
        return retract, False

    if not properties.is_mam_message:
        return None, False

    retracted = element.getTag("retracted", namespace=Namespace.MESSAGE_RETRACT)
    if retracted is not None:
        return retracted, True

    retracted = element.getTag("retracted", namespace=Namespace.MESSAGE_RETRACT_1)
    if retracted is not None:
        return retracted, True

    return None, False


def _parse_by_attr(moderated: Node) -> JID | None:
    by_attr = moderated.getAttr("by")
    if by_attr is None:
        return None

    try:
        return JID.from_string(by_attr)
    except Exception as error:
        raise ValueError("Invalid JID: %s, %s" % (by_attr, error))


def _parse_moderation_timestamp(
    retract: Node, is_tombstone: bool, properties: MessageProperties
) -> dt.datetime:

    if is_tombstone:
        stamp_attr = retract.getAttr("stamp")
        stamp = parse_datetime(stamp_attr, check_utc=True, convert="utc")
        if stamp is not None:
            assert isinstance(stamp, dt.datetime)
            return stamp

    if properties.is_mam_message:
        stamp = properties.mam.timestamp
    else:
        stamp = properties.timestamp

    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc)


def _make_moderation_request_0(muc_jid: JID, stanza_id: str, reason: str | None) -> Iq:
    iq = Iq("set", Namespace.FASTEN, to=muc_jid)
    query = iq.setQuery(name="apply-to")
    query.setAttr("id", stanza_id)
    moderate = query.addChild(name="moderate", namespace=Namespace.MESSAGE_MODERATE)
    moderate.addChild(name="retract", namespace=Namespace.MESSAGE_RETRACT)
    if reason is not None:
        moderate.addChild(name="reason", payload=[reason])
    return iq


def _make_moderation_request_1(muc_jid: JID, stanza_id: str, reason: str | None) -> Iq:
    iq = Iq("set", Namespace.MESSAGE_MODERATE_1, to=muc_jid)
    query = iq.setQuery(name="moderate")
    query.setAttr("id", stanza_id)
    query.addChild(name="retract", namespace=Namespace.MESSAGE_RETRACT_1)
    if reason is not None:
        query.addChild(name="reason", payload=[reason])
    return iq
