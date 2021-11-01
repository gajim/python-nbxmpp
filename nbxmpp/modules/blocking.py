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

from __future__ import annotations

from typing import Any
from typing import Generator
from typing import Optional
from typing import Union
from typing import Set

from nbxmpp import types
from nbxmpp.elements import Base

from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.structs import CommonResult, StanzaHandler
from nbxmpp.structs import BlockingPush
from nbxmpp.types import BlockingReportValues
from nbxmpp.builder import Iq
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response


RequestGenerator = Generator[Union[types.Iq, set[JID]], types.Iq, None]
BlockGenerator = Generator[Union[types.Iq, CommonResult], types.Iq, None]


class Blocking(BaseModule):
    def __init__(self, client: types.Client):
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
    def request_blocking_list(self) -> RequestGenerator:

        result = yield _make_blocking_list_request()
        if result.is_error():
            raise StanzaError(result)

        blocklist = result.find_tag('blocklist', namespace=Namespace.BLOCKING)
        if blocklist is None:
            raise MalformedStanzaError('blocklist node missing', result)

        blocked: set[JID] = set()
        for item in blocklist.find_tags('item'):
            try:
                jid = JID.from_string(item.get('jid'))
            except Exception:
                self._log.info('Invalid JID: %s', item.get('jid'))
                continue

            blocked.add(jid)

        self._log.info('Received blocking list: %s', blocked)
        yield blocked

    @iq_request_task
    def block(self,
              jids: list[JID],
              report: Optional[BlockingReportValues] = None) -> BlockGenerator:

        response = yield _make_block_request(jids, report)
        yield process_response(response)

    @iq_request_task
    def unblock(self, jids: list[JID]) -> BlockGenerator:

        response = yield _make_unblock_request(jids)
        yield process_response(response)

    @staticmethod
    def _process_blocking_push(client: types.Client,
                               iq: types.Iq,
                               properties: Any):
        unblock = iq.find_tag('unblock', namespace=Namespace.BLOCKING)
        if unblock is not None:
            properties.blocking = _parse_push(unblock)

        block = iq.find_tag('block', namespace=Namespace.BLOCKING)
        if block is not None:
            properties.blocking = _parse_push(block)

        client.send_stanza(iq.make_result())


def _make_blocking_list_request() -> types.Iq:
    iq = Iq()
    iq.add_tag('blocklist', namespace=Namespace.BLOCKING)
    return iq


def _make_block_request(jids: list[JID],
                        report: Optional[BlockingReportValues]) -> types.Iq:

    iq = Iq(type='set')
    block = iq.add_tag('block', namespace=Namespace.BLOCKING)
    for jid in jids:
        item = block.add_tag('item', jid=str(jid))
        if report is not None:
            action = item.add_tag('report', namespace=Namespace.REPORTING)
            action.add_tag(report)
    return iq


def _make_unblock_request(jids: list[JID]) -> types.Iq:
    iq = Iq(type='set')
    unblock = iq.add_tag('unblock', namespace=Namespace.BLOCKING)
    for jid in jids:
        unblock.add_tag('item', jid=str(jid))
    return iq


def _parse_push(element: Base) -> BlockingPush:
    items = element.find_tags('item')
    if not items:
        return BlockingPush(block=set(), unblock=set(), unblock_all=True)

    jids: Set[JID] = set()
    for item in items:
        jid = item.get('jid')
        if not jid:
            continue

        try:
            jid = JID.from_string(jid)
        except Exception:
            continue

        jids.add(jid)

    block: set[JID] = set()
    unblock: set[JID] = set()

    if element.localname == 'block':
        block = jids
    else:
        unblock = jids

    return BlockingPush(block=block, unblock=unblock, unblock_all=False)
