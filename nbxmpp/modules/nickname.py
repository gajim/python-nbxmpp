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
from nbxmpp.util import StanzaHandler

log = logging.getLogger('nbxmpp.m.nickname')


class Nickname:
    def __init__(self, client):
        self._client = client
        self.handlers = [
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
            if properties.type in (None, 'unavailable'):
                return
            properties.nickname = self._parse_nickname(stanza)

    @staticmethod
    def _parse_nickname(stanza):
        nickname = stanza.getTagData('nick', namespace=NS_NICK)
        if not nickname:
            return
        return nickname
