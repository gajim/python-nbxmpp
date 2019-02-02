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
import base64

from nbxmpp.protocol import NS_AVATAR_DATA
from nbxmpp.protocol import NS_AVATAR_METADATA
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import JID
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import AvatarMetaData
from nbxmpp.structs import AvatarData
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.modules.pubsub import get_pubsub_request

log = logging.getLogger('nbxmpp.m.user_avatar')


class UserAvatar:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_avatar,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_avatar(self, _con, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_AVATAR_METADATA:
            return

        item = properties.pubsub_event.item

        metadata = item.getTag('metadata', namespace=NS_AVATAR_METADATA)
        if not metadata.getChildren():
            pubsub_event = properties.pubsub_event._replace(empty=True)
            log.info('Received avatar metadata: %s - no avatar set',
                     properties.jid)
        else:
            info = metadata.getTags('info', one=True)
            try:
                data = AvatarMetaData(**info.getAttrs())
            except Exception:
                log.warning('Malformed user avatar data')
                log.warning(stanza)
                raise NodeProcessed

            pubsub_event = properties.pubsub_event._replace(data=data)
            log.info('Received avatar metadata: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @call_on_response('_avatar_data_received')
    def request_avatar(self, jid, id_):
        return get_pubsub_request(jid, NS_AVATAR_DATA, id_=id_)

    @callback
    def _avatar_data_received(self, stanza):
        jid = stanza.getFrom()
        if jid is None:
            jid = JID(self._client.get_bound_jid().getBare())

        if not isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            raise NodeProcessed

        pubsub_node = stanza.getTag('pubsub')
        items_node = pubsub_node.getTag('items')
        item = items_node.getTag('item')

        sha = item.getAttr('id')
        data_node = item.getTag('data', namespace=NS_AVATAR_DATA)
        if data_node is None:
            log.warning('No data node found')
            log.warning(stanza)
            raise NodeProcessed

        data = data_node.getData()
        if data is None:
            log.warning('Data node empty')
            log.warning(stanza)
            raise NodeProcessed

        data = base64.b64decode(data.encode('utf-8'))
        log.info('Received avatar data: %s %s', jid, sha)
        return AvatarData(jid, sha, data)
