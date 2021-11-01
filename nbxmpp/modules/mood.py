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
from typing import Optional

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import E
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import MoodData
from nbxmpp.const import MOODS
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.task import iq_request_task


class Mood(BaseModule):

    _depends = {
        'publish': 'PubSub'
    }

    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_mood,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_mood(self,
                             _client: types.Client,
                             stanza: types.Message,
                             properties: Any):

        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.MOOD:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        mood_node = item.find_tag('mood', namespace=Namespace.MOOD)
        if not mood_node.get_children():
            self._log.info('Received mood: %s - removed mood', properties.jid)
            return

        mood, text = None, None
        for child in mood_node.get_children():
            name = child.localname.strip()
            if name == 'text':
                text = child.text or ''
            elif name in MOODS:
                mood = name

        if mood is None and mood_node.get_children():
            self._log.warning('No valid mood value found')
            self._log.warning(stanza)
            raise NodeProcessed

        data = MoodData(mood, text)
        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received mood: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_mood(self, data: Optional[MoodData]):

        item = E('mood', namespace=Namespace.MOOD)
        if data is not None and data.mood:
            item.add_tag(data.mood)

            if data.text:
                item.add_tag_text('text', data.text)

        result = yield self.publish(Namespace.MOOD, item, id_='current')

        yield finalize(result)
