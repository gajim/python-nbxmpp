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
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import BlockingListResult
from nbxmpp.structs import CommonResult
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.base import BaseModule


class Blocking(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @call_on_response('_blocking_list_received')
    def get_blocking_list(self):
        iq = Iq('get', Namespace.BLOCKING)
        iq.setQuery('blocklist')
        return iq

    @callback
    def _blocking_list_received(self, stanza):
        blocked = []
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        blocklist = stanza.getTag('blocklist', namespace=Namespace.BLOCKING)
        if blocklist is None:
            return raise_error(self._log.warning, stanza, 'stanza-malformed')

        for item in blocklist.getTags('item'):
            blocked.append(item.getAttr('jid'))

        self._log.info('Received blocking list: %s', blocked)
        return BlockingListResult(blocking_list=blocked)

    @call_on_response('_default_response')
    def block(self, jids):
        self._log.info('Block: %s', jids)
        iq = Iq('set', Namespace.BLOCKING)
        query = iq.setQuery(name='block')
        for jid in jids:
            query.addChild(name='item', attrs={'jid': jid})
        return iq

    @call_on_response('_default_response')
    def unblock(self, jids):
        self._log.info('Unblock: %s', jids)
        iq = Iq('set', Namespace.BLOCKING)
        query = iq.setQuery(name='unblock')
        for jid in jids:
            query.addChild(name='item', attrs={'jid': jid})
        return iq

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return CommonResult(jid=stanza.getFrom())
