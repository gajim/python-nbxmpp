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
from nbxmpp.protocol import Iq
from nbxmpp.task import iq_request_task
from nbxmpp.errors import StanzaError
from nbxmpp.modules.util import process_response
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.bookmarks.util import build_storage_node
from nbxmpp.modules.bookmarks.util import get_private_request
from nbxmpp.modules.bookmarks.util import parse_private_bookmarks



class PrivateBookmarks(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_bookmarks(self):
        _task = yield

        response = yield get_private_request()
        if response.isError():
            raise StanzaError(response)

        bookmarks = parse_private_bookmarks(response, self._log)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        yield bookmarks

    @iq_request_task
    def store_bookmarks(self, bookmarks):
        _task = yield

        self._log.info('Store Bookmarks')

        storage_node = build_storage_node(bookmarks)
        response = yield Iq('set', Namespace.PRIVATE, payload=storage_node)
        yield process_response(response)
