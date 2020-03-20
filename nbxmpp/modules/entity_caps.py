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

from nbxmpp.protocol import NS_CAPS
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import EntityCapsData
from nbxmpp.modules.base import BaseModule


class EntityCaps(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_entity_caps,
                          ns=NS_CAPS,
                          priority=15),
        ]

    @staticmethod
    def _process_entity_caps(_client, stanza, properties):
        caps = stanza.getTag('c', namespace=NS_CAPS)
        if caps is None:
            properties.entity_caps = EntityCapsData()
            return

        properties.entity_caps = EntityCapsData(
            hash=caps.getAttr('hash'),
            node=caps.getAttr('node'),
            ver=caps.getAttr('ver')
        )
