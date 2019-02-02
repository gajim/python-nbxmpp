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

from nbxmpp.protocol import NS_NICK
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import Node
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import PresenceType

log = logging.getLogger('nbxmpp.m.nickname')


class Nickname:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_nickname,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_nickname,
                          ns=NS_NICK,
                          priority=40),
            StanzaHandler(name='presence',
                          callback=self._process_nickname,
                          ns=NS_NICK,
                          priority=40),
        ]

    def _process_nickname(self, _con, stanza, properties):
        if stanza.getName() == 'message':
            properties.nickname = self._parse_nickname(stanza)

        elif stanza.getName() == 'presence':
            # the nickname MUST NOT be included in presence broadcasts
            # (i.e., <presence/> stanzas with no 'type' attribute or
            # of type "unavailable").
            if properties.type in (PresenceType.AVAILABLE,
                                   PresenceType.UNAVAILABLE):
                return
            properties.nickname = self._parse_nickname(stanza)

    def _process_pubsub_nickname(self, _con, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_NICK:
            return

        nick = self._parse_nickname(properties.pubsub_event.item)
        if nick is None:
            log.info('Received nickname: %s - no nickname set', properties.jid)
        else:
            log.info('Received nickname: %s - %s', properties.jid, nick)

        properties.pubsub_event = properties.pubsub_event._replace(data=nick)

    @staticmethod
    def _parse_nickname(stanza):
        nickname = stanza.getTag('nick', namespace=NS_NICK)
        if nickname is None:
            return
        return nickname.getData() or None

    def set_nickname(self, nickname):
        item = Node('nick', {'xmlns': NS_NICK})
        if nickname is not None:
            item.addData(nickname)
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_NICK, item, id_='current')
