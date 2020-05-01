# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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

import time
import logging

from nbxmpp.protocol import Iq
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import ErrorNode
from nbxmpp.protocol import ERR_ITEM_NOT_FOUND
from nbxmpp.protocol import NodeProcessed
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.base import BaseModule
from nbxmpp.structs import DiscoIdentity
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import DiscoItems
from nbxmpp.structs import DiscoItem
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error


log = logging.getLogger('nbxmpp.m.discovery')


class Discovery(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_disco_info,
                          typ='get',
                          ns=Namespace.DISCO_INFO,
                          priority=90),
        ]

    @staticmethod
    def _process_disco_info(client, stanza, properties):
        iq = stanza.buildReply('error')
        iq.addChild(node=ErrorNode(ERR_ITEM_NOT_FOUND))
        client.send_stanza(iq)
        raise NodeProcessed

    @call_on_response('_disco_info_received')
    def disco_info(self, jid, node=None):
        self._log.info('Disco info: %s, node: %s', jid, node)
        return get_disco_request(Namespace.DISCO_INFO, jid, node)

    @callback
    def _disco_info_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return parse_disco_info(stanza)

    @call_on_response('_disco_items_received')
    def disco_items(self, jid, node=None):
        self._log.info('Disco items: %s, node: %s', jid, node)
        return get_disco_request(Namespace.DISCO_ITEMS, jid, node)

    @callback
    def _disco_items_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return parse_disco_items(stanza)


def parse_disco_info(stanza, timestamp=None):
    idenities = []
    features = []
    dataforms = []

    if timestamp is None:
        timestamp = time.time()

    query = stanza.getQuery()
    for node in query.getTags('identity'):
        attrs = node.getAttrs()
        try:
            idenities.append(
                DiscoIdentity(category=attrs['category'],
                              type=attrs['type'],
                              name=attrs.get('name'),
                              lang=attrs.get('xml:lang')))
        except Exception:
            return raise_error(log.warning, stanza, 'stanza-malformed')

    for node in query.getTags('feature'):
        try:
            features.append(node.getAttr('var'))
        except Exception:
            return raise_error(log.warning, stanza, 'stanza-malformed')

    for node in query.getTags('x', namespace=Namespace.DATA):
        dataforms.append(extend_form(node))

    return DiscoInfo(stanza=stanza,
                     identities=idenities,
                     features=features,
                     dataforms=dataforms,
                     timestamp=timestamp)


def parse_disco_items(stanza):
    items = []

    query = stanza.getQuery()
    for node in query.getTags('item'):
        attrs = node.getAttrs()
        try:
            items.append(
                DiscoItem(jid=attrs['jid'],
                          name=attrs.get('name'),
                          node=attrs.get('node')))
        except Exception:
            return raise_error(log.warning, stanza, 'stanza-malformed')

    return DiscoItems(jid=stanza.getFrom(),
                      node=query.getAttr('node'),
                      items=items)


def get_disco_request(namespace, jid, node=None):
    iq = Iq('get', to=jid, queryNS=namespace)
    if node:
        iq.getQuery().setAttr('node', node)
    return iq
