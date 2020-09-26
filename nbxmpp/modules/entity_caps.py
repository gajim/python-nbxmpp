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

from nbxmpp.namespaces import Namespace
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
                          ns=Namespace.CAPS,
                          priority=15),
            StanzaHandler(name='iq',
                          callback=self._process_disco_info,
                          typ='get',
                          ns=Namespace.DISCO_INFO,
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

        node = stanza.getQuerynode()
        if node is not None:
            if self._node != node:
                return

        iq = stanza.buildReply('result')
        if node is not None:
            iq.setQuerynode(node)

        query = iq.getQuery()
        for identity in self._caps.identities:
            query.addChild(node=identity.get_node())

        for feature in self._caps.features:
            query.addChild('feature', attrs={'var': feature})

        self._log.info('Respond with disco info')
        client.send_stanza(iq)
        raise NodeProcessed

    def _process_entity_caps(self, _client, stanza, properties):
        caps = stanza.getTag('c', namespace=Namespace.CAPS)
        if caps is None:
            return

        hash_algo = caps.getAttr('hash')
        if hash_algo != 'sha-1':
            self._log.warning('Unsupported hashing algorithm used: %s',
                              hash_algo)
            self._log.warning(stanza)
            return

        node = caps.getAttr('node')
        if not node:
            self._log.warning('node attribute missing')
            self._log.warning(stanza)
            return

        ver = caps.getAttr('ver')
        if not ver:
            self._log.warning('ver attribute missing')
            self._log.warning(stanza)
            return

        properties.entity_caps = EntityCapsData(
            hash=hash_algo,
            node=node,
            ver=ver)

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
