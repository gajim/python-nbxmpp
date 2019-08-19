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

import logging

from nbxmpp.protocol import NS_BOOKMARKS
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import NS_PRIVATE
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import BookmarkData
from nbxmpp.const import BookmarkStoreType
from nbxmpp.util import from_xs_boolean
from nbxmpp.util import to_xs_boolean
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.pubsub import get_pubsub_item
from nbxmpp.modules.pubsub import get_pubsub_request
from nbxmpp.modules.pubsub import get_bookmark_publish_options

log = logging.getLogger('nbxmpp.m.bookmarks')


class Bookmarks:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_bookmarks,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

    def _process_pubsub_bookmarks(self, _con, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_BOOKMARKS:
            return

        if properties.pubsub_event.deleted or properties.pubsub_event.retracted:
            return

        item = properties.pubsub_event.item
        if item is None:
            return

        storage_node = item.getTag('storage', namespace=NS_BOOKMARKS)
        if storage_node is None:
            return

        bookmarks = []
        if storage_node.getChildren():
            bookmarks = self._parse_bookmarks(storage_node)

        pubsub_event = properties.pubsub_event._replace(data=bookmarks)
        log.info('Received bookmarks from: %s', properties.jid)
        for bookmark in bookmarks:
            log.info(bookmark)

        properties.pubsub_event = pubsub_event

    @staticmethod
    def _parse_bookmarks(storage):
        bookmarks = []
        confs = storage.getTags('conference')
        for conf in confs:
            autojoin = conf.getAttr('autojoin')
            if autojoin is None:
                autojoin = False
            else:
                try:
                    autojoin = from_xs_boolean(autojoin)
                except ValueError as error:
                    log.warning(error)
                    log.warning(storage)
                    autojoin = False

            try:
                jid = JID(conf.getAttr('jid'))
            except Exception as error:
                log.warning('Invalid JID: %s, %s',
                            conf.getAttr('jid'), error)
                continue

            bookmark = BookmarkData(
                jid=jid,
                name=conf.getAttr('name'),
                autojoin=autojoin,
                password=conf.getTagData('password'),
                nick=conf.getTagData('nick'))
            bookmarks.append(bookmark)

        return bookmarks

    @staticmethod
    def get_private_request():
        iq = Iq(typ='get')
        query = iq.addChild(name='query', namespace=NS_PRIVATE)
        query.addChild(name='storage', namespace=NS_BOOKMARKS)
        return iq

    @call_on_response('_bookmarks_received')
    def request_bookmarks(self, type_):
        jid = self._client.get_bound_jid().getBare()
        if type_ == BookmarkStoreType.PUBSUB:
            log.info('Request bookmarks (PubSub)')
            request = get_pubsub_request(jid, NS_BOOKMARKS, max_items=1)
            return request, {'type_': type_}
        if type_ == BookmarkStoreType.PRIVATE:
            log.info('Request bookmarks (Private Storage)')
            return self.get_private_request(), {'type_': type_}

    @callback
    def _bookmarks_received(self, stanza, type_):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        bookmarks = []
        if type_ == BookmarkStoreType.PUBSUB:
            item = get_pubsub_item(stanza)
            storage_node = item.getTag('storage', namespace=NS_BOOKMARKS)

        if type_ == BookmarkStoreType.PRIVATE:
            query = stanza.getQuery()
            storage_node = query.getTag('storage', namespace=NS_BOOKMARKS)

        if storage_node.getChildren():
            bookmarks = self._parse_bookmarks(storage_node)

        from_ = stanza.getFrom()
        if from_ is None:
            from_ = self._client.get_bound_jid().getBare()
        log.info('Received bookmarks from: %s', from_)
        for bookmark in bookmarks:
            log.info(bookmark)
        return bookmarks

    @staticmethod
    def _build_storage_node(bookmarks):
        storage_node = Node(tag='storage', attrs={'xmlns': NS_BOOKMARKS})
        for bookmark in bookmarks:
            conf_node = storage_node.addChild(name="conference")
            conf_node.setAttr('jid', bookmark.jid)
            conf_node.setAttr('autojoin', to_xs_boolean(bookmark.autojoin))
            if bookmark.name:
                conf_node.setAttr('name', bookmark.name)
            if bookmark.nick:
                conf_node.setTagData('nick', bookmark.nick)
            if bookmark.password:
                conf_node.setTagData('password', bookmark.password)
        return storage_node

    def store_bookmarks(self, bookmarks, type_):
        if type_ == BookmarkStoreType.PUBSUB:
            self._store_with_pubsub(bookmarks)
        elif type_ == BookmarkStoreType.PRIVATE:
            self._store_with_private(bookmarks)

    def _store_with_pubsub(self, bookmarks):
        log.info('Store Bookmarks (PubSub)')
        jid = self._client.get_bound_jid().getBare()
        item = self._build_storage_node(bookmarks)
        options = get_bookmark_publish_options()
        self._client.get_module('PubSub').publish(jid,
                                                  NS_BOOKMARKS,
                                                  item,
                                                  id_='current',
                                                  options=options)

    @call_on_response('_on_private_store_result')
    def _store_with_private(self, bookmarks):
        log.info('Store Bookmarks (Private Storage)')
        storage_node = self._build_storage_node(bookmarks)
        return Iq('set', NS_PRIVATE, payload=storage_node)

    @staticmethod
    def _on_private_store_result(_con, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)
