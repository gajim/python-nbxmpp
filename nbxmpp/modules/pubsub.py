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

from nbxmpp.protocol import NS_PUBSUB
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import NS_PUBSUB_PUBLISH_OPTIONS
from nbxmpp.protocol import NS_DATA
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PubSubEventData
from nbxmpp.structs import CommonResult
from nbxmpp.util import call_on_response
from nbxmpp.util import callback


log = logging.getLogger('nbxmpp.m.pubsub')


class PubSub:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_base,
                          ns=NS_PUBSUB_EVENT,
                          priority=15),
        ]

    def _process_pubsub_base(self, _con, stanza, properties):
        properties.pubsub = True
        event = stanza.getTag('event', namespace=NS_PUBSUB_EVENT)

        delete = event.getTag('delete')
        if delete is not None:
            node = delete.getAttr('node')
            properties.pubsub_event = PubSubEventData(
                node, empty=True, deleted=True)
            return

        retract = event.getTag('retract')
        if retract is not None:
            node = retract.getAttr('node')
            item = retract.getTag('item')
            id_ = item.getAttr('id')
            properties.pubsub_event = PubSubEventData(
                node, id_, item, retracted=True)
            return

        items = event.getTag('items')
        if items is not None:
            if len(items.getChildren()) != 1:
                log.warning('PubSub event with more than one item')
                log.warning(stanza)
            node = items.getAttr('node')
            item = items.getTag('item')
            if item is None:
                return
            id_ = item.getAttr('id')
            properties.pubsub_event = PubSubEventData(node, id_, item)

    @call_on_response('_default_response')
    def publish(self, jid, node, item, id_=None, options=None):
        query = Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=NS_PUBSUB)
        publish = pubsub.addChild('publish', {'node': node})
        attrs = {}
        if id_ is not None:
            attrs = {'id': id_}
        publish.addChild('item', attrs, [item])
        if options:
            publish = pubsub.addChild('publish-options')
            publish.addChild(node=options)
        return query

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            return CommonResult(jid=stanza.getFrom(),
                                error=stanza.getError())
        return CommonResult(jid=stanza.getFrom())


def get_pubsub_request(jid, node, id_=None, max_items=None):
    query = Iq('get', to=jid)
    pubsub = query.addChild('pubsub', namespace=NS_PUBSUB)
    items = pubsub.addChild('items', {'node': node})
    if max_items is not None:
        items.setAttr('max_items', max_items)
    if id_ is not None:
        items.addChild('item', {'id': id_})
    return query


def get_pubsub_item(stanza):
    pubsub_node = stanza.getTag('pubsub')
    items_node = pubsub_node.getTag('items')
    return items_node.getTag('item')


def get_bookmark_publish_options():
    # TODO: Make generic
    options = Node(NS_DATA + ' x',
                   attrs={'type': 'submit'})
    field = options.addChild('field',
                             attrs={'var': 'FORM_TYPE', 'type': 'hidden'})
    field.setTagData('value', NS_PUBSUB_PUBLISH_OPTIONS)
    field = options.addChild('field', attrs={'var': 'pubsub#access_model'})
    field.setTagData('value', 'whitelist')
    return options
