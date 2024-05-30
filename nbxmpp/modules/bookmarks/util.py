# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from nbxmpp.errors import MalformedStanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import Node
from nbxmpp.protocol import validate_resourcepart
from nbxmpp.structs import BookmarkData
from nbxmpp.util import from_xs_boolean
from nbxmpp.util import to_xs_boolean


def parse_nickname(nick: str | None) -> str | None:
    if nick is None:
        return None

    try:
        return validate_resourcepart(nick)
    except Exception:
        return None


def parse_autojoin(autojoin: str | None) -> bool:
    if autojoin is None:
        return False

    try:
        return from_xs_boolean(autojoin)
    except ValueError:
        return False


def parse_bookmark(item: Node) -> BookmarkData:
    conference = item.getTag("conference", namespace=Namespace.BOOKMARKS_1)
    if conference is None:
        raise MalformedStanzaError("conference node missing", item)

    try:
        jid = JID.from_string(item.getAttr("id"))
    except Exception as error:
        raise MalformedStanzaError("invalid jid: %s" % error, item)

    if jid.localpart is None or jid.resource is not None:
        raise MalformedStanzaError("invalid jid", item)

    autojoin = parse_autojoin(conference.getAttr("autojoin"))
    nick = parse_nickname(conference.getTagData("nick"))
    name = conference.getAttr("name") or None
    password = conference.getTagData("password") or None
    extensions = conference.getTag("extensions")

    return BookmarkData(
        jid=jid,
        name=name,
        nick=nick,
        autojoin=autojoin,
        password=password,
        extensions=extensions,
    )


def parse_bookmarks(item: Node, log: logging.Logger) -> list[BookmarkData]:
    storage_node = item.getTag("storage", namespace=Namespace.BOOKMARKS)
    if storage_node is None:
        raise MalformedStanzaError("storage node missing", item)

    return parse_storage_node(storage_node, log)


def parse_private_bookmarks(response: Node, log: logging.Logger) -> list[BookmarkData]:
    query = response.getQuery()
    storage_node = query.getTag("storage", namespace=Namespace.BOOKMARKS)
    if storage_node is None:
        raise MalformedStanzaError("storage node missing", response)

    return parse_storage_node(storage_node, log)


def parse_storage_node(storage: Node, log: logging.Logger) -> list[BookmarkData]:
    bookmarks: list[BookmarkData] = []
    confs = storage.getTags("conference")
    for conf in confs:
        try:
            jid = JID.from_string(conf.getAttr("jid"))
        except Exception:
            log.warning("invalid jid: %s", conf)
            continue

        if jid.localpart is None or jid.resource is not None:
            log.warning("invalid jid: %s", conf)
            continue

        autojoin = parse_autojoin(conf.getAttr("autojoin"))
        nick = parse_nickname(conf.getTagData("nick"))
        name = conf.getAttr("name") or None
        password = conf.getTagData("password") or None

        bookmark = BookmarkData(
            jid=jid, name=name, autojoin=autojoin, password=password, nick=nick
        )
        bookmarks.append(bookmark)

    return bookmarks


def build_conference_node(bookmark: BookmarkData):
    attrs = {"xmlns": Namespace.BOOKMARKS_1}
    if bookmark.autojoin:
        attrs["autojoin"] = "true"
    if bookmark.name:
        attrs["name"] = bookmark.name
    conference = Node(tag="conference", attrs=attrs)
    if bookmark.nick:
        conference.setTagData("nick", bookmark.nick)
    if bookmark.password:
        conference.setTagData("password", bookmark.password)
    if bookmark.extensions is not None:
        conference.addChild(node=bookmark.extensions)
    return conference


def build_storage_node(bookmarks: list[BookmarkData]):
    storage_node = Node(tag="storage", attrs={"xmlns": Namespace.BOOKMARKS})
    for bookmark in bookmarks:
        conf_node = storage_node.addChild(name="conference")
        conf_node.setAttr("jid", bookmark.jid)
        conf_node.setAttr("autojoin", to_xs_boolean(bookmark.autojoin))
        if bookmark.name:
            conf_node.setAttr("name", bookmark.name)
        if bookmark.nick:
            conf_node.setTagData("nick", bookmark.nick)
        if bookmark.password:
            conf_node.setTagData("password", bookmark.password)
    return storage_node


def get_private_request() -> Iq:
    iq = Iq(typ="get")
    query = iq.addChild(name="query", namespace=Namespace.PRIVATE)
    query.addChild(name="storage", namespace=Namespace.BOOKMARKS)
    return iq
