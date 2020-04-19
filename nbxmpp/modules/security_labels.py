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
from nbxmpp.structs import SecurityLabel
from nbxmpp.structs import DisplayMarking
from nbxmpp.modules.base import BaseModule


class SecurityLabels(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_security_label,
                          ns=Namespace.SECLABEL,
                          priority=15),
        ]

    def _process_message_security_label(self, _client, stanza, properties):
        security = stanza.getTag('securitylabel', namespace=Namespace.SECLABEL)
        if security is None:
            return

        displaymarking = security.getTag('displaymarking')
        if displaymarking is None:
            return

        label = displaymarking.getData()
        if not label:
            self._log.warning('No label found')
            self._log.warning(stanza)
            return

        fgcolor = displaymarking.getAttr('fgcolor')
        bgcolor = displaymarking.getAttr('bgcolor')

        properties.security_label = SecurityLabel(
            DisplayMarking(label, fgcolor, bgcolor))
