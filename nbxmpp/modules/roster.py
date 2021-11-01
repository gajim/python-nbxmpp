# Copyright (C) 2021 Philipp Hörist <philipp AT hoerist.com>
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

from typing import Any
from typing import Optional

from nbxmpp import types
from nbxmpp.client import Client
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import Iq
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import RosterData
from nbxmpp.structs import RosterItem
from nbxmpp.structs import RosterPush
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response


class Roster(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_roster_push,
                          typ='set',
                          priority=15,
                          ns=Namespace.ROSTER),
        ]

    @iq_request_task
    def request_roster(self, version: Optional[str] = None):

        ver_support = self._client.features.has_roster_version()
        if not ver_support:
            version = None

        if ver_support and version is None:
            version = ''

        self._log.info('Roster versioning supported: %s', ver_support)

        response = yield _make_request(version, ver_support)
        if response.is_error():
            raise StanzaError(response)

        query = response.find_tag('query', namespace=Namespace.ROSTER)
        if query is None:
            if not ver_support:
                raise MalformedStanzaError('query node missing', response)
            yield RosterData(None, version)

        pushed_items, version = self._parse_push(response, ver_support)
        yield RosterData(pushed_items, version)

    def _process_roster_push(self,
                             _client: Client,
                             stanza: types.Iq,
                             properties: Any):

        from_ = stanza.get_from()
        if from_ is not None:
            if not self._client.get_bound_jid().bare == from_:
                self._log.warning('Malicious Roster Push from %s', from_)
                raise NodeProcessed

        ver_support = self._client.features.has_roster_version()
        pushed_items, version = self._parse_push(stanza, ver_support)
        if len(pushed_items) != 1:
            self._log.warning('Roster push contains more than one item')
            self._log.warning(stanza)
            raise NodeProcessed

        item = pushed_items[0]
        properties.roster = RosterPush(item, version)

        self._log.info('Roster Push, version: %s', properties.roster.version)
        self._log.info(item)

        self._client.send_stanza(stanza.make_result())

    @iq_request_task
    def delete_item(self, jid: JID):

        response = yield _make_delete(jid)
        yield process_response(response)

    @iq_request_task
    def set_item(self, jid: JID, name: str, groups: Optional[list[str]] = None):

        response = yield _make_set(jid, name, groups)
        yield process_response(response)

    def _parse_push(self,
                    stanza: types.Iq,
                    ver_support: bool) -> tuple[list[RosterItem],
                                                Optional[str]]:

        query = stanza.find_tag('query', namespace=Namespace.ROSTER)
        if query is None:
            raise MalformedStanzaError('query tag missing', stanza)

        version = None
        if ver_support:
            version = query.get('ver')
            if version is None:
                raise MalformedStanzaError('ver attribute missing', stanza)

        pushed_items: list[RosterItem] = []
        for item in query.find_tags('item'):
            try:
                roster_item = RosterItem.from_node(item)
            except Exception:
                self._log.warning('Invalid roster item')
                self._log.warning(stanza)
                continue

            pushed_items.append(roster_item)

        return pushed_items, version


def _make_delete(jid: JID) -> types.Iq:
    iq = Iq(type='set')
    query = iq.add_query(namespace=Namespace.ROSTER)
    query.add_tag('item', jid=str(jid), subscription='remove')
    return iq


def _make_set(jid: JID, name: str, groups: Optional[list[str]] = None):
    iq = Iq(type='set')
    query = iq.add_query(namespace=Namespace.ROSTER)
    item = query.add_tag('item', jid=str(jid))
    if name:
        item.set('name', name)

    if groups is not None:
        for group in groups:
            item.add_tag_text('group', group)

    return iq


def _make_request(version: Optional[str],
                  roster_ver_support: bool) -> types.Iq:
    iq = Iq()
    query = iq.add_query(namespace=Namespace.ROSTER)

    if not roster_ver_support:
        return iq

    if version is None:
        version = ''

    query.set('ver', version)
    return iq
