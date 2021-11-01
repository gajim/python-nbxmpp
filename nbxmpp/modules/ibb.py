# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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
from typing import Optional
from typing import Generator
from typing import Union

from nbxmpp import types
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import CommonResult, StanzaHandler
from nbxmpp.structs import IBBData
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.task import iq_request_task
from nbxmpp.const import ErrorCondition
from nbxmpp.const import ErrorType
from nbxmpp.builder import Iq


SetGenerator = Generator[Union[types.Iq, CommonResult], types.Iq, None]


class IBB(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._process_ibb,
                          ns=Namespace.IBB,
                          priority=20),
        ]

    def _process_ibb(self,
                     _client: types.Client,
                     iq: types.Iq,
                     properties: Any):

        if properties.type.is_set:
            open_ = iq.find_tag('open', namespace=Namespace.IBB)
            if open_ is not None:
                properties.ibb = self._parse_open(iq, open_)
                return

            close = iq.find_tag('close', namespace=Namespace.IBB)
            if close is not None:
                properties.ibb = self._parse_close(iq, close)
                return

            data = iq.find_tag('data', namespace=Namespace.IBB)
            if data is not None:
                properties.ibb = self._parse_data(iq, data)
                return

    def _parse_open(self, iq: types.Iq, open_: types.Base) -> IBBData:
        attrs = open_.get_attribs()
        try:
            block_size = int(attrs.get('block-size'))
        except Exception as error:
            self._log.warning(error)
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        if block_size > 65535:
            self._log.warning('Invalid block-size')
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        sid = attrs.get('sid')
        if not sid:
            self._log.warning('Invalid sid')
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        type_ = attrs.get('stanza')
        if type_ == 'message':
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.FEATURE_NOT_IMPLEMENTED,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        return IBBData(type='open', block_size=block_size, sid=sid)

    def _parse_close(self, iq: types.Iq, close: types.Base) -> IBBData:
        sid = close.get_attribs().get('sid')
        if sid is None:
            self._log.warning('Invalid sid')
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed
        return IBBData(type='close', sid=sid)

    def _parse_data(self, iq: types.Iq, data: types.Base) -> IBBData:
        attrs = data.get_attribs()

        sid = attrs.get('sid')
        if sid is None:
            self._log.warning('Invalid sid')
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        try:
            seq = int(attrs.get('seq'))
        except Exception:
            self._log.warning('Invalid seq')
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        try:
            decoded_data = b64decode(data.text or '')
        except Exception:
            self._log.warning('Failed to decode IBB data')
            self._log.warning(iq)
            self._client.send_stanza(
                iq.make_error(ErrorType.CANCEL,
                              ErrorCondition.BAD_REQUEST,
                              Namespace.XMPP_STANZAS))
            raise NodeProcessed

        return IBBData(type='data', sid=sid, seq=seq, data=decoded_data)

    def send_reply(self, iq: types.Iq, error: Optional[str] = None):
        if error is None:
            iq = iq.make_result()
        else:
            iq = iq.make_error(ErrorType.CANCEL,
                               error,
                               Namespace.XMPP_STANZAS)
        self._client.send_stanza(iq)

    @iq_request_task
    def send_open(self, jid: JID, sid: str, block_size: int) -> SetGenerator:

        response = yield _make_ibb_open(jid, sid, block_size)
        yield process_response(response)

    @iq_request_task
    def send_close(self, jid: JID, sid: str) -> SetGenerator:

        response = yield _make_ibb_close(jid, sid)
        yield process_response(response)

    @iq_request_task
    def send_data(self,
                  jid: JID,
                  sid: str,
                  seq: str,
                  data: bytes) -> SetGenerator:


        response = yield _make_ibb_data(jid, sid, seq, data)
        yield process_response(response)


def _make_ibb_open(jid: JID, sid: str, block_size: int) -> types.Iq:
    iq = Iq(to=jid, type='set')
    open_ = iq.add_tag('open', namespace=Namespace.IBB, sid=sid, stanza='iq')
    open_.set('block-size', str(block_size))
    return iq


def _make_ibb_close(jid: JID, sid: str) -> types.Iq:
    iq = Iq(to=jid, type='set')
    iq.add_tag('close', namespace=Namespace.IBB, sid=sid)
    return iq


def _make_ibb_data(jid: JID, sid: str, seq: str, data: bytes) -> types.Iq:
    iq = Iq(to=jid, type='set')
    ibb_data = iq.add_tag('data', namespace=Namespace.IBB, sid=sid, seq=seq)
    ibb_data.text = b64encode(data)
    return iq
