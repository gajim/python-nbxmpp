# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from nbxmpp.errors import ChangePasswordStanzaError
from nbxmpp.errors import RegisterStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.register.util import _make_password_change_request
from nbxmpp.modules.register.util import _make_password_change_with_form
from nbxmpp.modules.register.util import _make_register_form
from nbxmpp.modules.register.util import _make_unregister_request
from nbxmpp.modules.register.util import _parse_register_data
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.task import iq_request_task
from nbxmpp.util import get_form

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Register(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def unregister(self, jid: JID | None = None):
        _task = yield

        response = yield _make_unregister_request(jid)
        yield process_response(response)

    @iq_request_task
    def request_register_form(self, jid: JID | None = None):
        _task = yield

        if jid is None:
            jid = self._client.domain

        response = yield Iq("get", Namespace.REGISTER, to=jid)
        if response.isError():
            raise StanzaError(response)

        yield _parse_register_data(response)

    @iq_request_task
    def submit_register_form(self, form, jid: JID | None = None):
        _task = yield

        if jid is None:
            jid = self._client.domain

        response = yield _make_register_form(jid, form)
        if not response.isError():
            yield process_response(response)

        else:
            data = _parse_register_data(response)
            raise RegisterStanzaError(response, data)

    @iq_request_task
    def change_password(self, password: str):
        _task = yield

        response = yield _make_password_change_request(
            self._client.domain, self._client.username, password
        )
        if not response.isError():
            yield process_response(response)

        else:
            query = response.getQuery()
            if query is None:
                raise StanzaError(response)

            form = get_form(query, "jabber:iq:register:changepassword")
            if form is None or response.getType() != "modify":
                raise StanzaError(response)

            raise ChangePasswordStanzaError(response, form)

    @iq_request_task
    def change_password_with_form(self, form):
        _task = yield

        response = yield _make_password_change_with_form(self._client.domain, form)
        yield process_response(response)
