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
from typing import Union
from typing import cast

import copy

from lxml import etree

from nbxmpp.jid import JID
from nbxmpp.namespaces import Namespace


NSMap = dict[Optional[str], str]


def create_nsmap_and_tag(tag: str, 
                         namespace: Optional[str]) -> tuple[str, Optional[NSMap]]:
    nsmap: Optional[NSMap] = None
    if namespace is not None:
        nsmap = {None: namespace}
        tag = '{%s}%s' % (namespace, tag)
    return tag, nsmap


class Base(etree.ElementBase):

    def find_tag(self,
                 tag: str,
                 namespace: Optional[str] = None) -> Optional[Base]:

        if namespace is None:
            namespace = etree.QName(self).namespace
        return self.find('{%s}%s' % (namespace, tag))

    def find_tag_text(self,
                      tag: str,
                      namespace: Optional[str] = None) -> Optional[str]:

        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            return element
        return element.text

    def has_tag(self,
                tag: str,
                namespace: Optional[str] = None) -> bool:

        return self.find_tag(tag, namespace=namespace) is not None

    def add_tag(self,
                tag: str,
                namespace: Optional[str] = None,
                **attrib: str) -> Base:

        if namespace is None:
            namespace = etree.QName(self).namespace

        tag, nsmap = create_nsmap_and_tag(tag, namespace)

        element = etree.SubElement(self, tag, nsmap=nsmap, attrib=attrib)
        return element

    def add_tag_text(self,
                     tag: str,
                     text: str,
                     namespace: Optional[str] = None):

        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            element = self.add_tag(tag, namespace=namespace)
        element.text = text
        return element

    def find_tag_attr(self,
                      tag: str,
                      attr: str,
                      namespace: Optional[str] = None) -> Optional[str]:
        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            return element
        return element.get(attr)

    def find_tags(self,
                  tag: str,
                  namespace: Optional[str] = None) -> list[Base]:
        return list(self.iter_tags(tag, namespace=namespace))

    def remove_tag(self,
                   tag: str,
                   namespace: Optional[str] = None) -> Optional[Base]:
        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            return None
        self.remove(element)
        return element

    def remove_tags(self,
                    tag: str,
                    namespace: Optional[str] = None) -> None:
        for element in self.find_tags(tag, namespace=namespace):
            self.remove(element)

    def iter_tags(self,
                  tag: str,
                  namespace: Optional[str] = None) -> list[Base]:
        if namespace is None:
            namespace = cast(str, self.nsmap[self.prefix])
        return self.iterchildren('{%s}%s' % (namespace, tag))

    def get_attribs(self) -> dict[str, str]:
        return dict(self.attrib)

    def get_children(self) -> list[Base]:
        return list(self)

    @property
    def lang(self) -> Optional[str]:
        return self.get(f'{Namespace.XML}lang')

    @property
    def localname(self) -> str:
        return etree.QName(self).localname

    @property
    def namespace(self) -> Optional[str]:
        return etree.QName(self).namespace

    @property
    def default_namespace(self) -> Optional[str]:
        return self.nsmap.get(None)

    def tostring(self, pretty_print: bool = False) -> str:
        etree.indent(self, space=8*' ')
        return etree.tostring(self, pretty_print=pretty_print).decode()

    def __str__(self) -> str:
        return self.tostring()

    def __repr__(self) -> str:
        repr_str = super().__repr__()
        return repr_str.replace('<Element', f'<{self.__class__.__name__}')


class Stanza(Base):

    def _jid_attr_converter(self, attr: str) -> Optional[JID]:
        jid = self.get(attr)
        if not jid:
            return None
        return JID.from_string(jid)

    def get_from(self) -> Optional[JID]:
        return self._jid_attr_converter('from')

    def set_from(self, jid: Union[str, JID]):
        self.set('from', str(jid))

    def get_to(self) -> Optional[JID]:
        return self._jid_attr_converter('to')

    def set_to(self, jid: Union[str, JID]):
        self.set('to', str(jid))

    def make_error(self,
                   type: str,
                   condition: str,
                   namespace: str,
                   text: Optional[str] = None):

        stanza = copy.deepcopy(self)
        stanza.set('type', 'error')
        stanza.set('to', stanza.get('from'))
        stanza.attrib.pop('from', '')
        error = stanza.add_tag('error', type=type)
        error.add_tag(condition, namespace=namespace)
        if text is not None:
            error.add_tag_text('text', text, namespace=namespace)
        return stanza

    def add_error(self,
                  type: str,
                  condition: str,
                  namespace: str,
                  text: Optional[str] = None):

        self.set('type', 'error')
        error = self.add_tag('error', type=type)
        error.add_tag(condition, namespace=namespace)
        if text is not None:
            error.add_tag_text('text', text, namespace=namespace)


class Nonza(Base):
    pass


class StreamStart(Base):
    TAG = 'stream'
    NAMESPACE = Namespace.STREAMS

    def tostring(self, pretty_print: bool = False) -> str:
        data = etree.tostring(self, pretty_print=False, encoding=str)
        return '<?xml version="1.0"?>' + data[:-2] + '>'


class StreamEnd(Base):
    TAG = 'stream'
    NAMESPACE = Namespace.STREAMS

    def tostring(self, pretty_print: bool = False) -> str:
        return '</stream:stream>'


class Open(Base):
    TAG = 'open'
    NAMESPACE = Namespace.FRAMING


class Close(Base):
    TAG = 'close'
    NAMESPACE = Namespace.FRAMING
