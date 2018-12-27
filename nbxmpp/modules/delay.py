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

import logging

from nbxmpp.protocol import NS_DELAY2
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.date_and_time import parse_datetime

log = logging.getLogger('nbxmpp.m.delay')


class Delay:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_delay,
                          ns=NS_DELAY2,
                          priority=15),
            StanzaHandler(name='presence',
                          callback=self._process_presence_delay,
                          ns=NS_DELAY2,
                          priority=15)
        ]

    def _process_message_delay(self, _con, stanza, properties):
        if properties.is_muc_subject:
            # MUC Subjects can have a delay timestamp
            # to indicate when the user has set the subject,
            # the 'from' attr on these delays is the MUC server
            # but we treat it as user timestamp
            properties.user_timestamp = parse_delay(
                stanza, from_=properties.jid.getBare())

        else:
            jid = self._client.get_bound_jid().getDomain()
            timestamp = parse_delay(stanza, from_=jid)
            if timestamp is not None:
                properties.timestamp = timestamp

            properties.user_timestamp = parse_delay(stanza, not_from=[jid])

    @staticmethod
    def _process_presence_delay(_con, stanza, properties):
        properties.user_timestamp = parse_delay(stanza)


def parse_delay(stanza, epoch=True, convert='utc', from_=None, not_from=None):
    '''
    Returns the first valid delay timestamp that matches

    :param epoch:      Returns the timestamp as epoch

    :param convert:    Converts the timestamp to either utc or local

    :param from_:      Matches only delays that have the according
                       from attr set

    :param not_from:   Matches only delays that have the according
                       from attr not set
    '''
    delays = stanza.getTags('delay', namespace=NS_DELAY2)

    for delay in delays:
        stamp = delay.getAttr('stamp')
        if stamp is None:
            log.warning('Invalid timestamp received: %s', stamp)
            log.warning(stanza)
            continue

        delay_from = delay.getAttr('from')
        if from_ is not None:
            if delay_from != from_:
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
