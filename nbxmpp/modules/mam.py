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


from nbxmpp.protocol import JID
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MAMQueryData
from nbxmpp.structs import MAMPreferencesData
from nbxmpp.task import iq_request_task
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.rsm import parse_rsm
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.dataforms import create_field
from nbxmpp.modules.util import process_response


class MAM(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def make_query(self,
                   jid,
                   queryid=None,
                   start=None,
                   end=None,
                   with_=None,
                   after=None,
                   max_=70):

        _task = yield

        response = yield _make_request(jid, queryid,
                                       start, end, with_, after, max_)
        if response.isError():
            raise StanzaError(response)

        jid = response.getFrom()
        fin = response.getTag('fin', namespace=Namespace.MAM_2)
        if fin is None:
            raise MalformedStanzaError('fin node missing', response)

        rsm = parse_rsm(fin)
        if rsm is None:
            raise MalformedStanzaError('rsm set missing', response)

        complete = fin.getAttr('complete') == 'true'
        if max_ != 0 and not complete:
            # max_ == 0 is a request for count of the items in a result set
            # in this case first and last will be absent
            # See: https://xmpp.org/extensions/xep-0059.html#count
            if rsm.first is None or rsm.last is None:
                raise MalformedStanzaError('first or last element missing',
                                           response)

        yield MAMQueryData(jid=jid,
                           complete=complete,
                           rsm=rsm)

    @iq_request_task
    def request_preferences(self):
        _task = yield

        response = yield _make_pref_request()
        if response.isError():
            raise StanzaError(response)

        prefs = response.getTag('prefs', namespace=Namespace.MAM_2)
        if prefs is None:
            raise MalformedStanzaError('prefs node missing', response)

        default = prefs.getAttr('default')
        if default is None:
            raise MalformedStanzaError('default attr missing', response)

        always_node = prefs.getTag('always')
        if always_node is None:
            raise MalformedStanzaError('always node missing', response)

        always = _get_preference_jids(always_node)

        never_node = prefs.getTag('never')
        if never_node is None:
            raise MalformedStanzaError('never node missing', response)

        never = _get_preference_jids(never_node)
        yield MAMPreferencesData(default=default,
                                 always=always,
                                 never=never)

    @iq_request_task
    def set_preferences(self, default, always, never):
        _task = yield

        if default not in ('always', 'never', 'roster'):
            raise ValueError('Wrong default preferences type')

        response = yield _make_set_pref_request(default, always, never)
        yield process_response(response)


def _make_query_form(start, end, with_):
    fields = [
        create_field(typ='hidden', var='FORM_TYPE', value=Namespace.MAM_2)
    ]

    if start:
        fields.append(create_field(
            typ='text-single',
            var='start',
            value=start.strftime('%Y-%m-%dT%H:%M:%SZ')))

    if end:
        fields.append(create_field(
            typ='text-single',
            var='end',
            value=end.strftime('%Y-%m-%dT%H:%M:%SZ')))

    if with_:
        fields.append(create_field(
            typ='jid-single',
            var='with',
            value=with_))

    return SimpleDataForm(type_='submit', fields=fields)


def _make_rsm_query(max_, after):
    rsm_set = Node('set', attrs={'xmlns': Namespace.RSM})
    if max_ is not None:
        rsm_set.setTagData('max', max_)
    if after is not None:
        rsm_set.setTagData('after', after)
    return rsm_set


def _make_request(jid, queryid, start, end, with_, after, max_):
    iq = Iq(typ='set', to=jid, queryNS=Namespace.MAM_2)
    if queryid is not None:
        iq.getQuery().setAttr('queryid', queryid)

    payload = [
        _make_query_form(start, end, with_),
        _make_rsm_query(max_, after)
    ]

    iq.setQueryPayload(payload)
    return iq


def _make_pref_request():
    iq = Iq('get', queryNS=Namespace.MAM_2)
    iq.setQuery('prefs')
    return iq


def _get_preference_jids(node):
    jids = []
    for item in node.getTags('jid'):
        jid = item.getData()
        if not jid:
            continue

        try:
            jid = JID.from_string(jid)
        except Exception:
            continue

        jids.append(jid)
    return jids


def _make_set_pref_request(default, always, never):
    iq = Iq(typ='set')
    prefs = iq.addChild(name='prefs',
                        namespace=Namespace.MAM_2,
                        attrs={'default': default})
    always_node = prefs.addChild(name='always')
    never_node = prefs.addChild(name='never')
    for jid in always:
        always_node.addChild(name='jid').setData(jid)

    for jid in never:
        never_node.addChild(name='jid').setData(jid)
    return iq
