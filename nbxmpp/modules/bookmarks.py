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
from nbxmpp.protocol import NS_BOOKMARKS_2
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import NS_PRIVATE
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import BookmarkData
from nbxmpp.const import BookmarkStoreType
from nbxmpp.util import from_xs_boolean
from nbxmpp.util import to_xs_boolean
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.util import is_error_result
from nbxmpp.modules.pubsub import get_pubsub_item
from nbxmpp.modules.pubsub import get_pubsub_items
from nbxmpp.modules.pubsub import get_pubsub_request
from nbxmpp.modules.pubsub import get_publish_options


log = logging.getLogger('nbxmpp.m.bookmarks')


BOOKMARK_1_OPTIONS = {
    'pubsub#persist_items': 'true',
    'pubsub#access_model': 'whitelist',
}

BOOKMARK_2_OPTIONS = {
    'pubsub#notify_delete': 'true',
    'pubsub#notify_retract': 'true',
    'pubsub#persist_items': 'true',
    'pubsub#max_items': '128',
    'pubsub#access_model': 'whitelist',
    'pubsub#send_last_published_item': 'never',
}


class Bookmarks:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_bookmarks,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_pubsub_bookmarks2,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
        ]

        self._bookmark_2_queue = {}
        self._bookmark_1_queue = []
        self._node_configuration_in_progress = False
        self._node_configuration_not_possible = False

    def _process_pubsub_bookmarks(self, _con, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_BOOKMARKS:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        storage_node = item.getTag('storage', namespace=NS_BOOKMARKS)
        if storage_node is None:
            log.warning('No storage node found')
            log.warning(stanza)
            raise NodeProcessed

        bookmarks = self._parse_bookmarks(storage_node)
        if not bookmarks:
            log.info('Bookmarks removed')
            return

        pubsub_event = properties.pubsub_event._replace(data=bookmarks)
        log.info('Received bookmarks from: %s', properties.jid)
        for bookmark in bookmarks:
            log.info(bookmark)

        properties.pubsub_event = pubsub_event

    def _process_pubsub_bookmarks2(self, _con, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_BOOKMARKS_2:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        bookmark_item = self._parse_bookmarks2(item)
        if bookmark_item is None:
            raise NodeProcessed

        pubsub_event = properties.pubsub_event._replace(data=bookmark_item)
        log.info('Received bookmark item from: %s', properties.jid)
        log.info(bookmark_item)

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
    def _parse_bookmarks2(item):
        jid = item.getAttr('id')
        if jid is None:
            log.warning('No id attr found')
            return

        try:
            jid = JID(jid)
        except Exception as error:
            log.warning('Invalid JID: %s', error)
            log.warning(item)
            return

        conference = item.getTag('conference', namespace=NS_BOOKMARKS_2)
        if conference is None:
            log.warning('No conference node found')
            log.warning(item)
            return

        autojoin = conference.getAttr('autojoin') in ('True', 'true', '1')
        name = conference.getAttr('name')
        nick = conference.getTagData('nick')

        return BookmarkData(jid=jid,
                            name=name or None,
                            autojoin=autojoin,
                            nick=nick or None)

    @staticmethod
    def get_private_request():
        iq = Iq(typ='get')
        query = iq.addChild(name='query', namespace=NS_PRIVATE)
        query.addChild(name='storage', namespace=NS_BOOKMARKS)
        return iq

    @call_on_response('_bookmarks_received')
    def request_bookmarks(self, type_):
        jid = self._client.get_bound_jid().getBare()
        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_2:
            log.info('Request bookmarks 2 (PubSub)')
            request = get_pubsub_request(jid, NS_BOOKMARKS_2)
            return request, {'type_': type_}

        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_1:
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
        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_2:
            items = get_pubsub_items(stanza, NS_BOOKMARKS_2)
            if items is None:
                return bookmarks
            for item in items:
                bookmark_item = self._parse_bookmarks2(item)
                if bookmark_item is not None:
                    bookmarks.append(bookmark_item)

        elif type_ == BookmarkStoreType.PUBSUB_BOOKMARK_1:
            item = get_pubsub_item(stanza)
            if item is not None:
                storage_node = item.getTag('storage', namespace=NS_BOOKMARKS)
                if storage_node.getChildren():
                    bookmarks = self._parse_bookmarks(storage_node)

        elif type_ == BookmarkStoreType.PRIVATE:
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

    @staticmethod
    def _build_conference_node(bookmark):
        attrs = {'xmlns': NS_BOOKMARKS_2}
        if bookmark.autojoin:
            attrs['autojoin'] = 'true'
        if bookmark.name:
            attrs['name'] = bookmark.name
        conference = Node(tag='conference', attrs=attrs)
        if bookmark.nick:
            conference.setTagData('nick', bookmark.nick)
        return conference

    def store_bookmarks(self, bookmarks, type_):
        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_2:
            self._store_bookmark_2(bookmarks)
        elif type_ == BookmarkStoreType.PUBSUB_BOOKMARK_1:
            self._store_bookmark_1(bookmarks)
        elif type_ == BookmarkStoreType.PRIVATE:
            self._store_with_private(bookmarks)

    def retract_bookmark(self, bookmark_jid):
        log.info('Retract Bookmark: %s', bookmark_jid)
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').retract(jid,
                                                  NS_BOOKMARKS_2,
                                                  str(bookmark_jid))

    def _store_bookmark_1(self, bookmarks):
        log.info('Store Bookmarks 1 (PubSub)')
        jid = self._client.get_bound_jid().getBare()
        self._bookmark_1_queue = bookmarks
        item = self._build_storage_node(bookmarks)
        options = get_publish_options(BOOKMARK_1_OPTIONS)
        self._client.get_module('PubSub').publish(
            jid,
            NS_BOOKMARKS,
            item,
            id_='current',
            options=options,
            callback=self._on_store_bookmark_result,
            user_data=NS_BOOKMARKS)

    def _store_bookmark_2(self, bookmarks):
        if self._node_configuration_not_possible:
            log.warning('Node configuration not possible')
            return

        log.info('Store Bookmarks 2 (PubSub)')
        jid = self._client.get_bound_jid().getBare()
        for bookmark in bookmarks:
            self._bookmark_2_queue[bookmark.jid] = bookmark
            item = self._build_conference_node(bookmark)
            options = get_publish_options(BOOKMARK_2_OPTIONS)
            self._client.get_module('PubSub').publish(
                jid,
                NS_BOOKMARKS_2,
                item,
                id_=str(bookmark.jid),
                options=options,
                callback=self._on_store_bookmark_result,
                user_data=NS_BOOKMARKS_2)

    def _on_store_bookmark_result(self, result, node):
        if not is_error_result(result):
            self._bookmark_1_queue = []
            self._bookmark_2_queue.pop(result.id, None)
            return

        if (result.condition == 'conflict' and
                result.app_condition == 'precondition-not-met'):
            if self._node_configuration_in_progress:
                return

            self._node_configuration_in_progress = True
            jid = self._client.get_bound_jid().getBare()
            self._client.get_module('PubSub').get_node_configuration(
                jid,
                node,
                callback=self._on_node_configuration_received)

        else:
            self._bookmark_1_queue = []
            self._bookmark_2_queue.pop(result.id, None)
            log.warning(result)

    def _on_node_configuration_received(self, result):
        if is_error_result(result):
            log.warning(result)
            self._bookmark_1_queue = []
            self._bookmark_2_queue.clear()
            return

        if result.node == NS_BOOKMARKS:
            config = BOOKMARK_1_OPTIONS
        else:
            config = BOOKMARK_2_OPTIONS
        self._apply_config(result.form, config)
        self._client.get_module('PubSub').set_node_configuration(
            result.jid,
            result.node,
            result.form,
            callback=self._on_node_configuration_finished)

    def _on_node_configuration_finished(self, result):
        self._node_configuration_in_progress = False
        if is_error_result(result):
            log.warning(result)
            self._bookmark_2_queue.clear()
            self._bookmark_1_queue = []
            self._node_configuration_not_possible = True
            return

        log.info('Republish bookmarks')
        if self._bookmark_2_queue:
            bookmarks = self._bookmark_2_queue.copy()
            self._bookmark_2_queue.clear()
            self._store_bookmark_2(bookmarks.values())
        else:
            bookmarks = self._bookmark_1_queue.copy()
            self._bookmark_1_queue.clear()
            self._store_bookmark_1(bookmarks)

    @staticmethod
    def _apply_config(form, config):
        for var, value in config.items():
            try:
                field = form[var]
            except KeyError:
                pass
            else:
                field.value = value

    @call_on_response('_on_private_store_result')
    def _store_with_private(self, bookmarks):
        log.info('Store Bookmarks (Private Storage)')
        storage_node = self._build_storage_node(bookmarks)
        return Iq('set', NS_PRIVATE, payload=storage_node)

    @staticmethod
    def _on_private_store_result(_con, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)
