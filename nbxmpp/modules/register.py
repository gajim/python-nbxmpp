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

from nbxmpp.protocol import NS_X_OOB
from nbxmpp.protocol import NS_DATA
from nbxmpp.protocol import NS_REGISTER
from nbxmpp.protocol import Iq
from nbxmpp.protocol import isResultNode
from nbxmpp.structs import CommonResult
from nbxmpp.structs import RegisterData
from nbxmpp.structs import ChangePasswordResult
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.util import get_form
from nbxmpp.const import REGISTER_FIELDS
from nbxmpp.modules.bits_of_binary import parse_bob_data
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.dataforms import create_field
from nbxmpp.modules.dataforms import SimpleDataForm

log = logging.getLogger('nbxmpp.m.register')


class Register:
    def __init__(self, client):
        self._client = client
        self.handlers = []

    @call_on_response('_default_response')
    def unregister(self):
        hostname = self._client.get_bound_jid().getDomain()
        iq = Iq('set', to=hostname)
        query = iq.setQuery()
        query.setNamespace(NS_REGISTER)
        query.addChild('remove')
        return iq

    @call_on_response('_on_register_form')
    def request_register_form(self, jid=None):
        if jid is None:
            jid = self._client.Server
        return Iq('get', NS_REGISTER, to=jid)

    @callback
    def _on_register_form(self, stanza):
        query = stanza.getQuery()

        instructions = query.getTagData('instructions') or None

        return RegisterData(instructions=instructions,
                            form=self._parse_form(stanza),
                            fields_form=self._parse_fields_form(query),
                            oob_url=self._parse_oob_url(query),
                            bob_data=parse_bob_data(query))

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)
        return CommonResult(jid=stanza.getFrom())

    @staticmethod
    def _parse_oob_url(query):
        oob = query.getTag('x', namespace=NS_X_OOB)
        if oob is not None:
            return oob.getTagData('url') or None
        return None

    @staticmethod
    def _parse_form(stanza):
        form = stanza.getQuery().getTag('x', namespace=NS_DATA)
        if form is None:
            return None

        form = extend_form(node=form)
        field = form.vars.get('FORM_TYPE')
        if field is None:
            log.warning('No FORM_TYPE found')
            log.warning(stanza)
            return None

        # Invalid urn:xmpp:captcha used by ejabberd
        # See https://github.com/processone/ejabberd/issues/3093
        if field.value in ('jabber:iq:register', 'urn:xmpp:captcha'):
            return form
        return None

    @staticmethod
    def _parse_fields_form(query):
        fields = []
        for field in query.getChildren():
            field_name = field.getName()
            if field_name not in REGISTER_FIELDS:
                continue

            required = field_name in ('username', 'password')
            typ = 'text-single' if field_name != 'password' else 'text-private'
            fields.append(create_field(typ=typ,
                                       var=field_name,
                                       required=required))

        if not fields:
            return None

        fields.append(create_field(typ='hidden', var='fakeform'))
        return SimpleDataForm(type_='form', fields=fields)

    @call_on_response('_on_password_change')
    def change_password(self, password):
        hostname = self._client.get_bound_jid().getDomain()
        username = self._client.get_bound_jid().getNode()
        iq = Iq('set', NS_REGISTER, to=hostname)
        query = iq.getQuery()
        query.setTagData('username', username)
        query.setTagData('password', password)
        return iq

    @callback
    def _on_password_change(self, stanza):
        if isResultNode(stanza):
            return ChangePasswordResult(successful=True)

        if stanza.getQuery() is None:
            return raise_error(log.info, stanza)

        form = get_form(stanza.getQuery(),
                        'jabber:iq:register:changepassword')
        if form is None:
            return raise_error(log.info, stanza)
        return ChangePasswordResult(successful=False, form=form)

    @call_on_response('_default_response')
    def change_password_with_form(self, form):
        hostname = self._client.get_bound_jid().getDomain()
        iq = Iq('set', NS_REGISTER, to=hostname)
        iq.setQueryPayload(form)
        return iq
