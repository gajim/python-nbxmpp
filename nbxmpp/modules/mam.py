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

from __future__ import annotations

from typing import Generator
from typing import Optional
from typing import Union

from datetime import datetime

from nbxmpp import types
from nbxmpp.builder import DataForm
from nbxmpp.builder import E
from nbxmpp.builder import Iq
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.rsm import parse_rsm
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.structs import CommonResult
from nbxmpp.structs import MAMPreferencesData
from nbxmpp.structs import MAMQueryData
from nbxmpp.task import iq_request_task


QueryGenerator = Generator[Union[types.Iq, MAMQueryData], types.Iq, None]
PrefGenerator = Generator[Union[types.Iq, MAMPreferencesData], types.Iq, None]
SetPrefGenerator = Generator[Union[types.Iq, CommonResult], types.Iq, None]


class MAM(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def make_query(self,
                   jid: JID,
                   queryid: Optional[str] = None,
                   start: Optional[datetime] = None,
                   end: Optional[datetime] = None,
                   with_: Optional[JID] = None,
                   after: Optional[str] = None,
                   max_: int = 70) -> QueryGenerator:


        response = yield _make_request(jid, queryid,
                                       start, end, with_, after, max_)
        if response.is_error():
            raise StanzaError(response)

        jid = response.get_from()
        fin = response.find_tag('fin', namespace=Namespace.MAM_2)
        if fin is None:
            raise MalformedStanzaError('fin node missing', response)

        rsm = parse_rsm(fin)
        if rsm is None:
            raise MalformedStanzaError('rsm set missing', response)

        complete = fin.get('complete') == 'true'
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
    def request_preferences(self) -> PrefGenerator:

        response = yield _make_pref_request()
        if response.is_error():
            raise StanzaError(response)

        prefs = response.find_tag('prefs', namespace=Namespace.MAM_2)
        if prefs is None:
            raise MalformedStanzaError('prefs node missing', response)

        default = prefs.get('default')
        if default is None:
            raise MalformedStanzaError('default attr missing', response)

        always_node = prefs.find_tag('always')
        if always_node is None:
            raise MalformedStanzaError('always node missing', response)

        always = _get_preference_jids(always_node)

        never_node = prefs.find_tag('never')
        if never_node is None:
            raise MalformedStanzaError('never node missing', response)

        never = _get_preference_jids(never_node)
        yield MAMPreferencesData(default=default,
                                 always=always,
                                 never=never)

    @iq_request_task
    def set_preferences(self,
                        default: str,
                        always: str,
                        never: str) -> SetPrefGenerator:

        if default not in ('always', 'never', 'roster'):
            raise ValueError('Wrong default preferences type')

        response = yield _make_set_pref_request(default, always, never)
        yield process_response(response)


def _make_query_form(start: Optional[datetime],
                     end: Optional[datetime],
                     with_: Optional[JID]) -> types.DataForm:

    dataform = DataForm('submit')

    field = dataform.add_field('hidden', var='FORM_TYPE')
    field.set_value(Namespace.MAM_2)

    if start:
        field = dataform.add_field('text-single', var='start')
        field.set_value(start.strftime('%Y-%m-%dT%H:%M:%SZ'))

    if end:
        field = dataform.add_field('text-single', var='end')
        field.set_value(end.strftime('%Y-%m-%dT%H:%M:%SZ'))

    if end:
        field = dataform.add_field('jid-single', var='with')
        field.set_value(with_)

    return dataform


def _make_rsm_query(max_: int, after: Optional[str]) -> types.Base:
    rsm_set = E('set', namespace=Namespace.RSM)
    if max_ is not None:
        rsm_set.add_tag_text('max', str(max_))
    if after is not None:
        rsm_set.add_tag_text('after', after)
    return rsm_set


def _make_request(jid: JID,
                  queryid: Optional[str],
                  start: Optional[datetime],
                  end: Optional[datetime],
                  with_: Optional[JID],
                  after: Optional[str],
                  max_: int) -> types.Iq:

    iq = Iq(to=jid, type='set')
    query = iq.add_query(namespace=Namespace.MAM_2)
    if queryid is not None:
        query.set('queryid', queryid)

    form = _make_query_form(start, end, with_)
    rsm = _make_rsm_query(max_, after)

    query.append(form)
    query.append(rsm)

    return iq


def _make_pref_request() -> types.Iq:
    iq = Iq()
    iq.add_tag('prefs', namespace=Namespace.MAM_2)
    return iq


def _get_preference_jids(element: types.Base) -> list[JID]:
    jids: list[JID] = []
    for item in element.find_tags('jid'):
        jid = item.text or ''
        if not jid:
            continue

        try:
            jid = JID.from_string(jid)
        except Exception:
            continue

        jids.append(jid)
    return jids


def _make_set_pref_request(default: str, always: str, never: str) -> types.Iq:
    iq = Iq(type='set')
    prefs = iq.add_tag('prefs',
                       namespace=Namespace.MAM_2,
                       default=default)
    always_node = prefs.add_tag('always')
    never_node = prefs.add_tag('never')
    for jid in always:
        always_node.add_tag_text('jid', jid)

    for jid in never:
        never_node.add_tag_text('jid', jid)
    return iq
