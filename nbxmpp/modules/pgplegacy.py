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
from nbxmpp.modules.base import BaseModule


class PGPLegacy(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pgplegacy_message,
                          ns=Namespace.ENCRYPTED,
                          priority=7),
            StanzaHandler(name='presence',
                          callback=self._process_signed,
                          ns=Namespace.SIGNED,
                          priority=15)
        ]

    @staticmethod
    def _process_signed(_client, stanza, properties):
        signed = stanza.getTag('x', namespace=Namespace.SIGNED)
        if signed is None:
            return

        properties.signed = signed.getData()

    def _process_pgplegacy_message(self, _client, stanza, properties):
        pgplegacy = stanza.getTag('x', namespace=Namespace.ENCRYPTED)
        if pgplegacy is None:
            self._log.warning('No x node found')
            self._log.warning(stanza)
            return

        data = pgplegacy.getData()
        if not data:
            self._log.warning('No data in x node found')
            self._log.warning(stanza)
            return

        self._log.info('Encrypted message received')
        properties.pgp_legacy = data
