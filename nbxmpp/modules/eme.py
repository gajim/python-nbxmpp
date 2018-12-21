# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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

from nbxmpp.protocol import NS_EME
from nbxmpp.util import StanzaHandler

log = logging.getLogger('nbxmpp.m.eme')


class EME:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_eme,
                          ns=NS_EME,
                          priority=40)
        ]

    @staticmethod
    def _process_eme(_con, stanza, properties):
        enc_tag = stanza.getTag('encryption', namespace=NS_EME)
        if enc_tag is None:
            return

        ns = enc_tag.getAttr('namespace')
        if ns is None:
            log.warning('No namespace on message')
            return

        properties.eme = {}
        properties.eme['namespace'] = ns
        properties.eme['name'] = enc_tag.getAttr('name')
        log.info('Found data: %s', properties.eme)
