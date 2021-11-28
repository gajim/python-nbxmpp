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

from typing import Any
from typing import Callable
from typing import Union
from typing import cast

from lxml import etree
from lxml.etree import ElementBase

from nbxmpp.lookups import ElementLookup


DispatchCallable = Callable[[ElementBase], None]


class StreamParser:

    _dispatch_depth = 1

    def __init__(self, dispatch_callback: DispatchCallable):
        self._parser = self._create_parser()
        self._depth = 0
        self._dispatch_callback = dispatch_callback
        self._stream_end = False
        self._stream_error = ''
        self._destroyed = False
        self._root = None

    def get_root(self) -> ElementBase:
        return self._root

    def get_tree(self) -> Any:
        return self._root.getroottree()
    
    def _create_parser(self) -> etree.XMLPullParser:
        parser = etree.XMLPullParser(events=['start', 'end'],
                                     load_dtd=True,
                                     dtd_validation=False,
                                     no_network=False,
                                     recover=False,
                                     resolve_entities=False,
                                     remove_comments=True,
                                     remove_pis=True)

        parser.set_element_class_lookup(ElementLookup)
        return parser

    def feed(self, data: Union[str, bytes]):
        if self._destroyed:
            raise ValueError('Parser is destroyed')

        self._parser.feed(data)
        for action, element in list(self._parser.read_events()):
            if action == 'start':
                if self._depth == 0:
                    self._dispatch(element)
                self._depth += 1

            elif action == 'end':
                self._depth -= 1
                if self._depth == self._dispatch_depth:
                    self._dispatch(element)
                    self._free_elements(element)

                if self._depth == 0:
                    self._stream_end = True
                    self._dispatch(element)
                    self.destroy()
                    break

    def _free_elements(self, element: ElementBase):
        '''
        XMLPullParser stores the whole tree in memory by default.
        this deletes all previous siblings from the tree and frees the memory
        ''' 
        if element.getprevious() is not None:
            del element.getparent()[0]

    def _dispatch(self, element: ElementBase):
        if self._dispatch_callback is None:
            return

        self._dispatch_callback(element)

    def is_stream_end(self) -> bool:
        return self._stream_end

    def get_stream_error(self) -> str:
        return self._stream_error

    def _close(self):
        try:
            self._root = self._parser.close()
        except Exception:
            pass

    def _cleanup(self):
        self._parser = cast(etree.XMLPullParser, None)
        self._dispatch_callback = cast(DispatchCallable, None)

    def destroy(self):
        self._destroyed = True
        self._close()
        self._cleanup
