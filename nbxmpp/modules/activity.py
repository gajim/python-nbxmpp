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

from nbxmpp.protocol import NS_ACTIVITY
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import ActivityData
from nbxmpp.const import ACTIVITIES

log = logging.getLogger('nbxmpp.m.activity')


class Activity:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_activity,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_activity(self, _con, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_ACTIVITY:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        activity_node = item.getTag('activity', namespace=NS_ACTIVITY)
        if not activity_node.getChildren():
            log.info('Received activity: %s - no activity set', properties.jid)
            return

        activity, subactivity, text = None, None, None
        for child in activity_node.getChildren():
            name = child.getName()
            if name == 'text':
                text = child.getData()
            elif name in ACTIVITIES:
                activity = name
                subactivity = self._parse_sub_activity(child)

        if activity is None and activity_node.getPayload():
            log.warning('No valid activity value found')
            log.warning(stanza)
            raise NodeProcessed

        data = ActivityData(activity, subactivity, text)
        pubsub_event = properties.pubsub_event._replace(data=data)
        log.info('Received activity: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @staticmethod
    def _parse_sub_activity(activity):
        sub_activities = ACTIVITIES[activity.getName()]
        for sub in activity.getChildren():
            if sub.getName() in sub_activities:
                return sub.getName()

    def set_activity(self, data):
        item = Node('activity', {'xmlns': NS_ACTIVITY})
        if data is not None and data.activity:
            activity_node = item.addChild(data.activity)
            if data.subactivity:
                activity_node.addChild(data.subactivity)
            if data.text:
                item.addChild('text', payload=data.text)

        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_ACTIVITY, item, id_='current')
