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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.structs import HTTPUploadData
from nbxmpp.errors import HTTPUploadStanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule


ALLOWED_HEADERS = ['Authorization', 'Cookie', 'Expires']


class HTTPUpload(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_slot(self, jid, filename, size, content_type):
        _task = yield

        response = yield _make_request(jid, filename, size, content_type)
        if response.isError():
            raise HTTPUploadStanzaError(response)

        slot = response.getTag('slot', namespace=Namespace.HTTPUPLOAD_0)
        if slot is None:
            raise MalformedStanzaError('slot node missing', response)

        put_uri = slot.getTagAttr('put', 'url')
        if put_uri is None:
            raise MalformedStanzaError('put uri missing', response)

        get_uri = slot.getTagAttr('get', 'url')
        if get_uri is None:
            raise MalformedStanzaError('get uri missing', response)

        headers = {}
        for header in slot.getTag('put').getTags('header'):
            name = header.getAttr('name')
            if name not in ALLOWED_HEADERS:
                raise MalformedStanzaError(
                    'not allowed header found: %s' % name, response)

            data = header.getData()
            if '\n' in data:
                raise MalformedStanzaError(
                    'newline in header data found', response)

            headers[name] = data

        yield HTTPUploadData(put_uri=put_uri,
                             get_uri=get_uri,
                             headers=headers)


def _make_request(jid, filename, size, content_type):
    iq = Iq(typ='get', to=jid)
    attr = {'filename': filename,
            'size': size,
            'content-type': content_type}
    iq.setTag(name="request",
              namespace=Namespace.HTTPUPLOAD_0,
              attrs=attr)
    return iq
