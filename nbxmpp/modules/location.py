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

import logging

from nbxmpp.protocol import NS_LOCATION
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import Node
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import LocationData
from nbxmpp.const import LOCATION_DATA

log = logging.getLogger('nbxmpp.m.location')


class Location:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_location,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_location(self, _con, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_LOCATION:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        location_node = item.getTag('geoloc', namespace=NS_LOCATION)
        if not location_node.getChildren():
            log.info('Received location: %s - no location set', properties.jid)
            return

        location_dict = {}
        for node in LOCATION_DATA:
            location_dict[node] = location_node.getTagData(node)
        data = LocationData(**location_dict)
        pubsub_event = properties.pubsub_event._replace(data=data)
        log.info('Received location: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    def set_location(self, data):
        item = Node('geoloc', {'xmlns': NS_LOCATION})
        if data is None:
            return item

        data = data._asdict()
        for tag, value in data:
            if value is not None:
                item.addChild(tag, payload=value)

        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_LOCATION, item, id_='current')
