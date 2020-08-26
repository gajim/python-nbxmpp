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
from nbxmpp.const import PresenceType
from nbxmpp.const import PresenceShow
from nbxmpp.modules.base import BaseModule


class BasePresence(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_presence_base,
                          priority=10),
        ]

    def _process_presence_base(self, _client, stanza, properties):
        properties.type = self._parse_type(stanza)
        properties.priority = self._parse_priority(stanza)
        properties.show = self._parse_show(stanza)
        properties.jid = stanza.getFrom()
        properties.id = stanza.getID()
        properties.status = stanza.getStatus()

        if properties.type.is_error:
            properties.error = error_factory(stanza)

        own_jid = self._client.get_bound_jid()
        properties.self_presence = own_jid == properties.jid
        properties.self_bare = properties.jid.bare_match(own_jid)

    def _parse_priority(self, stanza):
        priority = stanza.getPriority()
        if priority is None:
            return 0

        try:
            priority = int(priority)
        except Exception:
            self._log.warning('Invalid priority value: %s', priority)
            self._log.warning(stanza)
            return 0

        if priority not in range(-129, 128):
            self._log.warning('Invalid priority value: %s', priority)
            self._log.warning(stanza)
            return 0

        return priority

    def _parse_type(self, stanza):
        type_ = stanza.getType()
        try:
            return PresenceType(type_)
        except ValueError:
            self._log.warning('Presence with invalid type received')
            self._log.warning(stanza)
            self._client.send_stanza(ErrorStanza(stanza, ERR_BAD_REQUEST))
            raise NodeProcessed

    def _parse_show(self, stanza):
        show = stanza.getShow()
        if show is None:
            return PresenceShow.ONLINE
        try:
            return PresenceShow(stanza.getShow())
        except ValueError:
            self._log.warning('Presence with invalid show')
            self._log.warning(stanza)
            return PresenceShow.ONLINE
