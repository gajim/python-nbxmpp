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
from nbxmpp.structs import HTTPAuthData
from nbxmpp.modules.base import BaseModule


class HTTPAuth(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_http_auth,
                          ns=Namespace.HTTP_AUTH,
                          priority=40),
            StanzaHandler(name='iq',
                          callback=self._process_http_auth,
                          typ='get',
                          ns=Namespace.HTTP_AUTH,
                          priority=40)
        ]

    def _process_http_auth(self, _client, stanza, properties):
        confirm = stanza.getTag('confirm', namespace=Namespace.HTTP_AUTH)
        if confirm is None:
            return

        attrs = confirm.getAttrs()
        body = stanza.getTagData('body')
        id_ = attrs.get('id')
        method = attrs.get('method')
        url = attrs.get('url')
        properties.http_auth = HTTPAuthData(id_, method, url, body)
        self._log.info('HTTPAuth received: %s %s %s %s',
                       id_, method, url, body)
