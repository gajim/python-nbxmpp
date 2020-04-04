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
from nbxmpp.protocol import NS_DISCO_INFO
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import EntityCapsData
from nbxmpp.structs import DiscoInfo
from nbxmpp.util import compute_caps_hash
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
            StanzaHandler(name='iq',
                          callback=self._process_disco_info,
                          ns=NS_DISCO_INFO,
                          priority=20),
        ]

        self._identities = []
        self._features = []

        self._uri = None
        self._node = None
        self._caps = None
        self._caps_hash = None

    def _process_disco_info(self, client, stanza, _properties):
        if self._caps is None:
            return

        if self._node != stanza.getQuerynode():
            return

        iq = stanza.buildReply('result')
        query = iq.getQuery()
        for identity in self._caps.identities:
            query.addChild(node=identity.get_node())

        for feature in self._caps.features:
            query.addChild('feature', attrs={'var': feature})

        self._log.info('Respond with entity caps')
        client.send_stanza(iq)
        raise NodeProcessed

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

    @property
    def caps(self):
        if self._caps is None:
            return None
        return EntityCapsData(hash='sha-1',
                              node=self._uri,
                              ver=self._caps_hash)

    def set_caps(self, identities, features, uri):
        self._uri = uri
        self._caps = DiscoInfo(None, identities, features, [])
        self._caps_hash = compute_caps_hash(self._caps, compare=False)
        self._node = '%s#%s' % (uri, self._caps_hash)
