# Copyright (C) 2021 Philipp Hörist <philipp AT hoerist.com>
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

from typing import cast

from collections import deque

from nbxmpp import types
from nbxmpp import elements as elem
from nbxmpp.namespaces import Namespace
from nbxmpp.elements import register_class_lookup
from nbxmpp.builder import StreamStart
from nbxmpp.builder import StreamEnd
from nbxmpp.builder import Open
from nbxmpp.builder import Close


class XMPPElementQueue:
    def __init__(self) -> None:
        self._element_buffer = deque([])
        self._domain = cast(str, None)
        self._lang = cast(str, None)

    def _get_stream_header(self) -> types.Base:
        raise NotImplementedError

    def _get_stream_end(self) -> types.Base:
        raise NotImplementedError

    def has_pending(self) -> bool:
        return bool(self._element_buffer)

    def append(self, element: types.Base, first: bool = False) -> None:
        if first:
            self._element_buffer.appendleft(element)
        else:
            self._element_buffer.append(element)

    def start_stream(self, domain: str, lang: str = 'en') -> None:
        self._element_buffer.clear()
        self._domain = domain
        self._lang = lang
        element = self._get_stream_header()
        self.send(element)

    def send(self, element: types.Base, now: bool = False) -> None:
        raise NotImplementedError

    def end_stream(self) -> None:
        element = self._get_stream_end()
        self.send(element)

    def pop(self) -> tuple[bytes, list[types.Base]]:
        elements = list(self._element_buffer)
        data = b''
        while True:
            try:
                element = self._element_buffer.popleft()
            except IndexError:
                break

            data += element.tostring().encode()

        return data, elements

    def clear_queue(self):
        self._element_buffer.clear()


class TCPElementQueue(XMPPElementQueue):

    def _get_stream_header(self) -> types.Base:
        return StreamStart(self._domain, self._lang)

    def _get_stream_end(self) -> types.Base:
        return StreamEnd()


class WebsocketElementQueue(XMPPElementQueue):

    def _get_stream_header(self) -> types.Base:
        return Open(self._domain, self._lang)

    def _get_stream_end(self) -> types.Base:
        return Close()



register_class_lookup('stream', Namespace.STREAMS, elem.StreamStart)
register_class_lookup('open', Namespace.FRAMING, elem.Open)
register_class_lookup('close', Namespace.FRAMING, elem.Close)
