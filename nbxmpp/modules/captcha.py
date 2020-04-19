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

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import CaptchaData
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.bits_of_binary import parse_bob_data
from nbxmpp.modules.base import BaseModule


class Captcha(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_captcha,
                          ns=Namespace.CAPTCHA,
                          priority=40),
        ]

    def _process_captcha(self, _client, stanza, properties):
        captcha = stanza.getTag('captcha', namespace=Namespace.CAPTCHA)
        if captcha is None:
            return

        data_form = captcha.getTag('x', namespace=Namespace.DATA)
        if data_form is None:
            self._log.warning('Invalid captcha form')
            self._log.warning(stanza)
            return

        form = extend_form(node=data_form)
        bob_data = parse_bob_data(stanza)

        properties.captcha = CaptchaData(form=form,
                                         bob_data=bob_data)
