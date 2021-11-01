# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import Union

import logging
from datetime import datetime

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.base import BaseModule

log = logging.getLogger('nbxmpp.m.delay')


class Delay(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_delay,
                          ns=Namespace.DELAY2,
                          priority=15),
            StanzaHandler(name='presence',
                          callback=self._process_presence_delay,
                          ns=Namespace.DELAY2,
                          priority=15)
        ]

    def _process_message_delay(self,
                               _client: types.Client,
                               message: types.Message,
                               properties: Any):

        if properties.is_muc_subject:
            # MUC Subjects can have a delay timestamp
            # to indicate when the user has set the subject,
            # the 'from' attr on these delays is the MUC server
            # but we treat it as user timestamp
            jids = [properties.jid.bare,
                    properties.jid.domain]

            properties.user_timestamp = parse_delay(message, from_=jids)

        else:
            if properties.from_muc:
                # Some servers use the MUC JID, others the domain
                jids = [properties.jid.bare,
                        properties.jid.domain]
            else:
                jids = [self._client.get_bound_jid().domain]

            server_delay = parse_delay(message, from_=jids)
            if server_delay is not None:
                properties.has_server_delay = True
                properties.timestamp = server_delay

            properties.user_timestamp = parse_delay(message, not_from=jids)

    @staticmethod
    def _process_presence_delay(_client: types.Client,
                                presence: types.Presence,
                                properties: Any):
        properties.user_timestamp = parse_delay(presence)


def parse_delay(stanza: types.Stanza,
                epoch: bool = True,
                convert: Optional[str] = 'utc',
                from_: Optional[list[str]] = None,
                not_from: Optional[list[str]] = None) -> Optional[Union[datetime, float]]:

    '''
    Returns the first valid delay timestamp that matches

    :param epoch:      Returns the timestamp as epoch

    :param convert:    Converts the timestamp to either utc or local

    :param from_:      Matches only delays that have the according
                       from attr set

    :param not_from:   Matches only delays that have the according
                       from attr not set
    '''
    delays = stanza.find_tags('delay', namespace=Namespace.DELAY2)

    for delay in delays:
        stamp = delay.get('stamp')
        if stamp is None:
            log.warning('Invalid timestamp received: %s', stamp)
            log.warning(stanza)
            continue

        delay_from = delay.get('from')
        if from_ is not None:
            if delay_from not in from_:
                continue
        if not_from is not None:
            if delay_from in not_from:
                continue

        timestamp = parse_datetime(stamp, check_utc=True,
                                   epoch=epoch, convert=convert)
        if timestamp is None:
            log.warning('Invalid timestamp received: %s', stamp)
            log.warning(stanza)
            continue

        return timestamp
