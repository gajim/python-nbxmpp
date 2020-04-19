##   simplexml.py based on Mattew Allum's xmlstream.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

"""
Simplexml module provides xmpppy library with all needed tools to handle XML
nodes and XML streams. I'm personally using it in many other separate
projects. It is designed to be as standalone as possible
"""

from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from typing import Iterator
from typing import Callable
from typing import Any

import logging
import xml.parsers.expat
from xml.parsers.expat import ExpatError
from copy import deepcopy

from nbxmpp.const import NOT_ALLOWED_XML_CHARS


Attrs = Dict[str, str]

log = logging.getLogger('nbxmpp.simplexml')

def XMLescape(text: str) -> str:
    """
    Return escaped text
    """

    for key, value in NOT_ALLOWED_XML_CHARS.items():
        text = text.replace(key, value)
    return text

class Node:
    """
    Node class describes syntax of separate XML Node. It have a constructor that
    permits node creation from set of "namespace name", attributes and payload
    of text strings and other nodes. It does not natively support building node
    from text string and uses NodeBuilder class for that purpose. After
    creation node can be mangled in many ways so it can be completely changed.
    Also node can be serialised into string in one of two modes: default (where
    the textual representation of node describes it exactly) and "fancy" - with
    whitespace added to make indentation and thus make result more readable by
    human.

    Node class have attribute FORCE_NODE_RECREATION that is defaults to False
    thus enabling fast node replication from the some other node. The drawback
    of the fast way is that new node shares some info with the "original" node
    that is changing the one node may influence the other. Though it is rarely
    needed (in xmpppy it is never needed at all since I'm usually never using
    original node after replication (and using replication only to move upwards
    on the classes tree).
    """

    name: str
    namespace: str
    attrs: Attrs
    data: List[str]
    kids: List[Union[Node, str]]
    parent: Optional[Node]
    nsd: Dict[str, str]
    nsp_cache: Dict[Any, Any]

    FORCE_NODE_RECREATION = False

    def __init__(
            self,
            tag: Optional[str] = None,
            attrs: Optional[Attrs] = None,
            payload: Optional[Union[Node, str, List[Union[Node, str]]]] = None,
            parent: Optional[Node] = None,
            nsp: Optional[Dict[Any, Any]] = None,
            node_built: bool = False,
            node: Optional[Union[Node, Any]] = None) -> None:
        """
        Takes "tag" argument as the name of node (prepended by namespace, if
        needed and separated from it by a space), attrs dictionary as the set of
        arguments, payload list as the set of textual strings and child nodes
        that this node carries within itself and "parent" argument that is
        another node that this one will be the child of. Also the __init__ can
        be provided with "node" argument that is either a text string containing
        exactly one node or another Node instance to begin with. If both "node"
        and other arguments is provided then the node initially created as
        replica of "node" provided and then modified to be compliant with other
        arguments.
        """
        if node:
            if self.FORCE_NODE_RECREATION and isinstance(node, Node):
                node = str(node)
            if not isinstance(node, Node):
                node = NodeBuilder(node, self)
                node_built = True
            else:
                self.name = node.name
                self.namespace = node.namespace
                self.attrs = {}
                self.data = []
                self.kids = []
                self.parent = node.parent
                self.nsd = {}
                for key in node.attrs.keys():
                    self.attrs[key] = node.attrs[key]
                for data in node.data:
                    self.data.append(data)
                for kid in node.kids:
                    self.kids.append(kid)
                for key, value in node.nsd.items():
                    self.nsd[key] = value
        else:
            self.name = 'tag'
            self.namespace = ''
            self.attrs = {}
            self.data = []
            self.kids = []
            self.parent = None
            self.nsd = {}
        if parent:
            self.parent = parent
        self.nsp_cache = {}
        if nsp:
            for key, value in nsp.items():
                self.nsp_cache[key] = value

        if attrs is not None:
            for attr, val in attrs.items():
                if attr == 'xmlns':
                    self.nsd[''] = val
                elif attr.startswith('xmlns:'):
                    self.nsd[attr[6:]] = val
                self.attrs[attr] = attrs[attr]

        if tag:
            if node_built:
                pfx, self.name = (['']+tag.split(':'))[-2:]
                self.namespace = self.lookup_nsp(pfx)
            else:
                if ' ' in tag:
                    self.namespace, self.name = tag.split()
                else:
                    self.name = tag
        if payload is not None:
            if not isinstance(payload, list):
                payload = [payload]
            for i in payload:
                if isinstance(i, Node):
                    self.addChild(node=i)
                else:
                    self.data.append(str(i))

    def lookup_nsp(self, pfx: str = '') -> str:
        ns = self.nsd.get(pfx, None)
        if ns is None:
            ns = self.nsp_cache.get(pfx, None)
        if ns is None:
            if self.parent:
                ns = self.parent.lookup_nsp(pfx)
                self.nsp_cache[pfx] = ns
            else:
                return 'http://www.gajim.org/xmlns/undeclared'
        return ns

    def __str__(self, fancy: int = 0) -> str:
        """
        Method used to dump node into textual representation. If "fancy"
        argument is set to True produces indented output for readability
        """
        s = (fancy-1) * 2 * ' ' + "<" + self.name
        if self.namespace:
            if not self.parent or self.parent.namespace!=self.namespace:
                if 'xmlns' not in self.attrs:
                    s += ' xmlns="%s"' % self.namespace
        for key in self.attrs.keys():
            val = str(self.attrs[key])
            s += ' %s="%s"' % (key, XMLescape(val))

        s += ">"
        cnt = 0
        if self.kids:
            if fancy:
                s += "\n"
            for a in self.kids:
                if not fancy and (len(self.data)-1) >= cnt:
                    s += XMLescape(self.data[cnt])
                elif (len(self.data)-1) >= cnt:
                    s += XMLescape(self.data[cnt].strip())
                if isinstance(a, str):
                    s += a.__str__()
                else:
                    s += a.__str__(fancy and fancy+1)
                cnt += 1
        if not fancy and (len(self.data)-1) >= cnt:
            s += XMLescape(self.data[cnt])
        elif (len(self.data)-1) >= cnt:
            s += XMLescape(self.data[cnt].strip())
        if not self.kids and s.endswith('>'):
            s = s[:-1] + ' />'
            if fancy:
                s += "\n"
        else:
            if fancy and not self.data:
                s += (fancy-1) * 2 * ' '
            s += "</" + self.name + ">"
            if fancy:
                s += "\n"
        return s

    def addChild(self,
                 name: Optional[str] = None,
                 attrs: Optional[Attrs] = None,
                 payload: Optional[List[Any]] = None,
                 namespace: Optional[str] = None,
                 node: Optional[Node] = None) -> Node:
        """
        If "node" argument is provided, adds it as child node. Else creates new
        node from the other arguments' values and adds it as well
        """
        if payload is None:
            payload = []

        if attrs is None:
            attrs = {}
        elif 'xmlns' in attrs:
            raise AttributeError("Use namespace=x instead of attrs={'xmlns':x}")
        if node:
            newnode=node
            node.parent = self
        else: newnode=Node(tag=name, parent=self, attrs=attrs, payload=payload)
        if namespace:
            newnode.setNamespace(namespace)
        self.kids.append(newnode)
        return newnode

    def addData(self, data: Any) -> None:
        """
        Add some CDATA to node
        """
        self.data.append(str(data))

    def clearData(self) -> None:
        """
        Remove all CDATA from the node
        """
        self.data = []

    def delAttr(self, key: str) -> None:
        """
        Delete an attribute "key"
        """
        del self.attrs[key]

    def delChild(self,
                 node: Union[Node, str],
                 attrs: Optional[Attrs] = None) -> Optional[Node]:
        """
        Delete the "node" from the node's childs list, if "node" is an instance.
        Else delete the first node that have specified name and (optionally)
        attributes
        """
        if not isinstance(node, Node):
            node = self.getTag(node, attrs)
        assert isinstance(node, Node)
        self.kids.remove(node)
        return node

    def getAttrs(self, copy: bool = False) -> Attrs:
        """
        Return all node's attributes as dictionary
        """
        if copy:
            return deepcopy(self.attrs)
        return self.attrs

    def getAttr(self, key: str) -> Optional[str]:
        """
        Return value of specified attribute
        """
        return self.attrs.get(key)

    def getChildren(self) -> List[Union[Node, str]]:
        """
        Return all node's child nodes as list
        """
        return self.kids

    def getData(self) -> str:
        """
        Return all node CDATA as string (concatenated)
        """
        return ''.join(self.data)

    def getName(self) -> str:
        """
        Return the name of node
        """
        return self.name

    def getNamespace(self) -> str:
        """
        Return the namespace of node
        """
        return self.namespace

    def getParent(self) -> Optional[Node]:
        """
        Returns the parent of node (if present)
        """
        return self.parent

    def getPayload(self) -> List[Union[Node, str]]:
        """
        Return the payload of node i.e. list of child nodes and CDATA entries.
        F.e. for "<node>text1<nodea/><nodeb/> text2</node>" will be returned
        list: ['text1', <nodea instance>, <nodeb instance>, ' text2']
        """
        ret: List[Union[Node, str]] = []
        for i in range(len(self.kids)+len(self.data)+1):
            try:
                if self.data[i]:
                    ret.append(self.data[i])
            except IndexError:
                pass
            try:
                ret.append(self.kids[i])
            except IndexError:
                pass
        return ret

    def getTag(self,
               name: str,
               attrs: Optional[Attrs] = None,
               namespace: Optional[str] = None) -> Optional[Node]:
        """
        Filter all child nodes using specified arguments as filter. Return the
        first found or None if not found
        """
        tag = self.getTags(name, attrs, namespace, one=True)
        assert not isinstance(tag, list)
        return tag

    def getTagAttr(self,
                   tag: str,
                   attr: str,
                   namespace: Optional[str] = None) -> Optional[str]:
        """
        Return attribute value of the child with specified name (or None if no
        such attribute)
        """
        node = self.getTag(tag, namespace=namespace)
        if node is None:
            return None
        return node.getAttr(attr)

    def getTagData(self, tag: str) -> Optional[str]:
        """
        Return cocatenated CDATA of the child with specified name
        """
        node = self.getTag(tag)
        if node is None:
            return None
        return node.getData()

    def getTags(self,
                name: str,
                attrs: Optional[Attrs] = None,
                namespace: Optional[str] = None,
                one: bool = False) -> Union[List[Node], Node, None]:
        """
        Filter all child nodes using specified arguments as filter. Returns the
        list of nodes found
        """
        nodes = []
        for node in self.kids:
            if namespace and namespace != node.getNamespace():
                continue
            if node.getName() == name:
                if attrs is None:
                    attrs = {}
                for key in attrs.keys():
                    if key not in node.attrs or node.attrs[key] != attrs[key]:
                        break
                else:
                    nodes.append(node)
            if one and nodes:
                return nodes[0]
        if not one:
            return nodes
        return None

    def iterTags(self,
                 name: str,
                 attrs: Optional[Attrs] = None,
                 namespace: Optional[str] = None) -> Iterator[Node]:
        """
        Iterate over all children using specified arguments as filter
        """
        for node in self.kids:
            if namespace is not None and namespace != node.getNamespace():
                continue
            if node.getName() == name:
                if attrs is None:
                    attrs = {}
                for key in attrs.keys():
                    if key not in node.attrs or \
                            node.attrs[key]!=attrs[key]:
                        break
                else:
                    yield node

    def setAttr(self, key: str, val: str) -> None:
        """
        Set attribute "key" with the value "val"
        """
        self.attrs[key] = val

    def setData(self, data: Any) -> None:
        """
        Set node's CDATA to provided string. Resets all previous CDATA!
        """
        self.data = [str(data)]

    def setName(self, val: str) -> None:
        """
        Change the node name
        """
        self.name = val

    def setNamespace(self, namespace: str) -> None:
        """
        Changes the node namespace
        """
        self.namespace = namespace

    def setParent(self, node: Node) -> None:
        """
        Set node's parent to "node". WARNING: do not checks if the parent
        already present and not removes the node from the list of childs of
        previous parent
        """
        self.parent = node

    def setPayload(self,
                   payload: Union[List[Union[Node, str]], Node, str],
                   add: bool = False) -> None:
        """
        Set node payload according to the list specified. WARNING: completely
        replaces all node's previous content. If you wish just to add child or
        CDATA - use addData or addChild methods
        """
        if not isinstance(payload, list):
            payload = [payload]
        if add:
            self.kids += payload
        else:
            self.kids = payload

    def setTag(self,
               name: str,
               attrs: Optional[Attrs] = None,
               namespace: Optional[str] = None) -> Node:
        """
        Same as getTag but if the node with specified namespace/attributes not
        found, creates such node and returns it
        """
        node = self.getTags(name, attrs, namespace=namespace, one=True)
        if node:
            return node
        return self.addChild(name, attrs, namespace=namespace)

    def setTagAttr(self,
                   tag: str,
                   attr: str,
                   val: str,
                   namespace: Optional[str] = None) -> None:
        """
        Create new node (if not already present) with name "tag" and set it's
        attribute "attr" to value "val"
        """
        try:
            self.getTag(tag, namespace=namespace).attrs[attr] = val
        except Exception:
            self.addChild(tag, namespace=namespace, attrs={attr: val})

    def setTagData(self,
                   tag: str,
                   val: str,
                   attrs: Optional[Attrs] = None) -> None:
        """
        Creates new node (if not already present) with name "tag" and
        (optionally) attributes "attrs" and sets it's CDATA to string "val"
        """
        try:
            self.getTag(tag, attrs).setData(str(val))
        except Exception:
            self.addChild(tag, attrs, payload = [str(val)])

    def getXmlLang(self) -> Optional[str]:
        lang = self.attrs.get('xml:lang')
        if lang is not None:
            return lang

        if self.parent is not None:
            return self.parent.getXmlLang()
        return None

    def has_attr(self, key: str) -> bool:
        """
        Check if node have attribute "key"
        """
        return key in self.attrs

    def __getitem__(self, item: str) -> Optional[str]:
        """
        Return node's attribute "item" value
        """
        return self.getAttr(item)

    def __setitem__(self, item: str, val: str) -> None:
        """
        Set node's attribute "item" value
        """
        self.setAttr(item, val)

    def __delitem__(self, item: str) -> None:
        """
        Delete node's attribute "item"
        """
        self.delAttr(item)

    def __contains__(self, item: str) -> bool:
        """
        Check if node has attribute "item"
        """
        return self.has_attr(item)

    def __getattr__(self, attr: str) -> Union['T', 'NT']:
        """
        Reduce memory usage caused by T/NT classes - use memory only when needed
        """
        if attr == 'T':
            self.T = T(self)
            return self.T
        if attr == 'NT':
            self.NT = NT(self)
            return self.NT
        raise AttributeError


