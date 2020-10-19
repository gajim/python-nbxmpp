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
from nbxmpp.protocol import Iq
from nbxmpp.const import REGISTER_FIELDS
from nbxmpp.structs import RegisterData
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.dataforms import create_field
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.bits_of_binary import parse_bob_data


def _make_password_change_request(domain, username, password):
    iq = Iq('set', Namespace.REGISTER, to=domain)
    query = iq.getQuery()
    query.setTagData('username', username)
    query.setTagData('password', password)
    return iq


def _make_password_change_with_form(domain, form):
    iq = Iq('set', Namespace.REGISTER, to=domain)
    iq.setQueryPayload(form)
    return iq


def _make_register_form(jid, form):
    iq = Iq('set', Namespace.REGISTER, to=jid)
    if form.is_fake_form():
        query = iq.getTag('query')
        for field in form.iter_fields():
            if field.var == 'fakeform':
                continue
            query.addChild(field.var, payload=[field.value])
        return iq

    iq.setQueryPayload(form)
    return iq


def _make_unregister_request(jid):
    iq = Iq('set', to=jid)
    query = iq.setQuery()
    query.setNamespace(Namespace.REGISTER)
    query.addChild('remove')
    return iq


def _parse_oob_url(query):
    oob = query.getTag('x', namespace=Namespace.X_OOB)
    if oob is not None:
        return oob.getTagData('url') or None
    return None


def _parse_form(stanza):
    query = stanza.getTag('query', namespace=Namespace.REGISTER)
    form = query.getTag('x', namespace=Namespace.DATA)
    if form is None:
        return None

    form = extend_form(node=form)
    field = form.vars.get('FORM_TYPE')
    if field is None:
        return None

    # Invalid urn:xmpp:captcha used by ejabberd
    # See https://github.com/processone/ejabberd/issues/3045
    if field.value in ('jabber:iq:register', 'urn:xmpp:captcha'):
        return form
    return None


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
    return SimpleDataForm(type_='form',
                          instructions=query.getTagData('instructions'),
                          fields=fields)


def _parse_register_data(response):
    query = response.getTag('query', namespace=Namespace.REGISTER)
    if query is None:
        raise StanzaError(response)

    instructions = query.getTagData('instructions') or None

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
