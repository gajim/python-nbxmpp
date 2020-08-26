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
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import Node
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MAMQueryData
from nbxmpp.structs import MAMPreferencesData
from nbxmpp.structs import CommonResult
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import raise_error
from nbxmpp.modules.rsm import parse_rsm
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.dataforms import create_field
from nbxmpp.modules.base import BaseModule


class MAM(BaseModule):
    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @call_on_response('_query_result')
    def make_query(self,
                   jid,
                   queryid=None,
                   start=None,
                   end=None,
                   with_=None,
                   after=None,
                   max_=70):

        iq = Iq(typ='set', to=jid, queryNS=Namespace.MAM_2)
        if queryid is not None:
            iq.getQuery().setAttr('queryid', queryid)

        payload = [
            self._make_query_form(start, end, with_),
            self._make_rsm_query(max_, after)
        ]

        iq.setQueryPayload(payload)
        return iq

    @staticmethod
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

    @staticmethod
    def _make_rsm_query(max_, after):
        rsm_set = Node('set', attrs={'xmlns': Namespace.RSM})
        if max_ is not None:
            rsm_set.setTagData('max', max_)
        if after is not None:
            rsm_set.setTagData('after', after)
        return rsm_set

    @callback
    def _query_result(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        jid = stanza.getFrom()
        fin = stanza.getTag('fin', namespace=Namespace.MAM_2)
        if fin is None:
            return raise_error(self._log.warning,
                               stanza,
                               'stanza-malformed',
                               'No fin node found')

        rsm = parse_rsm(fin)
        if rsm is None:
            return raise_error(self._log.warning,
                               stanza,
                               'stanza-malformed',
                               'rsm set missing')

        complete = fin.getAttr('complete') == 'true'
        if not complete:
            if rsm.first is None or rsm.last is None:
                return raise_error(self._log.warning,
                                   stanza,
                                   'stanza-malformed',
                                   'missing first or last element')

        return MAMQueryData(jid=jid,
                            complete=complete,
                            rsm=rsm)

    @call_on_response('_preferences_result')
    def request_preferences(self):
        iq = Iq('get', queryNS=Namespace.MAM_2)
        iq.setQuery('prefs')
        return iq

    @callback
    def _preferences_result(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)

        prefs = stanza.getTag('prefs', namespace=Namespace.MAM_2)
        if prefs is None:
            return raise_error(self._log.warning,
                               stanza,
                               'stanza-malformed',
                               'No prefs node found')

        default = prefs.getAttr('default')
        if default is None:
            return raise_error(self._log.warning,
                               stanza,
                               'stanza-malformed',
                               'No default attr found')

        always_node = prefs.getTag('always')
        if always_node is None:
            return raise_error(self._log.warning,
                               stanza,
                               'stanza-malformed',
                               'No always node found')

        always = self._get_preference_jids(always_node)

        never_node = prefs.getTag('never')
        if never_node is None:
            return raise_error(self._log.warning,
                               stanza,
                               'stanza-malformed',
                               'No never node found')

        never = self._get_preference_jids(never_node)
        return MAMPreferencesData(default=default,
                                  always=always,
                                  never=never)

    def _get_preference_jids(self, node):
        jids = []
        for item in node.getTags('jid'):
            jid = item.getData()
            if not jid:
                continue

            try:
                jid = JID.from_string(jid)
            except Exception:
                self._log.warning('Invalid jid found in preferences: %s',
                                  jid)
            jids.append(jid)
        return jids

    @call_on_response('_default_response')
    def set_preferences(self, default, always, never):
        if default not in ('always', 'never', 'roster'):
            raise ValueError('Wrong default preferences type')

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

    @callback
    def _default_response(self, stanza):
        if not isResultNode(stanza):
            return raise_error(self._log.info, stanza)
        return CommonResult(jid=stanza.getFrom())
