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
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import raise_if_error
from nbxmpp.modules.bookmarks.util import parse_bookmarks
from nbxmpp.modules.bookmarks.util import build_storage_node


BOOKMARK_OPTIONS = {
    'pubsub#persist_items': 'true',
    'pubsub#access_model': 'whitelist',
}


class PEPBookmarks(BaseModule):

    _depends = {
        'publish': 'PubSub',
        'request_items': 'PubSub',
    }

    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_bookmarks,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_bookmarks(self, _client, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.BOOKMARKS:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        try:
            bookmarks = parse_bookmarks(item, self._log)
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            raise NodeProcessed

        if not bookmarks:
            self._log.info('Bookmarks removed')
            return

        pubsub_event = properties.pubsub_event._replace(data=bookmarks)
        self._log.info('Received bookmarks from: %s', properties.jid)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def request_bookmarks(self):
        _task = yield

        items = yield self.request_items(Namespace.BOOKMARKS, max_items=1)
        raise_if_error(items)

        if not items:
            yield []

        bookmarks = parse_bookmarks(items[0], self._log)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        yield bookmarks

    @iq_request_task
    def store_bookmarks(self, bookmarks):
        _task = yield

        self._log.info('Store Bookmarks')

        self.publish(Namespace.BOOKMARKS,
                     build_storage_node(bookmarks),
                     id_='current',
                     options=BOOKMARK_OPTIONS,
                     force_node_options=True)
