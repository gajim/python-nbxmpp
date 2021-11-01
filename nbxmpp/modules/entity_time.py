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
from typing import Optional
from typing import Union

from nbxmpp import types
from nbxmpp.builder import Iq
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.jid import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.task import iq_request_task
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.const import ErrorCondition
from nbxmpp.const import ErrorType

from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.date_and_time import create_tzinfo
from nbxmpp.modules.date_and_time import get_local_time


RequestGenerator = Generator[Union[types.Iq, str], types.Iq, None]


class EntityTime(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          priority=60,
                          typ='get',
                          ns=Namespace.TIME),
        ]

        self._enabled = False
        self._allow_reply_func: Optional[Any] = None

    def disable(self):
        self._enabled = False

    def enable(self):
        self._enabled = True

    def set_allow_reply_func(self, func: Any):
        self._allow_reply_func = func

    @iq_request_task
    def request_entity_time(self, jid: JID) -> RequestGenerator:

        response = yield _make_request(jid)
        if response.is_error():
            raise StanzaError(response)

        yield _parse_response(response)

    def _answer_request(self,
                        _client: types.Client,
                        iq: types.Iq,
                        _properties: Any):

        self._log.info('Request received from %s', iq.get_from())
        if not self._enabled:
            error = iq.make_error(ErrorType.CANCEL,
                                  ErrorCondition.SERVICE_UNAVAILABLE,
                                  Namespace.XMPP_STANZAS)
            self._client.send_stanza(error)
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(iq.get_from()):
                error = iq.make_error(ErrorType.CANCEL,
                                      ErrorCondition.FORBIDDEN,
                                      Namespace.XMPP_STANZAS)
                self._client.send_stanza(error)
                raise NodeProcessed

        time, tzo = get_local_time()
        result = iq.make_result()
        time_node = result.add_tag('time', namespace=Namespace.TIME)
        time_node.add_tag_text('utc', time)
        time_node.add_tag_text('tzo', tzo)
        self._log.info('Send time: %s %s', time, tzo)
        self._client.send_stanza(result)
        raise NodeProcessed


def _make_request(jid: JID):
    iq = Iq(to=jid)
    iq.add_tag('time', namespace=Namespace.TIME)
    return iq


def _parse_response(response: types.Iq) -> str:
    time_ = response.find_tag('time')
    if not time_:
        raise MalformedStanzaError('time node missing', response)

    tzo = time_.find_tag_text('tzo')
    if not tzo:
        raise MalformedStanzaError('tzo node or data missing', response)

    remote_tz = create_tzinfo(tz_string=tzo)
    if remote_tz is None:
        raise MalformedStanzaError('invalid tzo data', response)

    utc_time = time_.find_tag_text('utc')
    if not utc_time:
        raise MalformedStanzaError('utc node or data missing', response)

    date_time = parse_datetime(utc_time, check_utc=True)
    if date_time is None:
        raise MalformedStanzaError('invalid timezone definition', response)

    date_time = date_time.astimezone(remote_tz)
    return date_time.strftime('%c %Z')
