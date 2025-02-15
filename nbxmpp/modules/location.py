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

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.const import LOCATION_DATA
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import Node
from nbxmpp.structs import LocationData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Location(BaseModule):

    _depends = {
        'publish': 'PubSub'
    }

    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_location,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_location(self, _client: Client, _stanza: Message, properties: MessageProperties) -> None:
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.LOCATION:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        location_node = item.getTag('geoloc', namespace=Namespace.LOCATION)
        if not location_node.getChildren():
            self._log.info('Received location: %s - no location set',
                           properties.jid)
            return

        location_dict = {}
        for node in LOCATION_DATA:
            location_dict[node] = location_node.getTagData(node)
        data = LocationData(**location_dict)
        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received location: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_location(self, data: LocationData):
        task = yield

        item = Node('geoloc', {'xmlns': Namespace.LOCATION})
        if data is not None:
            data = data._asdict()
            for tag, value in data.items():
                if value is not None:
                    item.addChild(tag, payload=value)

        result = yield self.publish(Namespace.LOCATION, item, id_='current')

        yield finalize(task, result)
