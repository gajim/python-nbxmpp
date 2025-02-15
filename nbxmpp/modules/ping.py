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

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Ping(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_ping,
                          typ='get',
                          ns=Namespace.PING,
                          priority=15),
        ]

    def _process_ping(self, _client: Client, stanza: Iq, _properties: IqProperties) -> None:
        self._log.info('Send pong to %s', stanza.getFrom())
        iq = stanza.buildSimpleReply('result')
        self._client.send_stanza(iq)
        raise NodeProcessed

    @iq_request_task
    def ping(self, jid: JID):
        _task = yield

        response = yield _make_ping_request(jid)
        yield process_response(response)


def _make_ping_request(jid: JID) -> Iq:
    iq = Iq('get', to=jid)
    iq.addChild(name='ping', namespace=Namespace.PING)
    return iq
