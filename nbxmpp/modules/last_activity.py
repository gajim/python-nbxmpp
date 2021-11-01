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
from typing import Generator
from typing import Union

from nbxmpp import types
from nbxmpp.builder import Iq
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.namespaces import Namespace
from nbxmpp.task import iq_request_task
from nbxmpp.structs import LastActivityData
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.const import ErrorType
from nbxmpp.const import ErrorCondition


RequestGenerator = Generator[Union[types.Iq, LastActivityData], types.Iq, None]


class LastActivity(BaseModule):
    def __init__(self, client: types.Client):
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

    def set_idle_func(self, func: Any):
        self._idle_func = func

    def set_allow_reply_func(self, func: Any):
        self._allow_reply_func = func

    @iq_request_task
    def request_last_activity(self, jid: JID) -> RequestGenerator:

        response = yield _make_request(jid)
        if response.is_error():
            raise StanzaError(response)

        yield _parse_response(response)

    def _answer_request(self,
                        _client: types.Client,
                        iq: types.Iq,
                        _properties: Any):

        self._log.info('Request received from %s', iq.get_from())
        if self._idle_func is None:
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.SERVICE_UNAVAILABLE,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(iq.get_from()):
                self._client.send_stanza(iq.make_error(ErrorType.CANCEL,
                                                       ErrorCondition.FORBIDDEN,
                                                       Namespace.XMPP_STANZAS))
                raise NodeProcessed

        seconds = self._idle_func()
        result = iq.make_result()
        query = result.add_query(namespace=Namespace.LAST)
        query.set('seconds', seconds)

        self._log.info('Send last activity: %s', seconds)
        self._client.send_stanza(result)
        raise NodeProcessed


def _make_request(jid: JID) -> types.Iq:
    iq = Iq(to=jid)
    iq.add_query(namespace=Namespace.LAST)
    return iq


def _parse_response(response: types.Iq) -> LastActivityData:
    query = response.get_query(namespace=Namespace.LAST)
    if query is None:
        raise MalformedStanzaError('query element missing', response)

    try:
        seconds = int(query.get('seconds'))
    except Exception:
        raise MalformedStanzaError('seconds attribute invalid', response)

    return LastActivityData(seconds=seconds, status=query.text or '')
