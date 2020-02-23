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

from nbxmpp.protocol import NS_CHATMARKERS
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import ChatMarker

log = logging.getLogger('nbxmpp.m.chat_markers')


class ChatMarkers:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_marker,
                          ns=NS_CHATMARKERS,
                          priority=15),
        ]

    @staticmethod
    def _process_message_marker(_client, stanza, properties):
        type_ = stanza.getTag('received', namespace=NS_CHATMARKERS)
        if type_ is None:
            type_ = stanza.getTag('displayed', namespace=NS_CHATMARKERS)
            if type_ is None:
                type_ = stanza.getTag('acknowledged', namespace=NS_CHATMARKERS)
                if type_ is None:
                    return

        name = type_.getName()
        id_ = type_.getAttr('id')
        if id_ is None:
            log.warning('Chatmarker without id')
            log.warning(stanza)
            return

        properties.marker = ChatMarker(name, id_)
