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

from nbxmpp.protocol import Node
from nbxmpp.protocol import validate_resourcepart
from nbxmpp.protocol import JID
from nbxmpp.protocol import Iq
from nbxmpp.util import from_xs_boolean
from nbxmpp.util import to_xs_boolean
from nbxmpp.namespaces import Namespace
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.structs import BookmarkData


def parse_nickname(nick):
    if nick is None:
        return None

    try:
        return validate_resourcepart(nick)
    except Exception:
        return None


def parse_autojoin(autojoin):
    if autojoin is None:
        return False

    try:
        return from_xs_boolean(autojoin)
    except ValueError:
        return False


def parse_bookmark(item):
    conference = item.getTag('conference', namespace=Namespace.BOOKMARKS_1)
    if conference is None:
        raise MalformedStanzaError('conference node missing', item)

    try:
        jid = JID.from_string(item.getAttr('id'))
    except Exception as error:
        raise MalformedStanzaError('invalid jid: %s' % error, item)

    if jid.localpart is None or jid.resource is not None:
        raise MalformedStanzaError('invalid jid', item)

    autojoin = parse_autojoin(conference.getAttr('autojoin'))
    nick = parse_nickname(conference.getTagData('nick'))
    name = conference.getAttr('name') or None
    password = conference.getTagData('password') or None

    return BookmarkData(jid=jid,
                        name=name,
                        autojoin=autojoin,
                        password=password,
                        nick=nick)


def parse_bookmarks(item, log):
    storage_node = item.getTag('storage', namespace=Namespace.BOOKMARKS)
    if storage_node is None:
        raise MalformedStanzaError('storage node missing', item)

    return parse_storage_node(storage_node, log)


def parse_private_bookmarks(response, log):
    query = response.getQuery()
    storage_node = query.getTag('storage', namespace=Namespace.BOOKMARKS)
    if storage_node is None:
        raise MalformedStanzaError('storage node missing', response)

    return parse_storage_node(storage_node, log)


def parse_storage_node(storage, log):
    bookmarks = []
    confs = storage.getTags('conference')
    for conf in confs:
        try:
            jid = JID.from_string(conf.getAttr('jid'))
        except Exception:
            log.warning('invalid jid: %s', conf)
            continue

        if jid.localpart is None or jid.resource is not None:
            log.warning('invalid jid: %s', conf)
            continue

        autojoin = parse_autojoin(conf.getAttr('autojoin'))
        nick = parse_nickname(conf.getTagData('nick'))
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


def build_conference_node(bookmark):
    attrs = {'xmlns': Namespace.BOOKMARKS_1}
    if bookmark.autojoin:
        attrs['autojoin'] = 'true'
    if bookmark.name:
        attrs['name'] = bookmark.name
    conference = Node(tag='conference', attrs=attrs)
    if bookmark.nick:
        conference.setTagData('nick', bookmark.nick)
    return conference


def build_storage_node(bookmarks):
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


def get_private_request():
    iq = Iq(typ='get')
    query = iq.addChild(name='query', namespace=Namespace.PRIVATE)
    query.addChild(name='storage', namespace=Namespace.BOOKMARKS)
    return iq
