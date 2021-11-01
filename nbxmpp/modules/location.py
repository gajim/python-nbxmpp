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

from typing import Any

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import E
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import LocationData
from nbxmpp.const import LOCATION_DATA
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.task import iq_request_task


class Location(BaseModule):

    _depends = {
        'publish': 'PubSub'
    }

    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_location,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_location(self,
                                 _client: types.Client,
                                 _stanza: types.Message,
                                 properties: Any):

        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.LOCATION:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        location_node = item.find_tag('geoloc', namespace=Namespace.LOCATION)
        if not location_node.get_children():
            self._log.info('Received location: %s - no location set',
                           properties.jid)
            return

        location_dict = {}
        for node in LOCATION_DATA:
            location_dict[node] = location_node.find_tag_text(node)

        data = LocationData(**location_dict)
        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received location: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_location(self, data):

        item = E('geoloc', namespaces=Namespace.LOCATION)
        if data is not None:
            data = data._asdict()
            for tag, value in data.items():
                if value is not None:
                    item.add_tag_text(tag, value)

        result = yield self.publish(Namespace.LOCATION, item, id_='current')

        yield finalize(result)
