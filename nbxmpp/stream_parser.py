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
from copy import deepcopy

from typing import Any
from typing import Optional
from typing import Callable
from typing import Union
from typing import cast

import logging

from lxml import etree
from lxml.etree import ElementBase
from nbxmpp import types

from nbxmpp.lookups import ElementLookup
from nbxmpp.util import Observable
from nbxmpp.util import LogAdapter


DispatchCallable = Callable[[ElementBase], None]

log = logging.getLogger('nbxmpp.parser')


PARSER_SETTINGS = {
    'load_dtd': True,
    'dtd_validation': False,
    'no_network': False,
    'recover': False,
    'resolve_entities': False,
    'remove_comments': True,
    'remove_pis': True,
}


class BaseParser(Observable):
    def __init__(self, log_context: str) -> None:
        Observable.__init__(self, log)

        self._log = LogAdapter(log, {'context': log_context})
        self._destroyed = False
        self._parser = self._create_parser()

    def _create_parser(self) -> Any:
        raise NotImplementedError

    def feed(self, data: str) -> None:
        raise NotImplementedError

    def _cleanup(self) -> None:
        raise NotImplementedError

    def destroy(self) -> None:
        self.remove_subscriptions()
        self._destroyed = True
        self._cleanup()


class TCPStreamParser(BaseParser):

    _dispatch_depth = 1

    def __init__(self, log_context: str):
        BaseParser.__init__(self, log_context)

        self._depth = 0
        self._root = None

    def get_root(self) -> ElementBase:
        return self._root

    def get_tree(self) -> Any:
        return self._root.getroottree()
    
    def _create_parser(self) -> etree.XMLPullParser:
        parser = etree.XMLPullParser(events=['start', 'end'], **PARSER_SETTINGS)

        parser.set_element_class_lookup(ElementLookup)
        return parser

    def feed(self, data: Union[str, bytes]):
        if self._destroyed:
            raise ValueError('Parser is destroyed')

        self._parser.feed(data)
        for action, element in list(self._parser.read_events()):
            if action == 'start':
                if self._depth == 0:
                    element = self._cleanup_stream_start(element)
                    self.notify('stream-start', element)
                self._depth += 1

            elif action == 'end':
                self._depth -= 1
                if self._depth == self._dispatch_depth:
                    self.notify('element', element)
                    self._free_elements(element)

                if self._depth == 0:
                    self._stream_end = True
                    self.notify('stream-end', element)
                    self.destroy()
                    break

    def _free_elements(self, element: ElementBase):
        '''
        XMLPullParser stores the whole tree in memory by default.
        this deletes all previous siblings from the tree and frees the memory
        ''' 
        if element.getprevious() is not None:
            del element.getparent()[0]

    def _cleanup_stream_start(self, element: ElementBase):
        '''
        The first data contains often also the stream features. So the first
        element lxml yields already has a features child. This removes it so it
        creates no confusion.
        '''
        element = deepcopy(element)
        for child in list(element):
            element.remove(child)
        return element

    def _cleanup(self):
        try:
            self._root = self._parser.close()
        except Exception:
            pass

        self._parser = cast(etree.XMLPullParser, None)


class WebsocketParser(BaseParser):

    def __init__(self, log_context: str):
        BaseParser.__init__(self, log_context)

    def _create_parser(self) -> etree.XMLPullParser:
        parser = etree.XMLParser(**PARSER_SETTINGS)
        parser.set_element_class_lookup(ElementLookup)
        return parser

    def feed(self, data: str) -> None:
        if self._destroyed:
            raise ValueError('Parser is destroyed')

        element = etree.fromstring(data, self._parser)

        if isinstance(element, types.Open):
            self.notify('stream-start', element)

        elif isinstance(element, types.Close):
            self.notify('stream-end', element)

        else:
            self.notify('element', element)

    def _cleanup(self) -> None:
        self._parser = cast(etree.XMLParser, None)


def get_stream_parser(websocket: bool, log_context: Optional[str] = None) -> BaseParser:
    if websocket:
        return WebsocketParser(log_context or '')
    return TCPStreamParser(log_context or '')
