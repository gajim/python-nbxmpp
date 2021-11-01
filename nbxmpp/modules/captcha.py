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
from nbxmpp.structs import CaptchaData

from nbxmpp.modules.bits_of_binary import parse_bob_data
from nbxmpp.modules.base import BaseModule


class Captcha(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_captcha,
                          ns=Namespace.CAPTCHA,
                          priority=40),
        ]

    def _process_captcha(self,
                         _client: types.Client,
                         message: types.Message,
                         properties: Any):

        captcha = message.find_tag('captcha', namespace=Namespace.CAPTCHA)
        if captcha is None:
            return

        data_form = captcha.find_tag('x', namespace=Namespace.DATA)
        if data_form is None:
            self._log.warning('Invalid captcha form')
            self._log.warning(message)
            return

        bob_data = parse_bob_data(message)

        properties.captcha = CaptchaData(form=data_form,
                                         bob_data=bob_data)
