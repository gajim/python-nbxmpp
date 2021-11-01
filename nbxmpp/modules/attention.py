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
from nbxmpp.modules.base import BaseModule


class Attention(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_attention,
                          ns=Namespace.ATTENTION,
                          priority=15),
        ]

    def _process_message_attention(self,
                                   _client: types.Client,
                                   stanza: types.Message,
                                   properties: Any):

        attention = stanza.find_tag('attention', namespace=Namespace.ATTENTION)
        if attention is None:
            return

        if properties.is_mam_message:
            return

        if properties.is_carbon_message and properties.carbon.is_sent:
            return

        if stanza.find_tag('delay', namespace=Namespace.DELAY2) is not None:
            return

        properties.attention = True
