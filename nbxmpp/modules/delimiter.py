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

from typing import TYPE_CHECKING

from nbxmpp.errors import StanzaError
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import process_response
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Node
from nbxmpp.task import iq_request_task

if TYPE_CHECKING:
    from nbxmpp.client import Client


class Delimiter(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = []

    @iq_request_task
    def request_delimiter(self):
        _task = yield

        response = yield _make_request()
        if response.isError():
            raise StanzaError(response)

        delimiter = response.getQuery().getTagData('roster') or None
        yield delimiter

    @iq_request_task
    def set_delimiter(self, delimiter: str):
        _task = yield

        response = yield _make_set_request(delimiter)
        yield process_response(response)


def _make_request() -> Iq:
    node = Node('storage', attrs={'xmlns': Namespace.DELIMITER})
    iq = Iq('get', Namespace.PRIVATE, payload=node)
    return iq


def _make_set_request(delimiter: str) -> Iq:
    iq = Iq('set', Namespace.PRIVATE)
    roster = iq.getQuery().addChild('roster', namespace=Namespace.DELIMITER)
    roster.setData(delimiter)
    return iq
