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

from collections import deque

from lxml import etree

from nbxmpp.namespaces import Namespace


ElementT = etree._Element


class XMPPElementQueue:
    def __init__(self) -> None:
        self._element_buffer = deque([])
        self._domain = None
        self._lang = None

    def _get_stream_header(self) -> bytes:
        raise NotImplementedError

    def _get_stream_end(self) -> bytes:
        raise NotImplementedError

    def has_pending(self) -> bool:
        return bool(self._element_buffer)

    def append(self, element: ElementT, first: bool = False) -> None:
        if first:
            self._element_buffer.appendleft(element)
        else:
            self._element_buffer.append(element)

    def serialise(self, element: ElementT) -> bytes:
        return etree.tostring(element, encoding='utf-8')

    def start_stream(self, domain: str, lang: str = 'en') -> None:
        self._element_buffer.clear()
        self._domain = domain
        self._lang = lang
        start = self._get_stream_header()
        self._start_stream(start)

    def _start_stream(self, data: bytes) -> None:
        raise NotImplementedError

    def end_stream(self) -> None:
        end = self._get_stream_end()
        self._end_stream(end)

    def _end_stream(self, data: bytes) -> None:
        raise NotImplementedError

    def pop(self) -> tuple[bytes, list[ElementT]]:
        elements = list(self._element_buffer)
        data = b''
        while True:
            try:
                element = self._element_buffer.popleft()
            except IndexError:
                break

            data += etree.tostring(element, encoding='utf-8')

        return data, elements

    def clear_queue(self):
        self._element_buffer.clear()


class TCPElementQueue(XMPPElementQueue):

    def _get_stream_header(self) -> bytes:
        return (
            f'<?xml version="1.0"?><stream:stream xmlns="{Namespace.CLIENT}" '
            f'version="1.0" xmlns:stream="{Namespace.STREAMS}" '
            f'to="{self._domain}" xml:lang="{self._lang}">'.encode())

    def _get_stream_end(self) -> bytes:
        return '</stream:stream>'.encode()


class WebsocketElementQueue(XMPPElementQueue):

    def _get_stream_header(self) -> bytes:
        open_ = etree.Element('open',
                              attrib={'version': '1.0',
                                      'to': self._domain,
                                      'xml:lang': self._lang},
                              nsmap={None: Namespace.FRAMING})
        return etree.tostring(open_, encoding='utf-8')

    def _get_stream_end(self) -> bytes:
        close = etree.Element('close', nsmap={None: Namespace.FRAMING})
        return etree.tostring(close, encoding='utf-8')
