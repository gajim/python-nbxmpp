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

from nbxmpp import types
from nbxmpp.client import Client
from nbxmpp.const import ErrorCondition
from nbxmpp.const import ErrorType
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import Iq
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.base import BaseModule
from nbxmpp.task import iq_request_task
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError


class SoftwareVersion(BaseModule):
    def __init__(self, client: Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          typ='get',
                          priority=60,
                          ns=Namespace.VERSION),
        ]

        self._name = None
        self._version = None
        self._os = None

        self._enabled = False
        self._allow_reply_func = None

    def disable(self):
        self._enabled = False

    def set_allow_reply_func(self, func: Any):
        self._allow_reply_func = func

    @iq_request_task
    def request_software_version(self, jid: JID):

        response = yield _make_query(jid)
        if response.is_error():
            raise StanzaError(response)

        yield _parse_info(response)

    def set_software_version(self,
                             name: str,
                             version: str,
                             os: Optional[str] = None):

        self._name, self._version, self._os = name, version, os
        self._enabled = True

    def _answer_request(self,
                        _client: Client,
                        stanza: types.Iq,
                        _properties: Any):

        self._log.info('Request received from %s', stanza.get_from())
        if (not self._enabled or
                self._name is None or
                self._version is None):

            iq = stanza.make_error(ErrorType.CANCEL,
                                   ErrorCondition.SERVICE_UNAVAILABLE,
                                   Namespace.XMPP_STANZAS)

            self._client.send_stanza(iq)
            raise NodeProcessed

        if self._allow_reply_func is not None:
            if not self._allow_reply_func(stanza.get_from()):

                iq = stanza.make_error(ErrorType.CANCEL,
                                       ErrorCondition.FORBIDDEN,
                                       Namespace.XMPP_STANZAS)

                self._client.send_stanza(iq)
                raise NodeProcessed

        result = stanza.make_result()
        query = result.add_query(namespace=Namespace.VERSION)
        query.add_tag_text('name', self._name)
        query.add_tag_text('version', self._version)
        if self._os is not None:
            query.add_tag_text('os', self._os)

        self._log.info('Send software version: %s %s %s',
                       self._name, self._version, self._os)

        self._client.send_stanza(result)
        raise NodeProcessed


def _make_query(jid: JID) -> types.Iq:
    iq = Iq(to=jid)
    iq.add_query(namespace=Namespace.VERSION)
    return iq


def _parse_info(stanza: types.Iq) -> SoftwareVersionResult:
    query = stanza.get_query(namespace=Namespace.VERSION)
    if query is None:
        raise MalformedStanzaError('query node missing', stanza)

    name = query.find_tag_text('name')
    if name is None:
        raise MalformedStanzaError('name missing', stanza)

    version = query.find_tag_text('version')
    if version is None:
        raise MalformedStanzaError('version missing', stanza)

    os = query.find_tag_text('os') or ''

    return SoftwareVersionResult(name, version, os)
