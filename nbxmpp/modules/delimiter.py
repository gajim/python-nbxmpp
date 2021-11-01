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

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.structs import CommonResult
from nbxmpp.task import iq_request_task
from nbxmpp.builder import Iq
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response


RequestGenerator = Generator[Union[Optional[str], types.Iq], types.Iq, None]
SetGenerator = Generator[Union[types.Iq, CommonResult], types.Iq, None]


class Delimiter(BaseModule):
    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_delimiter(self) -> RequestGenerator:

        response = yield _make_request()
        if response.is_error():
            raise StanzaError(response)

        query = response.get_query(namespace=Namespace.PRIVATE)
        if query is None:
            raise MalformedStanzaError('query element missing', response)

        yield query.find_tag_text('roster')

    @iq_request_task
    def set_delimiter(self, delimiter: str) -> SetGenerator:

        response = yield _make_set_request(delimiter)
        yield process_response(response)


def _make_request() -> types.Iq:
    iq = Iq()
    query = iq.add_query(namespace=Namespace.PRIVATE)
    query.add_tag('roster', namespace=Namespace.DELIMITER)
    return iq


def _make_set_request(delimiter: str) -> types.Iq:
    iq = Iq()
    query = iq.add_query(namespace=Namespace.PRIVATE)
    query.add_tag_text('roster', delimiter, namespace=Namespace.DELIMITER)
    return iq
