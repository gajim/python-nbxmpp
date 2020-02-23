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

import logging

from nbxmpp.protocol import NS_VERSION
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import ErrorNode
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import ERR_SERVICE_UNAVAILABLE
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error

log = logging.getLogger('nbxmpp.m.software_version')


class SoftwareVersion:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          typ='get',
                          ns=NS_VERSION),
        ]

        self._name = None
        self._version = None
        self._os = None

        self._enabled = False

    def disable(self):
        self._enabled = False

    @call_on_response('_software_version_received')
    def request_software_version(self, jid):
        log.info('Request software version for %s', jid)
        return Iq(typ='get', to=jid, queryNS=NS_VERSION)

    @callback
    def _software_version_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        try:
            return SoftwareVersionResult(*self._parse_info(stanza))
        except Exception as error:
            log.warning(error)
            return raise_error(log.warning, stanza, 'stanza-malformed')

    @staticmethod
    def _parse_info(stanza):
        name = stanza.getQueryChild('name').getData()
        version = stanza.getQueryChild('version').getData()

        os_info = stanza.getQueryChild('os')
        if os_info is not None:
            os_info = os_info.getData()

        return name, version, os_info

    def set_software_version(self, name, version, os=None):
        self._name, self._version, self._os = name, version, os
        self._enabled = True

    def _answer_request(self, _con, stanza, _properties):
        log.info('Request received from %s', stanza.getFrom())
        if (not self._enabled or
                self._name is None or
                self._version is None):
            iq = stanza.buildReply('error')
            iq.addChild(node=ErrorNode(ERR_SERVICE_UNAVAILABLE))
            log.info('Send service-unavailable')

        else:
            iq = stanza.buildReply('result')
            query = iq.getQuery()
            query.setTagData('name', self._name)
            query.setTagData('version', self._version)
            if self._os is not None:
                query.setTagData('os', self._os)
            log.info('Send software version: %s %s %s',
                     self._name, self._version, self._os)

        self._client.send_stanza(iq)
        raise NodeProcessed
