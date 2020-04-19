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
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.base import BaseModule


class Idle(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_idle,
                          ns=Namespace.IDLE,
                          priority=15)
        ]

    def _process_idle(self, _client, stanza, properties):
        idle_tag = stanza.getTag('idle', namespace=Namespace.IDLE)
        if idle_tag is None:
            return

        since = idle_tag.getAttr('since')
        if since is None:
            self._log.warning('No since attr in idle node')
            self._log.warning(stanza)
            return

        timestamp = parse_datetime(since, convert='utc', epoch=True)
        if timestamp is None:
            self._log.warning('Invalid timestamp received: %s', since)
            self._log.warning(stanza)

        properties.idle_timestamp = timestamp
