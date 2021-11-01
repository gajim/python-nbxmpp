# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
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

from __future__ import annotations

from typing import Optional

import logging

from nbxmpp import types
from nbxmpp.jid import validate_resourcepart
from nbxmpp.jid import JID
from nbxmpp.builder import Iq
from nbxmpp.builder import E
from nbxmpp.util import from_xs_boolean
from nbxmpp.util import to_xs_boolean
from nbxmpp.namespaces import Namespace
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.structs import BookmarkData


def parse_nickname(nick: Optional[str]) -> Optional[str]:
    if nick is None:
        return None

    try:
        return validate_resourcepart(nick)
    except Exception:
        return None


def parse_autojoin(autojoin: Optional[str]) -> bool:
    if autojoin is None:
        return False

    try:
        return from_xs_boolean(autojoin)
    except ValueError:
        return False


def parse_bookmark(item: types.Base) -> BookmarkData:
    conference = item.find_tag('conference', namespace=Namespace.BOOKMARKS_1)
    if conference is None:
        raise MalformedStanzaError('conference node missing', item)

    try:
        jid = JID.from_string(item.get('id'))
    except Exception as error:
        raise MalformedStanzaError('invalid jid: %s' % error, item)

    if jid.localpart is None or jid.resource is not None:
        raise MalformedStanzaError('invalid jid', item)

    autojoin = parse_autojoin(conference.get('autojoin'))
    nick = parse_nickname(conference.find_tag_text('nick'))
    name = conference.get('name') or None
    password = conference.find_tag_text('password') or None
    extensions = conference.find_tag('extensions')

    return BookmarkData(jid=jid,
                        name=name,
                        nick=nick,
                        autojoin=autojoin,
                        password=password,
                        extensions=extensions)


def parse_bookmarks(item: types.Base, log: logging.Logger) -> list[BookmarkData]:
    storage_node = item.find_tag('storage', namespace=Namespace.BOOKMARKS)
    if storage_node is None:
        raise MalformedStanzaError('storage node missing', item)

    return parse_storage_node(storage_node, log)


def parse_private_bookmarks(response: types.Iq, log: logging.Logger) -> list[BookmarkData]:
    query = response.get_query()
    storage_node = query.find_tag('storage', namespace=Namespace.BOOKMARKS)
    if storage_node is None:
        raise MalformedStanzaError('storage node missing', response)

    return parse_storage_node(storage_node, log)


def parse_storage_node(storage: types.Base, log: logging.Logger) -> list[BookmarkData]:
    bookmarks: list[BookmarkData] = []
    confs = storage.find_tags('conference')
    for conf in confs:
        try:
            jid = JID.from_string(conf.get('jid'))
        except Exception:
            log.warning('invalid jid: %s', conf)
            continue

        if jid.localpart is None or jid.resource is not None:
            log.warning('invalid jid: %s', conf)
            continue

        autojoin = parse_autojoin(conf.get('autojoin'))
        nick = parse_nickname(conf.find_tag_text('nick'))
        name = conf.get('name') or None
        password = conf.find_tag_text('password') or None

        bookmark = BookmarkData(
            jid=jid,
            name=name,
            autojoin=autojoin,
            password=password,
            nick=nick)
        bookmarks.append(bookmark)

    return bookmarks


def build_conference_node(bookmark: BookmarkData) -> types.Base:
    conference = E('conference', namespace=Namespace.BOOKMARKS_1)
    if bookmark.autojoin:
        conference.set('autojoin', 'true')

    if bookmark.name:
        conference.set('name', bookmark.name)

    if bookmark.nick:
        conference.add_tag_text('nick', bookmark.nick)

    if bookmark.extensions is not None:
        conference.append(bookmark.extensions)

    return conference


def build_storage_node(bookmarks: list[BookmarkData]) -> types.Base:
    storage_node = E('storage', namespace=Namespace.BOOKMARKS)
    for bookmark in bookmarks:
        conf_node = storage_node.add_tag(
            'conference',
             jid=bookmark.jid,
             autojoin=to_xs_boolean(bookmark.autojoin))

        if bookmark.name:
            conf_node.set('name', bookmark.name)
        if bookmark.nick:
            conf_node.add_tag_text('nick', bookmark.nick)
        if bookmark.password:
            conf_node.add_tag_text('password', bookmark.password)

    return storage_node


def get_private_request() -> types.Iq:
    iq = Iq()
    query = iq.add_query(namespace=Namespace.PRIVATE)
    query.add_tag('storage', namespace=Namespace.BOOKMARKS)
    return iq
