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

import logging

from nbxmpp.protocol import NS_REGISTER
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import CommonResult
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error

log = logging.getLogger('nbxmpp.m.register')


class Register:
    def __init__(self, client):
        self._client = client
        self.handlers = []

    @call_on_response('_default_response')
    def unregister(self):
        hostname = self._client.get_bound_jid().getDomain()
        iq = Iq('set', to=hostname)
        query = iq.setQuery()
        query.setNamespace(NS_REGISTER)
        query.addChild('remove')
        return iq

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)
        return CommonResult(jid=stanza.getFrom())
