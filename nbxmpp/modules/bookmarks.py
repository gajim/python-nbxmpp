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
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import validate_resourcepart
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
from nbxmpp.modules.base import BaseModule


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


class Bookmarks(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_bookmarks,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_pubsub_bookmarks2,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
        ]

        self._bookmark_2_queue = {}
        self._bookmark_1_queue = []
        self._node_configuration_in_progress = False
        self._node_configuration_not_possible = False

    def _process_pubsub_bookmarks(self, _client, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.BOOKMARKS:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        storage_node = item.getTag('storage', namespace=Namespace.BOOKMARKS)
        if storage_node is None:
            self._log.warning('No storage node found')
            self._log.warning(stanza)
            raise NodeProcessed

        bookmarks = self._parse_bookmarks(storage_node)
        if not bookmarks:
            self._log.info('Bookmarks removed')
            return

        pubsub_event = properties.pubsub_event._replace(data=bookmarks)
        self._log.info('Received bookmarks from: %s', properties.jid)
        for bookmark in bookmarks:
            self._log.info(bookmark)

        properties.pubsub_event = pubsub_event

    def _process_pubsub_bookmarks2(self, _client, _stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.BOOKMARKS_2:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        bookmark_item = self._parse_bookmarks2(item)
        if bookmark_item is None:
            raise NodeProcessed

        pubsub_event = properties.pubsub_event._replace(data=bookmark_item)
        self._log.info('Received bookmark item from: %s', properties.jid)
        self._log.info(bookmark_item)

        properties.pubsub_event = pubsub_event

    def _parse_bookmarks(self, storage):
        bookmarks = []
        confs = storage.getTags('conference')
        for conf in confs:
            try:
                jid = JID(conf.getAttr('jid'))
            except Exception as error:
                self._log.warning('Invalid JID: "%s", %s',
                                  conf.getAttr('jid'),
                                  error)
                continue

            autojoin = self._parse_autojoin(conf.getAttr('autojoin'))
            nick = self._parse_nickname(conf.getTagData('nick'))
            name = conf.getAttr('name') or None
            password = conf.getTagData('password') or None

            bookmark = BookmarkData(
                jid=jid,
                name=name,
                autojoin=autojoin,
                password=password,
                nick=nick)
            bookmarks.append(bookmark)

        return bookmarks

    def _parse_bookmarks2(self, item):
        conference = item.getTag('conference', namespace=Namespace.BOOKMARKS_2)
        if conference is None:
            self._log.warning('No conference node found')
            self._log.warning(item)
            return None

        try:
            jid = JID(item.getAttr('id'))
        except Exception as error:
            self._log.warning('Invalid JID: "%s", %s',
                              item.getAttr('id'),
                              error)
            return None

        autojoin = self._parse_autojoin(conference.getAttr('autojoin'))
        nick = self._parse_nickname(conference.getTagData('nick'))
        name = conference.getAttr('name') or None
        password = conference.getTagData('password') or None

        return BookmarkData(jid=jid,
                            name=name,
                            autojoin=autojoin,
                            password=password,
                            nick=nick)

    def _parse_nickname(self, nick):
        if nick is None:
            return None

        try:
            return validate_resourcepart(nick)
        except Exception as error:
            self._log.warning('Invalid nick: %s, %s', nick, error)
            return None

    def _parse_autojoin(self, autojoin):
        if autojoin is None:
            return False

        try:
            return from_xs_boolean(autojoin)
        except ValueError as error:
            self._log.warning('Invalid autojoin attribute: (%s) %s',
                              autojoin, error)
            return False

    @staticmethod
    def get_private_request():
        iq = Iq(typ='get')
        query = iq.addChild(name='query', namespace=Namespace.PRIVATE)
        query.addChild(name='storage', namespace=Namespace.BOOKMARKS)
        return iq

    @call_on_response('_bookmarks_received')
    def request_bookmarks(self, type_):
        jid = self._client.get_bound_jid().getBare()
        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_2:
            self._log.info('Request bookmarks 2 (PubSub)')
            request = get_pubsub_request(jid, Namespace.BOOKMARKS_2)
            return request, {'type_': type_}

        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_1:
            self._log.info('Request bookmarks (PubSub)')
            request = get_pubsub_request(jid, Namespace.BOOKMARKS, max_items=1)
            return request, {'type_': type_}

        if type_ == BookmarkStoreType.PRIVATE:
            self._log.info('Request bookmarks (Private Storage)')
            return self.get_private_request(), {'type_': type_}
        return None

    @callback
    def _bookmarks_received(self, stanza, type_):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        bookmarks = []
        if type_ == BookmarkStoreType.PUBSUB_BOOKMARK_2:
            items = get_pubsub_items(stanza, Namespace.BOOKMARKS_2)
            if items is None:
                return raise_error(self._log.warning,
                                   stanza,
                                   'stanza-malformed')

            for item in items:
                bookmark_item = self._parse_bookmarks2(item)
                if bookmark_item is not None:
                    bookmarks.append(bookmark_item)

        elif type_ == BookmarkStoreType.PUBSUB_BOOKMARK_1:
            item = get_pubsub_item(stanza)
            if item is not None:
                storage_node = item.getTag('storage',
                                           namespace=Namespace.BOOKMARKS)
                if storage_node is None:
                    return raise_error(self._log.warning,
                                       stanza,
                                       'stanza-malformed',
                                       'No storage node')

                if storage_node.getChildren():
                    bookmarks = self._parse_bookmarks(storage_node)

        elif type_ == BookmarkStoreType.PRIVATE:
            query = stanza.getQuery()
            storage_node = query.getTag('storage',
                                        namespace=Namespace.BOOKMARKS)
            if storage_node is None:
                return raise_error(self._log.warning,
                                   stanza,
                                   'stanza-malformed',
                                   'No storage node')

            if storage_node.getChildren():
                bookmarks = self._parse_bookmarks(storage_node)

        from_ = stanza.getFrom()
        if from_ is None:
            from_ = self._client.get_bound_jid().getBare()
        self._log.info('Received bookmarks from: %s', from_)
        for bookmark in bookmarks:
            self._log.info(bookmark)
        return bookmarks

    @staticmethod
    def _build_storage_node(bookmarks):
        storage_node = Node(tag='storage', attrs={'xmlns': Namespace.BOOKMARKS})
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
        attrs = {'xmlns': Namespace.BOOKMARKS_2}
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
        self._log.info('Retract Bookmark: %s', bookmark_jid)
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').retract(jid,
                                                  Namespace.BOOKMARKS_2,
                                                  str(bookmark_jid))

    def _store_bookmark_1(self, bookmarks):
        self._log.info('Store Bookmarks 1 (PubSub)')
        jid = self._client.get_bound_jid().getBare()
        self._bookmark_1_queue = bookmarks
        item = self._build_storage_node(bookmarks)
        options = get_publish_options(BOOKMARK_1_OPTIONS)
        self._client.get_module('PubSub').publish(
            jid,
            Namespace.BOOKMARKS,
            item,
            id_='current',
            options=options,
            callback=self._on_store_bookmark_result,
            user_data=Namespace.BOOKMARKS)

    def _store_bookmark_2(self, bookmarks):
        if self._node_configuration_not_possible:
            self._log.warning('Node configuration not possible')
            return

        self._log.info('Store Bookmarks 2 (PubSub)')
        jid = self._client.get_bound_jid().getBare()
        for bookmark in bookmarks:
            self._bookmark_2_queue[bookmark.jid] = bookmark
            item = self._build_conference_node(bookmark)
            options = get_publish_options(BOOKMARK_2_OPTIONS)
            self._client.get_module('PubSub').publish(
                jid,
                Namespace.BOOKMARKS_2,
                item,
                id_=str(bookmark.jid),
                options=options,
                callback=self._on_store_bookmark_result,
                user_data=Namespace.BOOKMARKS_2)

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
            self._log.warning(result)

    def _on_node_configuration_received(self, result):
        if is_error_result(result):
            self._log.warning(result)
            self._bookmark_1_queue = []
            self._bookmark_2_queue.clear()
            return

        if result.node == Namespace.BOOKMARKS:
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
            self._log.warning(result)
            self._bookmark_2_queue.clear()
            self._bookmark_1_queue = []
            self._node_configuration_not_possible = True
            return

        self._log.info('Republish bookmarks')
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
        self._log.info('Store Bookmarks (Private Storage)')
        storage_node = self._build_storage_node(bookmarks)
        return Iq('set', Namespace.PRIVATE, payload=storage_node)

    def _on_private_store_result(self, _client, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return None
