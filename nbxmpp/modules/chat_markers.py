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

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import ChatMarker
from nbxmpp.modules.base import BaseModule


class ChatMarkers(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_marker,
                          ns=Namespace.CHATMARKERS,
                          priority=15),
        ]

    def _process_message_marker(self,
                                _client: types.Client,
                                stanza: types.Message,
                                properties: Any):

        type_ = stanza.find_tag('received', namespace=Namespace.CHATMARKERS)
        if type_ is None:
            type_ = stanza.find_tag('displayed',
                                    namespace=Namespace.CHATMARKERS)
            if type_ is None:
                type_ = stanza.find_tag('acknowledged',
                                        namespace=Namespace.CHATMARKERS)
                if type_ is None:
                    return

        name = type_.localname
        id_ = type_.get('id')
        if id_ is None:
            self._log.warning('Chatmarker without id')
            self._log.warning(stanza)
            return

        properties.marker = ChatMarker(name, id_)
