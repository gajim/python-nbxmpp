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

from nbxmpp.protocol import NS_CAPTCHA
from nbxmpp.protocol import NS_DATA
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import CaptchaData
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.bits_of_binary import parse_bob_data

log = logging.getLogger('nbxmpp.m.captcha')


class Captcha:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_captcha,
                          ns=NS_CAPTCHA,
                          priority=40),
        ]

    @staticmethod
    def _process_captcha(_con, stanza, properties):
        captcha = stanza.getTag('captcha', namespace=NS_CAPTCHA)
        if captcha is None:
            return

        data_form = captcha.getTag('x', namespace=NS_DATA)
        if data_form is None:
            log.warning('Invalid captcha form')
            log.warning(stanza)
            return

        form = extend_form(node=data_form)
        bob_data = parse_bob_data(stanza)

        properties.captcha = CaptchaData(form=form,
                                         bob_data=bob_data)
