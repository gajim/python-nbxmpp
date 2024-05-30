# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

import datetime as dt
import logging

from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import Presence
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client

log = logging.getLogger("nbxmpp.m.delay")


class Delay(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message_delay,
                ns=Namespace.DELAY2,
                priority=15,
            ),
            StanzaHandler(
                name="presence",
                callback=self._process_presence_delay,
                ns=Namespace.DELAY2,
                priority=15,
            ),
        ]

    def _process_message_delay(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        # Determine if delay is from the server
        # Some servers use the bare jid, others the domain
        our_jid = self._client.get_bound_jid()
        jids = [our_jid.bare, our_jid.domain]

        if properties.from_muc:
            muc_jid = properties.jid
            jids += [muc_jid.bare, muc_jid.domain]

        if properties.is_muc_subject:
            # MUC Subjects can have a delay timestamp
            # to indicate when the user has set the subject,
            # the 'from' attr on these delays is the MUC server
            # but we treat it as user timestamp
            properties.user_timestamp = parse_delay(stanza, from_=jids)

        else:
            server_delay = parse_delay(stanza, from_=jids)
            if server_delay is not None:
                properties.has_server_delay = True
                properties.timestamp = server_delay

            properties.user_timestamp = parse_delay(stanza, not_from=jids)

    @staticmethod
    def _process_presence_delay(
        _client: Client, stanza: Presence, properties: PresenceProperties
    ) -> None:
        properties.user_timestamp = parse_delay(stanza)


def parse_delay(
    stanza: Message | Presence,
    epoch: bool = True,
    convert: str = "utc",
    from_: list[str] | None = None,
    not_from: list[str] | None = None,
) -> dt.datetime | float | None:
    """
    Returns the first valid delay timestamp that matches

    :param epoch:      Returns the timestamp as epoch

    :param convert:    Converts the timestamp to either utc or local

    :param from_:      Matches only delays that have the according
                       from attr set

    :param not_from:   Matches only delays that have the according
                       from attr not set
    """
    delays = stanza.getTags("delay", namespace=Namespace.DELAY2)

    for delay in delays:
        stamp = delay.getAttr("stamp")
        if stamp is None:
            log.warning("Invalid timestamp received: %s", stamp)
            log.warning(stanza)
            continue

        delay_from = delay.getAttr("from")
        if from_ is not None:
            if delay_from not in from_:
                continue
        if not_from is not None:
            if delay_from in not_from:
                continue

        timestamp = parse_datetime(stamp, check_utc=True, epoch=epoch, convert=convert)
        if timestamp is None:
            log.warning("Invalid timestamp received: %s", stamp)
            log.warning(stanza)
            continue

        return timestamp
