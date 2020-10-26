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

from nbxmpp.protocol import Iq
from nbxmpp.protocol import NodeProcessed
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response


class Ping(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_ping,
                          typ='get',
                          ns=Namespace.PING,
                          priority=15),
        ]

    def _process_ping(self, _client, stanza, properties):
        self._log.info('Send pong to %s', stanza.getFrom())
        iq = stanza.buildSimpleReply('result')
        self._client.send_stanza(iq)
        raise NodeProcessed

    @iq_request_task
    def ping(self, jid):
        _task = yield

        self._log.info('Ping')
        response = yield _make_ping_request(jid)
        yield process_response(response)


def _make_ping_request(jid):
    iq = Iq('get', to=jid)
    iq.addChild(name='ping', namespace=Namespace.PING)
    return iq
