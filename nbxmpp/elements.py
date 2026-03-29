from __future__ import annotations

from typing import Any
from typing import cast
from typing import Union

import copy
from collections import defaultdict
from collections.abc import Iterator

from lxml import etree

from nbxmpp.jid import JID
from nbxmpp.namespaces import Namespace

NSMap = dict[str | None, str]


def create_nsmap_and_tag(tag: str, namespace: str | None) -> tuple[str, NSMap | None]:
    nsmap: NSMap | None = None
    if namespace is not None:
        nsmap = {None: namespace}
        tag = "{%s}%s" % (namespace, tag)
    return tag, nsmap


def E(
    tag: str, text: str | None = None, namespace: str | None = None, **attrib: str
) -> Base:
    tag, nsmap = create_nsmap_and_tag(tag, namespace)

    element = cast(Base, _element_parser.makeelement(tag, nsmap=nsmap, attrib=attrib))
    if text is not None:
        element.text = text
    return element


class Base(etree.ElementBase):
    def find_tag(self, tag: str, namespace: str | None = None) -> Base | None:
        if namespace is None:
            namespace = etree.QName(self).namespace
            print(repr(namespace))
        return self.find("{%s}%s" % (namespace, tag))

    def find_tag_text(self, tag: str, namespace: str | None = None) -> str | None:
        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            return element
        return element.text

    def has_tag(self, tag: str, namespace: str | None = None) -> bool:
        return self.find_tag(tag, namespace=namespace) is not None

    def add_tag(self, tag: str, namespace: str | None = None, **attrib: str) -> Base:
        if namespace is None:
            namespace = etree.QName(self).namespace

        tag, nsmap = create_nsmap_and_tag(tag, namespace)

        element = etree.SubElement(self, tag, nsmap=nsmap, attrib=attrib)
        return element

    def add_tag_text(self, tag: str, text: str, namespace: str | None = None):
        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            element = self.add_tag(tag, namespace=namespace)
        element.text = text
        return element

    def find_tag_attr(
        self, tag: str, attr: str, namespace: str | None = None
    ) -> str | None:
        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            return element
        return element.get(attr)

    def find_tags(self, tag: str, namespace: str | None = None) -> list[Base]:
        return list(self.iter_tags(tag, namespace=namespace))

    def remove_tag(self, tag: str, namespace: str | None = None) -> Base | None:
        element = self.find_tag(tag, namespace=namespace)
        if element is None:
            return None
        self.remove(element)
        return element

    def remove_tags(self, tag: str, namespace: str | None = None) -> None:
        for element in self.find_tags(tag, namespace=namespace):
            self.remove(element)

    def iter_tags(self, tag: str, namespace: str | None = None) -> Iterator[Base]:
        if namespace is None:
            namespace = self.nsmap[self.prefix]
        return self.iterchildren("{%s}%s" % (namespace, tag))

    def get_attribs(self) -> dict[str, str]:
        return dict(self.attrib)

    def get_children(self) -> list[Base]:
        return list(self)

    @property
    def lang(self) -> str | None:
        # TODO: looks wrong
        return self.get(f"{Namespace.XML}lang")

    @property
    def localname(self) -> str:
        return etree.QName(self).localname

    @property
    def namespace(self) -> str | None:
        return etree.QName(self).namespace

    @property
    def default_namespace(self) -> str | None:
        return self.nsmap.get(None)

    def tostring(self, pretty_print: bool = False) -> str:
        # etree.indent(self, space=2 * " ")
        return etree.tostring(self, encoding="unicode", pretty_print=pretty_print)

    def __str__(self) -> str:
        return self.tostring()

    def __repr__(self) -> str:
        repr_str = super().__repr__()
        return repr_str.replace("<Element", f"<{self.__class__.__name__}")


class Stanza(Base):
    def _jid_attr_converter(self, attr: str) -> JID | None:
        jid = self.get(attr)
        if not jid:
            return None
        return JID.from_string(jid)

    def get_from(self) -> JID | None:
        return self._jid_attr_converter("from")

    def set_from(self, jid: Union[str, JID]):
        self.set("from", str(jid))

    def get_to(self) -> JID | None:
        return self._jid_attr_converter("to")

    def set_to(self, jid: Union[str, JID]):
        self.set("to", str(jid))

    def make_error(
        self, type_: str, condition: str, namespace: str, text: str | None = None
    ):
        stanza = copy.deepcopy(self)
        stanza.set("type", "error")
        stanza.set("to", stanza.get("from"))
        stanza.attrib.pop("from", "")
        error = stanza.add_tag("error", type=type_)
        error.add_tag(condition, namespace=namespace)
        if text is not None:
            error.add_tag_text("text", text, namespace=namespace)
        return stanza

    def add_error(
        self, type_: str, condition: str, namespace: str, text: str | None = None
    ):
        self.set("type", "error")
        error = self.add_tag("error", type=type_)
        error.add_tag(condition, namespace=namespace)
        if text is not None:
            error.add_tag_text("text", text, namespace=namespace)


