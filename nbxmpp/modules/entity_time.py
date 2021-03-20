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
from nbxmpp.protocol import ERR_FORBIDDEN
from nbxmpp.protocol import ERR_SERVICE_UNAVAILABLE
from nbxmpp.namespaces import Namespace
from nbxmpp.task import iq_request_task
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule

from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.date_and_time import create_tzinfo
from nbxmpp.modules.date_and_time import get_local_time


class EntityTime(BaseModule):
    def __init__(self, client):
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
        self._allow_reply_func = None

    def disable(self):
        self._enabled = False

    def enable(self):
        self._enabled = True

    def set_allow_reply_func(self, func):
        self._allow_reply_func = func

    @iq_request_task
    def request_entity_time(self, jid):
        _task = yield

        response = yield _make_request(jid)
        if response.isError():
            raise StanzaError(response)

        yield _parse_response(response)

    def _answer_request(self, _con, stanza, _properties):
        self._log.info('Request received from %s', stanza.getFrom())
        if not self._enabled:
            self._client.send_stanza(Error(stanza, ERR_SERVICE_UNAVAILABLE))
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(stanza.getFrom()):
                self._client.send_stanza(Error(stanza, ERR_FORBIDDEN))
                raise NodeProcessed

        time, tzo = get_local_time()
        iq = stanza.buildSimpleReply('result')
        time_node = iq.addChild('time', namespace=Namespace.TIME)
        time_node.setTagData('utc', time)
        time_node.setTagData('tzo', tzo)
        self._log.info('Send time: %s %s', time, tzo)
        self._client.send_stanza(iq)
        raise NodeProcessed


def _make_request(jid):
    iq = Iq('get', to=jid)
    iq.addChild('time', namespace=Namespace.TIME)
    return iq


def _parse_response(response):
    time_ = response.getTag('time')
    if not time_:
        raise MalformedStanzaError('time node missing', response)

    tzo = time_.getTagData('tzo')
    if not tzo:
        raise MalformedStanzaError('tzo node or data missing', response)

    remote_tz = create_tzinfo(tz_string=tzo)
    if remote_tz is None:
        raise MalformedStanzaError('invalid tzo data', response)

    utc_time = time_.getTagData('utc')
    if not utc_time:
        raise MalformedStanzaError('utc node or data missing', response)

    date_time = parse_datetime(utc_time, check_utc=True)
    if date_time is None:
        raise MalformedStanzaError('invalid timezone definition', response)

    date_time = date_time.astimezone(remote_tz)
    return date_time.strftime('%c %Z')
