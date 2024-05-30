# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.bits_of_binary import parse_bob_data
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import CaptchaData
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Captcha(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_captcha,
                ns=Namespace.CAPTCHA,
                priority=40,
            ),
        ]

    def _process_captcha(
        self, _client: Client, stanza: Message, properties: MessageProperties
    ) -> None:
        captcha = stanza.getTag("captcha", namespace=Namespace.CAPTCHA)
        if captcha is None:
            return

        data_form = captcha.getTag("x", namespace=Namespace.DATA)
        if data_form is None:
            self._log.warning("Invalid captcha form")
            self._log.warning(stanza)
            return

        form = extend_form(node=data_form)
        bob_data = parse_bob_data(stanza)

        properties.captcha = CaptchaData(form=form, bob_data=bob_data)
