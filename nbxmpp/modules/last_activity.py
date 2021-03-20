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

from nbxmpp.protocol import Iq
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Error
from nbxmpp.protocol import ERR_SERVICE_UNAVAILABLE
from nbxmpp.protocol import ERR_FORBIDDEN
from nbxmpp.namespaces import Namespace
from nbxmpp.task import iq_request_task
from nbxmpp.structs import LastActivityData
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule


class LastActivity(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          priority=60,
                          typ='get',
                          ns=Namespace.LAST),
        ]

        self._idle_func = None
        self._allow_reply_func = None

    def disable(self):
        self._idle_func = None

    def set_idle_func(self, func):
        self._idle_func = func

    def set_allow_reply_func(self, func):
        self._allow_reply_func = func

    @iq_request_task
    def request_last_activity(self, jid):
        _task = yield

        response = yield _make_request(jid)
        if response.isError():
            raise StanzaError(response)

        yield _parse_response(response)

    def _answer_request(self, _client, stanza, _properties):
        self._log.info('Request received from %s', stanza.getFrom())
        if self._idle_func is None:
            self._client.send_stanza(Error(stanza, ERR_SERVICE_UNAVAILABLE))
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(stanza.getFrom()):
                self._client.send_stanza(Error(stanza, ERR_FORBIDDEN))
                raise NodeProcessed

        seconds = self._idle_func()
        iq = stanza.buildReply('result')
        query = iq.getQuery()
        query.setAttr('seconds', seconds)
        self._log.info('Send last activity: %s', seconds)
        self._client.send_stanza(iq)
        raise NodeProcessed


def _make_request(jid):
    return Iq('get', queryNS=Namespace.LAST, to=jid)


def _parse_response(response):
    query = response.getQuery()
    seconds = query.getAttr('seconds')

    try:
        seconds = int(seconds)
    except Exception:
        raise MalformedStanzaError('seconds attribute invalid', response)

    return LastActivityData(seconds=seconds, status=query.getData())
