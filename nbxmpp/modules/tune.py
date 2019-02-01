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

from nbxmpp.protocol import NS_TUNE
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import Node
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import TuneData

log = logging.getLogger('nbxmpp.m.tune')


class Tune:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_tune,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_tune(self, _con, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_TUNE:
            return

        item = properties.pubsub_event.item

        tune_node = item.getTag('tune', namespace=NS_TUNE)
        if not tune_node.getChildren():
            data = TuneData()
        else:
            artist = tune_node.getTagData('artist')
            length = tune_node.getTagData('length')
            rating = tune_node.getTagData('rating')
            source = tune_node.getTagData('source')
            title = tune_node.getTagData('title')
            track = tune_node.getTagData('track')
            uri = tune_node.getTagData('uri')

            data = TuneData(artist, length, rating, source, title, track, uri)

        log.info('Received tune: %s - %s', properties.jid, data)
        properties.pubsub_event = properties.pubsub_event._replace(data=data)

    def set_tune(self, data):
        item = Node('tune', {'xmlns': NS_TUNE})
        if data is None:
            return item

        if data.artist:
            item.addChild('artist', payload=data.artist)
        if data.length:
            item.addChild('length', payload=data.length)
        if data.rating:
            item.addChild('length', payload=data.rating)
        if data.source:
            item.addChild('source', payload=data.source)
        if data.title:
            item.addChild('title', payload=data.title)
        if data.track:
            item.addChild('track', payload=data.track)
        if data.uri:
            item.addChild('track', payload=data.uri)

        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_TUNE, item, id_='current')