class T:
    """
    Auxiliary class used to quick access to node's child nodes
    """

    def __init__(self, node):
        self.__dict__['node'] = node

    def __getattr__(self, attr):
        return self.node.setTag(attr)

    def __setattr__(self, attr, val):
        if isinstance(val, Node):
            Node.__init__(self.node.setTag(attr), node=val)
            return None
        return self.node.setTagData(attr, val)

    def __delattr__(self, attr):
        return self.node.delChild(attr)

class NT(T):
    """
    Auxiliary class used to quick create node's child nodes
    """

    def __getattr__(self, attr):
        return self.node.addChild(attr)

    def __setattr__(self, attr, val):
        if isinstance(val, Node):
            self.node.addChild(attr, node=val)
            return None
        return self.node.addChild(attr, payload=[val])


class NodeBuilder:
    """
    Builds a Node class minidom from data parsed to it. This class used for two
    purposes:

      1. Creation an XML Node from a textual representation. F.e. reading a
         config file. See an XML2Node method.
      2. Handling an incoming XML stream. This is done by mangling the
         __dispatch_depth parameter and redefining the dispatch method.

    You do not need to use this class directly if you do not designing your own
    XML handler
    """

    _parser: Any
    Parse: Callable[[str, bool], None]
    __depth: int
    __last_depth: int
    __max_depth: int
    _dispatch_depth: int
    _document_attrs: Optional[Attrs]
    _document_nsp: Optional[Dict[str, str]]
    _mini_dom: Optional[Node]
    last_is_data: bool
    _ptr: Optional[Node]
    data_buffer: Optional[List[str]]
    streamError: str
    _is_stream: bool

    def __init__(self,
                 data: Optional[str] = None,
                 initial_node: Optional[Node] = None,
                 dispatch_depth: int = 1,
                 finished: bool = True) -> None:
        """
        Take two optional parameters: "data" and "initial_node"

        By default class initialised with empty Node class instance. Though, if
        "initial_node" is provided it used as "starting point". You can think
        about it as of "node upgrade". "data" (if provided) feeded to parser
        immidiatedly after instance init.
        """
        self._parser = xml.parsers.expat.ParserCreate()
        self._parser.UseForeignDTD(False)
        self._parser.StartElementHandler = self.starttag
        self._parser.EndElementHandler = self.endtag
        self._parser.StartNamespaceDeclHandler = self.handle_namespace_start
        self._parser.CharacterDataHandler = self.handle_cdata
        self._parser.StartDoctypeDeclHandler = self.handle_invalid_xmpp_element
        self._parser.EntityDeclHandler = self.handle_invalid_xmpp_element
        self._parser.CommentHandler = self.handle_invalid_xmpp_element
        self._parser.ExternalEntityRefHandler = self.handle_invalid_xmpp_element
        self._parser.AttlistDeclHandler = self.handle_invalid_xmpp_element
        self._parser.ProcessingInstructionHandler = \
            self.handle_invalid_xmpp_element
        self._parser.buffer_text = True
        self.Parse = self._parser.Parse

        self.__depth = 0
        self.__last_depth = 0
        self.__max_depth = 0
        self._dispatch_depth = dispatch_depth
        self._document_attrs = None
        self._document_nsp = None
        self._mini_dom = initial_node
        self.last_is_data = True
        self._ptr = None
        self.data_buffer = None
        self.streamError = ''
        self._is_stream = not finished
        if data:
            self._parser.Parse(data, finished)

    def check_data_buffer(self) -> None:
        if self.data_buffer:
            self._ptr.data.append(''.join(self.data_buffer))
            del self.data_buffer[:]
            self.data_buffer = None

    def destroy(self) -> None:
        """
        Method used to allow class instance to be garbage-collected
        """
        self.check_data_buffer()
        self._parser.StartElementHandler = None
        self._parser.EndElementHandler = None
        self._parser.CharacterDataHandler = None
        self._parser.StartNamespaceDeclHandler = None

    def starttag(self, tag: str, attrs: Attrs) -> None:
        """
        XML Parser callback. Used internally
        """
        self.check_data_buffer()
        self._inc_depth()
        log.debug("STARTTAG.. DEPTH -> %i , tag -> %s, attrs -> %s",
                  self.__depth, tag, attrs)
        if self.__depth == self._dispatch_depth:
            if not self._mini_dom:
                self._mini_dom = Node(tag=tag,
                                      attrs=attrs,
                                      nsp=self._document_nsp,
                                      node_built=True)
            else:
                Node.__init__(self._mini_dom,
                              tag=tag,
                              attrs=attrs,
                              nsp=self._document_nsp,
                              node_built=True)
            self._ptr = self._mini_dom
        elif self.__depth > self._dispatch_depth:
            self._ptr.kids.append(Node(tag=tag,
                                       parent=self._ptr,
                                       attrs=attrs,
                                       node_built=True))
            self._ptr = self._ptr.kids[-1]
        if self.__depth == 1:
            self._document_attrs = {}
            self._document_nsp = {}
            nsp, name = (['']+tag.split(':'))[-2:]
            for attr, val in attrs.items():
                if attr == 'xmlns':
                    self._document_nsp[''] = val
                elif attr.startswith('xmlns:'):
                    self._document_nsp[attr[6:]] = val
                else:
                    self._document_attrs[attr] = val
            ns = self._document_nsp.get(
                nsp, 'http://www.gajim.org/xmlns/undeclared-root')
            try:
                header = Node(tag=tag,
                              attrs=attrs,
                              nsp=self._document_nsp, node_built=True)
                self.dispatch(header)
                self._check_stream_start(ns, name)
            except ValueError as error:
                self._document_attrs = None
                raise ValueError(str(error))
        if not self.last_is_data and self._ptr.parent:
            self._ptr.parent.data.append('')
        self.last_is_data = False

    def _check_stream_start(self, ns: str, tag: str) -> None:
        if self._is_stream:
            if ns != 'http://etherx.jabber.org/streams' or tag != 'stream':
                raise ValueError('Incorrect stream start: (%s,%s). Terminating.'
                                 % (tag, ns))
        else:
            self.stream_header_received()

    def endtag(self, tag: str) -> None:
        """
        XML Parser callback. Used internally
        """
        log.debug("DEPTH -> %i , tag -> %s", self.__depth, tag)
        self.check_data_buffer()
        if self.__depth == self._dispatch_depth:
            if self._mini_dom.getName() == 'error':
                children = self._mini_dom.getChildren()
                if children:
                    self.streamError = children[0].getName()
                else:
                    self.streamError = self._mini_dom.getData()
            self.dispatch(self._mini_dom)
        elif self.__depth > self._dispatch_depth:
            self._ptr = self._ptr.parent
        else:
            log.debug("Got higher than dispatch level. Stream terminated?")
        self._dec_depth()
        self.last_is_data = False
        if self.__depth == 0:
            self.stream_footer_received()

    def handle_cdata(self, data: str) -> None:
        if self.last_is_data:
            if self.data_buffer:
                self.data_buffer.append(data)
        elif self._ptr:
            self.data_buffer = [data]
            self.last_is_data = True

    @staticmethod
    def handle_invalid_xmpp_element(*args: Any) -> None:
        raise ExpatError('Found invalid xmpp stream element: %s' % str(args))

    def handle_namespace_start(self, _prefix: str, _uri: str) -> None:
        """
        XML Parser callback. Used internally
        """
        self.check_data_buffer()

    def getDom(self) -> Optional[Node]:
        """
        Return just built Node
        """
        self.check_data_buffer()
        return self._mini_dom

    def dispatch(self, stanza: Any) -> None:
        """
        Get called when the NodeBuilder reaches some level of depth on it's way
        up with the built node as argument. Can be redefined to convert incoming
        XML stanzas to program events
        """

    def stream_header_received(self) -> None:
        """
        Method called when stream just opened
        """
        self.check_data_buffer()

    def stream_footer_received(self) -> None:
        """
        Method called when stream just closed
        """
        self.check_data_buffer()

    def has_received_endtag(self, level: int = 0) -> bool:
        """
        Return True if at least one end tag was seen (at level)
        """
        return self.__depth <= level < self.__max_depth

    def _inc_depth(self) -> None:
        self.__last_depth = self.__depth
        self.__depth += 1
        self.__max_depth = max(self.__depth, self.__max_depth)

    def _dec_depth(self) -> None:
        self.__last_depth = self.__depth
        self.__depth -= 1

def XML2Node(xml_str: str) -> Optional[Node]:
    """
    Convert supplied textual string into XML node. Handy f.e. for reading
    configuration file. Raises xml.parser.expat.parsererror if provided string
    is not well-formed XML
    """
    return NodeBuilder(xml_str).getDom()

def BadXML2Node(xml_str: str) -> Optional[Node]:
    """
    Convert supplied textual string into XML node. Survives if xml data is
    cutted half way round. I.e. "<html>some text <br>some more text". Will raise
    xml.parser.expat.parsererror on misplaced tags though. F.e. "<b>some text
    <br>some more text</b>" will not work
    """
    return NodeBuilder(xml_str).getDom()
