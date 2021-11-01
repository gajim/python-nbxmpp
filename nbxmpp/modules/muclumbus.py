# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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

import json

from gi.repository import Soup

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult
from nbxmpp.const import AnonymityMode
from nbxmpp.builder import Iq
from nbxmpp.builder import E
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.task import http_request_task
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize


# API Documentation
# https://search.jabber.network/docs/api

class Muclumbus(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

        self._proxy_resolver = None
        self._soup_session = Soup.Session()

    def set_proxy(self, proxy):
        if proxy is None:
            return
        self._proxy_resolver = proxy.get_resolver()
        self._soup_session.props.proxy_resolver = self._proxy_resolver

    @iq_request_task
    def request_parameters(self, jid):

        response = yield _make_parameter_request(jid)
        if response.is_error():
            raise StanzaError(response)

        search = response.find_tag('search', namespace=Namespace.MUCLUMBUS)
        if search is None:
            raise MalformedStanzaError('search node missing', response)

        dataform = search.find_tag('x', namespace=Namespace.DATA)
        if dataform is None:
            raise MalformedStanzaError('dataform node missing', response)

        self._log.info('Muclumbus parameters received')
        yield finalize(extend_form(node=dataform))

    @iq_request_task
    def set_search(self, jid, dataform, items_per_page=50, after=None):

        response = yield _make_search_query(jid,
                                            dataform,
                                            items_per_page,
                                            after)
        if response.is_error():
            raise StanzaError(response)

        result = response.find_tag('result', namespace=Namespace.MUCLUMBUS)
        if result is None:
            raise MalformedStanzaError('result node missing', response)

        items = result.find_tags('item')
        if not items:
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        set_ = result.find_tag('set', namespace=Namespace.RSM)
        if set_ is None:
            raise MalformedStanzaError('set node missing', response)

        first = set_.find_tag_text('first')
        last = set_.find_tag_text('last')
        try:
            max_ = int(set_.find_tag_text('max'))
        except Exception:
            raise MalformedStanzaError('invalid max value', response)

        results = []
        for item in items:
            jid = item.get('address')
            name = item.find_tag_text('name')
            nusers = item.find_tag_text('nusers')
            description = item.find_tag_text('description')
            language = item.find_tag_text('language')
            is_open = item.find_tag('is-open') is not None

            try:
                anonymity_mode = AnonymityMode(
                    item.find_tag_text('anonymity-mode'))
            except ValueError:
                anonymity_mode = AnonymityMode.UNKNOWN
            results.append(MuclumbusItem(jid=jid,
                                         name=name or '',
                                         nusers=nusers or '',
                                         description=description or '',
                                         language=language or '',
                                         is_open=is_open,
                                         anonymity_mode=anonymity_mode))
        yield MuclumbusResult(first=first,
                              last=last,
                              max=max_,
                              end=len(items) < max_,
                              items=results)

    @http_request_task
    def set_http_search(self, uri, keywords, after=None):

        search = {'keywords': keywords}
        if after is not None:
            search['after'] = after

        message = Soup.Message.new('POST', uri)
        message.set_request('application/json',
                            Soup.MemoryUse.COPY,
                            json.dumps(search).encode())

        response_message = yield message

        soup_body = response_message.get_property('response-body')

        if response_message.status_code != 200:
            self._log.warning(soup_body.data)
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        response = json.loads(soup_body.data)

        result = response['result']
        items = result.get('items')
        if items is None:
            yield MuclumbusResult(first=None,
                                  last=None,
                                  max=None,
                                  end=True,
                                  items=[])

        results = []
        for item in items:
            try:
                anonymity_mode = AnonymityMode(item['anonymity_mode'])
            except (ValueError, KeyError):
                anonymity_mode = AnonymityMode.UNKNOWN

            results.append(
                MuclumbusItem(jid=item['address'],
                              name=item['name'] or '',
                              nusers=str(item['nusers'] or ''),
                              description=item['description'] or '',
                              language=item['language'] or '',
                              is_open=item['is_open'],
                              anonymity_mode=anonymity_mode))

        yield MuclumbusResult(first=None,
                              last=result['last'],
                              max=None,
                              end=not result['more'],
                              items=results)


def _make_parameter_request(jid: JID) -> types.Iq:
    iq = Iq(to=jid)
    iq.add_tag('search', namespace=Namespace.MUCLUMBUS)
    return iq


def _make_search_query(jid: JID,
                       dataform: types.DataForm,
                       items_per_page: int = 50,
                       after: Optional[str] = None) -> types.Iq:
    iq = Iq(to=jid)
    search = iq.add_tag('search', namespace=Namespace.MUCLUMBUS)
    search.append(dataform)
    rsm = search.add_tag('set', namespace=Namespace.RSM)
    rsm.add_tag_text('max', str(items_per_page))
    if after is not None:
        rsm.add_tag_text('after', str(after))

    return iq
