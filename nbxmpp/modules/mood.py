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

from nbxmpp.protocol import NS_MOOD
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import MoodData
from nbxmpp.const import MOODS

log = logging.getLogger('nbxmpp.m.mood')


class Mood:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_mood,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_mood(self, _con, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_MOOD:
            return

        item = properties.pubsub_event.item

        mood_node = item.getTag('mood', namespace=NS_MOOD)
        if not mood_node.getChildren():
            data = properties.pubsub_event._replace(empty=True)
        else:
            mood, text = None, None
            for child in mood_node.getChildren():
                name = child.getName().strip()
                if name == 'text':
                    text = child.getData()
                elif name in MOODS:
                    mood = name

            if mood is None and mood_node.getPayload():
                log.warning('No valid mood value found')
                log.warning(stanza)
                raise NodeProcessed

            data = MoodData(mood, text)
            data = properties.pubsub_event._replace(data=data)

        log.info('Received mood: %s - %s', properties.jid, data)
        properties.pubsub_event = data

    def set_mood(self, data):
        item = Node('mood', {'xmlns': NS_MOOD})
        if data is not None and data.mood:
            item.addChild(data.mood)

            if data.text:
                item.addChild('text', payload=data.text)

        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_MOOD, item, id_='current')
