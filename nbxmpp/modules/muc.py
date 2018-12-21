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

from nbxmpp.protocol import NS_MUC_USER
from nbxmpp.protocol import NS_MUC
from nbxmpp.util import StanzaHandler

log = logging.getLogger('nbxmpp.m.presence')


class MUC:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._process_muc_presence,
                          ns=NS_MUC,
                          priority=11),
            StanzaHandler(name='presence',
                          callback=self._process_muc_user_presence,
                          ns=NS_MUC_USER,
                          priority=11),
        ]

    def _process_muc_presence(self, _con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC)
        if muc is None:
            return
        properties.from_muc = True

    def _process_muc_user_presence(self, _con, stanza, properties):
        muc = stanza.getTag('x', namespace=NS_MUC_USER)
        if muc is None:
            return
        properties.from_muc = True
