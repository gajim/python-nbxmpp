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
from typing import cast

from nbxmpp import types
from nbxmpp.builder import E
from nbxmpp.elements import Base
from nbxmpp.lookups import register_class_lookup
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import ActivityData
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task


class UserActivity(BaseModule):

    _depends = {
        'publish': 'PubSub'
    }

    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_activity,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_activity(self,
                                 _client: types.Client,
                                 stanza: types.Message,
                                 properties: Any):

        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.ACTIVITY:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        activity = cast(Optional[Activity],
                        item.find_tag('activity', namespace=Namespace.ACTIVITY))
        if activity is None:
            self._log.info('Received activity: %s - no activity set',
                           properties.jid)
            return

        general, specific = activity.get_activity()
        if general is None:
            self._log.warning('No activity value found')
            self._log.warning(stanza)
            raise NodeProcessed

        text = activity.get_text()

        data = ActivityData(general, specific, text)
        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received activity: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_activity(self, data: ActivityData):

        item = E('activity', namespace=Namespace.ACTIVITY)
        if data is not None:
            general = item.add_tag(data.general)
            if data.specific is not None:
                general.add_tag(data.specific)
            if data.text:
                general.add_tag_text('text', data.text)

        result = yield self.publish(Namespace.ACTIVITY, item, id_='current')

        yield finalize(result)


class Activity(Base):

    def get_activity(self) -> tuple[Optional[str], Optional[str]]:
        elements = self.findall('{%s}*' % Namespace.ACTIVITY)
        for element in elements:
            if element.localname == 'text':
                continue

            specific = element.find('{%s}*' % Namespace.ACTIVITY)
            if specific is None:
                return element.localname, None
            return element.localname, specific.localname
        return None, None

    def get_text(self) -> Optional[str]:
        return self.find_tag_text('text')


register_class_lookup('activity', Namespace.ACTIVITY, Activity)
