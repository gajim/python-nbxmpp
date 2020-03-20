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

from nbxmpp.protocol import Error as ErrorStanza
from nbxmpp.protocol import ERR_BAD_REQUEST
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import error_factory
from nbxmpp.const import IqType
from nbxmpp.modules.base import BaseModule


class BaseIq(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_iq_base,
                          priority=10),
        ]

    def _process_iq_base(self, _client, stanza, properties):
        try:
            properties.type = IqType(stanza.getType())
        except ValueError:
            self._log.warning('Message with invalid type: %s', stanza.getType())
            self._log.warning(stanza)
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

        properties.jid = stanza.getFrom()
        properties.id = stanza.getID()

        childs = stanza.getChildren()
        for child in childs:
            if child.getName() != 'error':
                properties.payload = child
                break

        properties.query = stanza.getQuery()

        if properties.type.is_error:
            properties.error = error_factory(stanza)