class Nonza(Base):
    pass


class Message(Stanza):
    # def get_type(self) -> MessageType:
    #     type_ = self.get("type")
    #     if type_ is None:
    #         return MessageType.NORMAL
    #     return MessageType(type_)

    def get_body(self) -> str | None:
        return self.find_tag_text("body")

    def get_thread(self) -> str | None:
        return self.find_tag_text("thread")

    def get_subject(self) -> str | None:
        return self.find_tag_text("subject")

    # def get_xhtml(self) -> XHTML | None:
    #     return self.find_tag("html", namespace=Namespace.XHTML_IM)

    def get_origin_id(self):
        return self.find_tag_attr("origin-id", "id", namespace=Namespace.SID)

    def get_stanza_id_attrs(self) -> dict[str, str] | None:
        stanza_id = self.find_tag("stanza-id", namespace=Namespace.SID)
        if stanza_id is None:
            return None
        return stanza_id.get_attribs()

    @staticmethod
    def new(
        to: Union[str, JID], type_: str | None = None, id_: str | None = None
    ) -> Message:
        message = cast(Message, E("message", namespace="jabber:client"))

        if isinstance(to, str):
            to = JID.from_string(to)
        message.set_to(str(to))

        if type_ is not None:
            # MessageType(type_)
            message.set("type", type_)

        if id_ is not None:
            message.set("id", id_)

        return message


class Iq(Stanza):
    def is_error(self) -> bool:
        return self.get("type") == "error"

    def is_result(self) -> bool:
        return self.get("type") == "result"

    def get_query(
        self, namespace: str | None = None, node: str | None = None
    ) -> Base | None:
        if namespace is None:
            query = self.find("{*}query")
        else:
            query = self.find_tag("query", namespace=namespace)

        if query is None:
            return query

        if node is not None:
            if query.get("node") == node:
                return query
            return None

        return query

    def add_query(self, namespace: str | None = None, node: str | None = None) -> Base:
        query = self.add_tag("query", namespace=namespace)
        if node is not None:
            query.set("node", node)
        return query

    def make_result(self) -> Iq:
        return Iq.new(to=self.get("from"), type_="result", id_=self.get("id"))

    @staticmethod
    def new(
        to: Union[str, JID] | None = None,
        type_: str | None = "get",
        id_: str | None = None,
    ) -> Iq:
        iq = cast(Iq, E("iq", namespace="jabber:client"))

        # IqType(type_)
        iq.set("type", type_)

        if isinstance(to, str):
            to = JID.from_string(to)
        iq.set_to(str(to))

        if id_ is not None:
            iq.set("id", id_)

        return iq


class Presence(Stanza):
    def get_priority(self) -> str | None:
        return self.find_tag_text("priority")

    def get_show(self) -> str | None:
        return self.find_tag_text("show")

    def get_status(self) -> str | None:
        return self.find_tag_text("status")

    @staticmethod
    def new(
        to: Union[str, JID] | None = None,
        type_: str | None = None,
        id_: str | None = None,
        priority: int | None = None,
        show: str | None = None,
        status: str | None = None,
        nickname: str | None = None,
        idle_time: str | None = None,
        signed: str | None = None,
        muc_join: bool | None = False,
        muc_history: str | None = None,
        muc_password: str | None = None,
        caps: dict[str, str] | None = None,
    ) -> Presence:
        presence = cast(Presence, E("presence", namespace="jabber:client"))

        if type_ is not None:
            # PresenceType(type_)
            presence.set("type", type_)

        if to is not None:
            if isinstance(to, str):
                to = JID.from_string(to)
            presence.set_to(str(to))

        if id_ is not None:
            presence.set("id", id_)

        if priority is not None:
            if priority not in range(-128, 128):
                raise ValueError("invalid priority: %s" % priority)
            presence.add_tag_text("priority", str(priority))

        if show is not None:
            if show not in ("chat", "away", "xa", "dnd"):
                raise ValueError("invalid show value: %s" % show)
            presence.add_tag_text("show", show)

        if status is not None:
            presence.add_tag_text("status", status)

        if caps is not None and type_ != "unavailable":
            presence.add_tag("c", namespace=Namespace.CAPS, **caps)

        if nickname is not None:
            presence.add_tag_text("nick", nickname, namespace=Namespace.NICK)

        if idle_time is not None:
            presence.add_tag("idle", namespace=Namespace.IDLE, since=idle_time)

        if signed is not None:
            presence.add_tag_text("x", signed, namespace=Namespace.SIGNED)

        if muc_join or muc_history is not None or muc_password is not None:
            muc_x = presence.add_tag("x", namespace=Namespace.MUC)
            if muc_history is not None:
                muc_x.add_tag_text("history", muc_history)

            if muc_password is not None:
                muc_x.add_tag_text("password", muc_password)

        return presence


