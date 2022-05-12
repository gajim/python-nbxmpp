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


from nbxmpp.namespaces import Namespace
from nbxmpp.simplexml import Node
from nbxmpp.protocol import Iq
from nbxmpp.protocol import NodeProcessed
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
    def __init__(self, client):
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
    def request_roster(self, version=None):
        _task = yield

        ver_support = self._client.features.has_roster_version()
        if not ver_support:
            version = None

        if ver_support and version is None:
            version = ''

        self._log.info('Roster versioning supported: %s', ver_support)

        response = yield _make_request(version, ver_support)
        if response.isError():
            raise StanzaError(response)

        query = response.getTag('query', namespace=Namespace.ROSTER)
        if query is None:
            if not ver_support:
                raise MalformedStanzaError('query node missing', response)
            yield RosterData(None, version)

        pushed_items, version = self._parse_push(response, ver_support)
        yield RosterData(pushed_items, version)

    def _process_roster_push(self, _client, stanza, properties):
        from_ = stanza.getFrom()
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

        self._ack_roster_push(stanza)

    def _ack_roster_push(self, stanza):
        iq = Iq('result',
                to=stanza.getFrom(),
                frm=stanza.getTo(),
                attrs={'id': stanza.getID()})
        self._client.send_stanza(iq)

    @iq_request_task
    def delete_item(self, jid):
        _task = yield

        response = yield _make_delete(jid)
        yield process_response(response)

    @iq_request_task
    def set_item(self, jid, name, groups=None):
        _task = yield

        response = yield _make_set(jid, name, groups)
        yield process_response(response)

    def _parse_push(self, stanza, ver_support):
        query = stanza.getTag('query', namespace=Namespace.ROSTER)

        version = None
        if ver_support:
            version = query.getAttr('ver')
            if version is None:
                # raise MalformedStanzaError('ver attribute missing', stanza)
                # Prosody sometimes does not send ver attribute with some
                # community modules
                self._log.warning('no version attribute found')

        pushed_items = []
        for item in query.getTags('item'):
            try:
                roster_item = RosterItem.from_node(item)
            except Exception:
                self._log.warning('Invalid roster item')
                self._log.warning(stanza)
                continue

            pushed_items.append(roster_item)

        return pushed_items, version


def _make_delete(jid):
    return Iq('set',
              Namespace.ROSTER,
              payload=[Node('item', {'jid': jid, 'subscription': 'remove'})])


def _make_set(jid, name, groups=None):
    if groups is None:
        groups = []

    infos = {'jid': jid}
    if name:
        infos['name'] = name
    iq = Iq('set', Namespace.ROSTER)
    query = iq.setQuery()
    item = query.addChild('item', attrs=infos)
    for group in groups:
        item.addChild('group').setData(group)
    return iq


def _make_request(version, roster_ver_support):
    iq = Iq('get', Namespace.ROSTER)
    if version is None:
        version = ''

    if roster_ver_support:
        iq.setTagAttr('query', 'ver', version)
    return iq
