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

from typing import Optional

from nbxmpp import types
from nbxmpp.jid import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.builder import DataForm
from nbxmpp.builder import Iq
from nbxmpp.const import REGISTER_FIELDS
from nbxmpp.structs import RegisterData
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.bits_of_binary import parse_bob_data


def make_password_change_request(domain: str,
                                 username: str,
                                 password: str) -> types.Iq:

    iq = Iq(to=domain, type='set')
    query = iq.add_query(namespace=Namespace.REGISTER)
    query.add_tag_text('username', username)
    query.add_tag_text('password', password)
    return iq


def make_password_change_with_form(domain: str,
                                   form: types.DataForm) -> types.Iq:

    iq = Iq(type='set', to=domain)
    query = iq.add_query(namespace=Namespace.REGISTER)
    query.append(form)
    return iq


def make_register_form(jid: Optional[JID], form: types.DataForm) -> types.Iq:
    iq = Iq(to=jid, type='set')
    query = iq.add_query(namespace=Namespace.REGISTER)
    if form.is_fake_form():
        for field in form.iter_fields():
            if field.var == 'fakeform':
                continue
            query.add_tag_text(field.var, field.value)
        return iq

    query.append(form)
    return iq


def make_unregister_request(jid: Optional[JID]) -> types.Iq:
    iq = Iq(to=jid, type='set')
    query = iq.add_query(namespace=Namespace.REGISTER)
    query.add_tag('remove')
    return iq


def _parse_oob_url(query: types.Base) -> Optional[str]:
    oob = query.find_tag('x', namespace=Namespace.X_OOB)
    if oob is not None:
        return oob.find_tag_text('url') or None
    return None


def _parse_form(stanza: types.Iq) -> Optional[types.DataForm]:
    query = stanza.get_query(namespace=Namespace.REGISTER)
    form = query.find_tag('x', namespace=Namespace.DATA)
    if form is None:
        return None

    field = form.get_field('FORM_TYPE')
    if field is None:
        return None

    # Invalid urn:xmpp:captcha used by ejabberd
    # See https://github.com/processone/ejabberd/issues/3045
    if field.value in ('jabber:iq:register', 'urn:xmpp:captcha'):
        return form
    return None


def _parse_fields_form(query: types.Base) -> Optional[types.DataForm]:
    dataform = DataForm('form')
    for field in query:
        field_name = field.localname
        if field_name not in REGISTER_FIELDS:
            continue

        required = field_name in ('username', 'password')
        typ = 'text-single' if field_name != 'password' else 'text-private'
        dataform.add_field(typ, var=field_name, required=required)

    if not dataform.has_fields():
        return None

    dataform.add_field('hidden', var='fakeform')
    dataform.set_instructions(query.find_tag_text('instructions'))
    return dataform


def parse_register_data(response: types.Iq) -> RegisterData:
    query = response.get_query(namespace=Namespace.REGISTER)
    if query is None:
        raise StanzaError(response)

    instructions = query.find_tag_text('instructions') or None

    data = RegisterData(instructions=instructions,
                        form=_parse_form(response),
                        fields_form=_parse_fields_form(query),
                        oob_url=_parse_oob_url(query),
                        bob_data=parse_bob_data(query))

    if (data.form is None and
            data.fields_form is None and
            data.oob_url is None):
        raise MalformedStanzaError('invalid register response', response)

    return data
