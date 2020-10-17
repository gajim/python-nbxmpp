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
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.modules.base import BaseModule
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.structs import BlockingPush
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.util import process_response


class Blocking(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          priority=15,
                          callback=self._process_blocking_push,
                          typ='set',
                          ns=Namespace.BLOCKING),
        ]

    @iq_request_task
    def request_blocking_list(self):
        _task = yield

        result = yield _make_blocking_list_request()
        if result.isError():
            raise StanzaError(result)

        blocklist = result.getTag('blocklist', namespace=Namespace.BLOCKING)
        if blocklist is None:
            raise MalformedStanzaError('blocklist node missing', result)

        blocked = []
        for item in blocklist.getTags('item'):
            blocked.append(item.getAttr('jid'))

        self._log.info('Received blocking list: %s', blocked)
        yield blocked

    @iq_request_task
    def block(self, jids, report=None):
        _task = yield

        self._log.info('Block: %s', jids)

        response = yield _make_block_request(jids, report)
        yield process_response(response)

    @iq_request_task
    def unblock(self, jids):
        _task = yield

        self._log.info('Unblock: %s', jids)

        response = yield _make_unblock_request(jids)
        yield process_response(response)

    @staticmethod
    def _process_blocking_push(client, stanza, properties):
        unblock = stanza.getTag('unblock', namespace=Namespace.BLOCKING)
        if unblock is not None:
            properties.blocking = _parse_push(unblock)
            return

        block = stanza.getTag('block', namespace=Namespace.BLOCKING)
        if block is not None:
            properties.blocking = _parse_push(block)

        reply = stanza.buildSimpleReply('result')
        client.send_stanza(reply)


def _make_blocking_list_request():
    iq = Iq('get', Namespace.BLOCKING)
    iq.setQuery('blocklist')
    return iq


def _make_block_request(jids, report):
    iq = Iq('set', Namespace.BLOCKING)
    query = iq.setQuery(name='block')
    for jid in jids:
        item = query.addChild(name='item', attrs={'jid': jid})
        if report in ('spam', 'abuse'):
            action = item.addChild(name='report',
                                   namespace=Namespace.REPORTING)
            action.setTag(report)
    return iq


def _make_unblock_request(jids):
    iq = Iq('set', Namespace.BLOCKING)
    query = iq.setQuery(name='unblock')
    for jid in jids:
        query.addChild(name='item', attrs={'jid': jid})
    return iq


def _parse_push(node):
    items = node.getTags('item')
    if not items:
        return BlockingPush(block=[], unblock=[], unblock_all=True)

    jids = []
    for item in items:
        jid = item.getAttr('jid')
        if not jid:
            continue

        try:
            jid = JID.from_string(jid)
        except Exception:
            continue

        jids.append(jid)


    block, unblock = [], []
    if node.getName() == 'block':
        block = jids
    else:
        unblock = jids

    return BlockingPush(block=block, unblock=unblock, unblock_all=False)
