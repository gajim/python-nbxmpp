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

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import EntityCapsData
from nbxmpp.util import compute_caps_hash
from nbxmpp.modules.base import BaseModule


class EntityCaps(BaseModule):
    def __init__(self, client: types.Client):
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

        self._uri = None
        self._disco_info = None
        self._caps_hash = None

    def _process_disco_info(self,
                            client: types.Client,
                            iq: types.Iq,
                            _properties: Any):

        if self._disco_info is None:
            return

        node = iq.find_tag_attr('query', 'node', Namespace.DISCO_INFO) 
        if node is not None:
            if self._disco_info.get('node') != node:
                return

        result = iq.make_result()
        result.append(self._disco_info)

        self._log.info('Respond with disco info')
        client.send_stanza(result)
        raise NodeProcessed

    def _process_entity_caps(self,
                             _client: types.Client,
                             presence: types.Presence,
                             properties: Any):

        caps = presence.find_tag('c', namespace=Namespace.CAPS)
        if caps is None:
            return

        hash_algo = caps.get('hash')
        if hash_algo != 'sha-1':
            self._log.warning('Unsupported hashing algorithm used: %s',
                              hash_algo)
            self._log.warning(presence)
            return

        node = caps.get('node')
        if not node:
            self._log.warning('node attribute missing')
            self._log.warning(presence)
            return

        ver = caps.get('ver')
        if not ver:
            self._log.warning('ver attribute missing')
            self._log.warning(presence)
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

    def set_caps(self, disco_info: types.DiscoInfo, uri: str):

        self._uri = uri
        self._disco_info: types.DiscoInfo = disco_info
        self._caps_hash = compute_caps_hash(self._disco_info, compare=False)
        self._node = '%s#%s' % (uri, self._caps_hash)
