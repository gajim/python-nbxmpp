# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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

from nbxmpp.protocol import NS_HTTPUPLOAD_0
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import HTTPUploadData
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.base import BaseModule


ALLOWED_HEADERS = ['Authorization', 'Cookie', 'Expires']


class HTTPUpload(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @call_on_response('_received_slot')
    def request_slot(self, jid, filename, size, content_type):
        iq = Iq(typ='get', to=jid)
        attr = {'filename': filename,
                'size': size,
                'content-type': content_type}
        iq.setTag(name="request",
                  namespace=NS_HTTPUPLOAD_0,
                  attrs=attr)
        return iq

    @callback
    def _received_slot(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        slot = stanza.getTag('slot', namespace=NS_HTTPUPLOAD_0)
        if slot is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed',
                               'No slot node found')

        put_uri = slot.getTagAttr('put', 'url')
        if put_uri is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed',
                               'No put uri found')

        get_uri = slot.getTagAttr('get', 'url')
        if get_uri is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed',
                               'No get uri found')

        headers = {}
        for header in slot.getTag('put').getTags('header'):
            name = header.getAttr('name')
            if name not in ALLOWED_HEADERS:
                return raise_error(self._log.warning, stanza,
                                   'stanza-malformed',
                                   'Not allowed header found: %s' % name)
            data = header.getData()
            if '\n' in data:
                return raise_error(self._log.warning, stanza,
                                   'stanza-malformed',
                                   'NNewline in header data found')

            headers[name] = data

        return HTTPUploadData(put_uri=put_uri,
                              get_uri=get_uri,
                              headers=headers)
