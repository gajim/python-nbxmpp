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
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import RosterData
from nbxmpp.structs import RosterItem
# from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import StanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response


class Roster(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            # StanzaHandler(name='iq',
            #               callback=self._process_roster_push,
            #               typ='set',
            #               priority=15,
            #               ns=Namespace.ROSTER),
        ]

    @iq_request_task
    def request_roster(self, version=None):
        _task = yield

        self._log.info('Request Roster, version: %s', version)
        response = yield _make_request(version)
        if response.isError():
            raise StanzaError(response)

        yield _parse_push(response)

    def _process_roster_push(self, _client, stanza, properties):
        from_ = stanza.getFrom()
        if from_ is not None:
            if not self._con.get_bound_jid().bare == from_:
                self._log.warning('Malicious Roster Push from %s', from_)
                raise NodeProcessed

        properties.roster = _parse_push(stanza)

        self._log.info('Roster Push, version: %s', properties.roster.version)
        for item in properties.roster.items:
            self._log.info(item)

        self._ack_roster_push(stanza)

    def _ack_roster_push(self, stanza):
        iq = Iq('result',
                to=stanza.getFrom(),
                frm=stanza.getTo(),
                attrs={'id': stanza.getID()})
        self._con.send_stanza(iq)

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


def _make_request(version):
    iq = Iq('get', Namespace.ROSTER)
    if version is not None:
        iq.setTagAttr('query', 'ver', version)
    return iq


def _get_item_attrs(item):
    default_attrs = {'name': None,
                     'ask': None,
                     'subscription': None,
                     'groups': []}

    attrs = item.getAttrs()
    del attrs['jid']
    groups = {group.getData() for group in item.getTags('group')}
    attrs['groups'] = list(groups)

    default_attrs.update(attrs)
    return default_attrs


def _parse_push(stanza):
    query = stanza.getTag('query', namespace=Namespace.ROSTER)
    version = query.getAttr('ver')
    pushed_items = []

    for item in query.getTags('item'):
        jid = JID.from_string(item.getAttr('jid'))
        attrs = _get_item_attrs(item)
        pushed_items.append(RosterItem(attrs, jid))

    return RosterData(pushed_items, version)
