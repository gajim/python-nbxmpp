# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
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

from nbxmpp.protocol import NS_HTTP_AUTH
from nbxmpp.util import StanzaHandler

log = logging.getLogger('nbxmpp.m.http_auth')


class HTTPAuth:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_http_auth,
                          ns=NS_HTTP_AUTH,
                          priority=40),
            StanzaHandler(name='iq',
                          callback=self._process_http_auth,
                          typ='get',
                          ns=NS_HTTP_AUTH,
                          priority=40)
        ]

    @staticmethod
    def _process_http_auth(_con, stanza, properties):
        confirm = stanza.getTag('confirm', namespace=NS_HTTP_AUTH)
        if confirm is None:
            return

        http_auth = confirm.getAttrs().copy()
        http_auth['body'] = stanza.getTagData('body')
        properties.http_auth = http_auth
        log.info('Found data: %s', http_auth)
