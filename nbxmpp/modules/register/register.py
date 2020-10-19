# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
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
from nbxmpp.util import get_form
from nbxmpp.task import iq_request_task
from nbxmpp.errors import StanzaError
from nbxmpp.errors import RegisterStanzaError
from nbxmpp.errors import ChangePasswordStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.modules.register.util import _make_unregister_request
from nbxmpp.modules.register.util import _make_register_form
from nbxmpp.modules.register.util import _make_password_change_request
from nbxmpp.modules.register.util import _make_password_change_with_form
from nbxmpp.modules.register.util import _parse_register_data


class Register(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def unregister(self, jid=None):
        _task = yield

        response = yield _make_unregister_request(jid)
        yield process_response(response)

    @iq_request_task
    def request_register_form(self, jid=None):
        _task = yield

        if jid is None:
            jid = self._client.domain

        response = yield Iq('get', Namespace.REGISTER, to=jid)
        if response.isError():
            raise StanzaError(response)

        yield _parse_register_data(response)

    @iq_request_task
    def submit_register_form(self, form, jid=None):
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
    def change_password(self, password):
        _task = yield

        response = yield _make_password_change_request(
            self._client.domain, self._client.username, password)
        if not response.isError():
            yield process_response(response)

        else:
            query = response.getQuery()
            if query is None:
                raise StanzaError(response)

            form = get_form(query, 'jabber:iq:register:changepassword')
            if form is None or response.getType() != 'modify':
                raise StanzaError(response)

            raise ChangePasswordStanzaError(response, form)

    @iq_request_task
    def change_password_with_form(self, form):
        _task = yield

        response = yield _make_password_change_with_form(self._client.domain,
                                                         form)
        yield process_response(response)
