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

from nbxmpp.protocol import NS_X_OOB
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import OOBData

log = logging.getLogger('nbxmpp.m.oob')


class OOB:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_oob,
                          ns=NS_X_OOB,
                          priority=15),
        ]

    def _process_message_oob(self, _client, stanza, properties):
        oob = stanza.getTag('x', namespace=NS_X_OOB)
        if oob is None:
            return

        url = oob.getTagData('url')
        if url is None:
            log.warning('OOB data without url')
            log.warning(stanza)
            return

        desc = oob.getTagData('desc')
        properties.oob = OOBData(url, desc)
