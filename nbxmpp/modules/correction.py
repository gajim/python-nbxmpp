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

from __future__ import annotations

from typing import Any

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import CorrectionData
from nbxmpp.modules.base import BaseModule


class Correction(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_correction,
                          ns=Namespace.CORRECT,
                          priority=15),
        ]

    def _process_message_correction(self,
                                    _client: types.Client,
                                    stanza: types.Message,
                                    properties: Any):

        replace = stanza.find_tag('replace', namespace=Namespace.CORRECT)
        if replace is None:
            return

        id_ = replace.get('id')
        if id_ is None:
            self._log.warning('Correcton without id attribute')
            self._log.warning(stanza)
            return

        if stanza.get('id') == id_:
            self._log.warning('correcton id == message id')
            self._log.warning(stanza)
            return

        properties.correction = CorrectionData(id_)
