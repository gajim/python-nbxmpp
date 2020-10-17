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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import ErrorNode
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import ERR_SERVICE_UNAVAILABLE
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.base import BaseModule
from nbxmpp.task import iq_request_task
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError


class SoftwareVersion(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          typ='get',
                          ns=Namespace.VERSION),
        ]

        self._name = None
        self._version = None
        self._os = None

        self._enabled = False

    def disable(self):
        self._enabled = False

    @iq_request_task
    def request_software_version(self, jid):
        _task = yield

        self._log.info('Request software version for %s', jid)

        response = yield Iq(typ='get', to=jid, queryNS=Namespace.VERSION)
        if response.isError():
            raise StanzaError(response)

        yield _parse_info(response)

    def set_software_version(self, name, version, os=None):
        self._name, self._version, self._os = name, version, os
        self._enabled = True

    def _answer_request(self, _con, stanza, _properties):
        self._log.info('Request received from %s', stanza.getFrom())
        if (not self._enabled or
                self._name is None or
                self._version is None):
            iq = stanza.buildReply('error')
            iq.addChild(node=ErrorNode(ERR_SERVICE_UNAVAILABLE))
            self._log.info('Send service-unavailable')

        else:
            iq = stanza.buildReply('result')
            query = iq.getQuery()
            query.setTagData('name', self._name)
            query.setTagData('version', self._version)
            if self._os is not None:
                query.setTagData('os', self._os)
            self._log.info('Send software version: %s %s %s',
                           self._name, self._version, self._os)

        self._client.send_stanza(iq)
        raise NodeProcessed


def _parse_info(stanza):
    try:
        name = stanza.getQueryChild('name').getData()
    except Exception:
        raise MalformedStanzaError('name node missing', stanza)

    try:
        version = stanza.getQueryChild('version').getData()
    except Exception:
        raise MalformedStanzaError('version node missing', stanza)

    os_info = stanza.getQueryChild('os')
    if os_info is not None:
        os_info = os_info.getData()

    return SoftwareVersionResult(name, version, os_info)
