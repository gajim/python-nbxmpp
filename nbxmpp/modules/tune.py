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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Node
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import TuneData
from nbxmpp.const import TUNE_DATA
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.task import iq_request_task


class Tune(BaseModule):

    _depends = {
        'publish': 'PubSub'
    }

    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_tune,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_tune(self, _client, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.TUNE:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        tune_node = item.getTag('tune', namespace=Namespace.TUNE)
        if not tune_node.getChildren():
            self._log.info('Received tune: %s - no tune set', properties.jid)
            return

        tune_dict = {}
        for attr in TUNE_DATA:
            tune_dict[attr] = tune_node.getTagData(attr)

        data = TuneData(**tune_dict)
        if data.artist is None and data.title is None:
            self._log.warning('Missing artist or title: %s %s',
                              data, properties.jid)
            return

        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received tune: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_tune(self, data):
        task = yield

        item = Node('tune', {'xmlns': Namespace.TUNE})
        if data is not None:
            data = data._asdict()
            for tag, value in data.items():
                if value is not None:
                    item.addChild(tag, payload=value)

        result = yield self.publish(Namespace.TUNE, item, id_='current')

        yield finalize(task, result)