class StreamStart(Base):
    TAG = "stream"
    NAMESPACE = Namespace.STREAMS

    def tostring(self, pretty_print: bool = False) -> str:
        data = etree.tostring(self, pretty_print=False, encoding=str)
        return '<?xml version="1.0"?>' + data[:-2] + ">"

    @staticmethod
    def new(domain: str, lang: str) -> StreamStart:
        return StreamStart(
            attrib={"version": "1.0", "to": domain, f"{{{Namespace.XML}}}lang": lang},
            nsmap={
                "stream": Namespace.STREAMS,
                "xml": Namespace.XML,
                None: Namespace.CLIENT,
            },
        )


class StreamEnd(Base):
    TAG = "stream"
    NAMESPACE = Namespace.STREAMS

    def tostring(self, pretty_print: bool = False) -> str:
        return "</stream:stream>"


class Open(Base):
    TAG = "open"
    NAMESPACE = Namespace.FRAMING

    @staticmethod
    def new(domain: str, lang: str) -> Open:
        return Open(
            attrib={"version": "1.0", "to": domain, f"{{{Namespace.XML}}}lang": lang},
            nsmap={None: Namespace.FRAMING, "xml": Namespace.XML},
        )


class Close(Base):
    TAG = "close"
    NAMESPACE = Namespace.FRAMING

    @staticmethod
    def new() -> Close:
        return Close(nsmap={None: Namespace.FRAMING})


class ClassAttributeLookup(etree.PythonElementClassLookup):
    _class_lookups: dict(str, dict(str, dict(str, Any))) = defaultdict(
        lambda: defaultdict(dict)
    )

    @classmethod
    def register(cls, tag: str, attr: str, value: str | None, element_class: Any):
        cls._class_lookups[tag][attr][value] = element_class

    def lookup(self, _document: Any, element: etree._Element) -> Any | None:
        attribute_lookups = self._class_lookups.get(element.tag)
        if attribute_lookups is None:
            return None

        for attr, value_class_dict in attribute_lookups.items():
            value = element.get(attr)
            class_ = value_class_dict.get(value)
            if class_ is None:
                continue
            return class_

        return None


class SubElementLookup(etree.PythonElementClassLookup):
    _class_lookups: dict(str, dict(str, Any)) = defaultdict(dict)

    @classmethod
    def register(cls, tag: str, sub_tag: str, element_class: Any):
        cls._class_lookups[tag][sub_tag] = element_class

    def lookup(self, _document: Any, element: etree._Element) -> Any | None:
        sub_lookups = self._class_lookups.get(element.tag)
        if sub_lookups is None:
            return None

        for child in list(element):
            element_class = sub_lookups.get(child.tag)
            if element_class is not None:
                return element_class

        return None


def register_attribute_lookup(
    tag: str, attr: str, value: str | None, element_class: Any
):
    ClassAttributeLookup.register(tag, attr, value, element_class)


def register_sub_element_lookup(tag: str, sub_tag: str, element_class: Any):
    SubElementLookup.register(tag, sub_tag, element_class)


def register_class_lookup(tag: str, namespace: str, element_class: Any):
    _NamespaceLookup.get_namespace(namespace)[tag] = element_class


# Fallback order is important
_BaseLookup = etree.ElementDefaultClassLookup(element=Base)
_NamespaceLookup = etree.ElementNamespaceClassLookup(fallback=_BaseLookup)
# _SubElementLookup = SubElementLookup(fallback=_NamespaceLookup) # does not work with PullParser
_ClassAttributeLookup = ClassAttributeLookup(fallback=_NamespaceLookup)

ElementLookup = _ClassAttributeLookup

_element_parser = etree.XMLParser()
_element_parser.set_element_class_lookup(ElementLookup)


def parse(data: str) -> Base:
    return cast(Base, etree.fromstring(data, _element_parser))


register_class_lookup("iq", Namespace.CLIENT, Iq)
register_class_lookup("message", Namespace.CLIENT, Message)
register_class_lookup("presence", Namespace.CLIENT, Presence)
