# Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

# XEP-0004: Data Forms

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Union

from collections.abc import Iterator

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.simplexml import Node

FieldT = Union[
    "BooleanField",
    "StringField",
    "JidMultiField",
    "JidSingleField",
    "ListMultiField",
    "ListSingleField",
    "TextMultiField",
]


# exceptions used in this module
class Error(Exception):
    pass


# when we get nbxmpp.Node which we do not understand
class UnknownDataForm(Error):
    pass


# when we get nbxmpp.Node which contains bad fields
class WrongFieldValue(Error):
    pass


# helper class to change class of already existing object
class ExtendedNode(Node):
    @classmethod
    def __new__(cls, *args: Any, **kwargs: Any):
        if "extend" not in kwargs or not kwargs["extend"]:
            return object.__new__(cls)

        extend = kwargs["extend"]
        assert issubclass(cls, extend.__class__)
        extend.__class__ = cls
        return extend


# helper to create fields from scratch
def create_field(typ: str, **attrs: Any) -> FieldT:
    """Helper function to create a field of given type."""
    field: FieldT = {
        "boolean": BooleanField,
        "fixed": StringField,
        "hidden": StringField,
        "text-private": StringField,
        "text-single": StringField,
        "jid-multi": JidMultiField,
        "jid-single": JidSingleField,
        "list-multi": ListMultiField,
        "list-single": ListSingleField,
        "text-multi": TextMultiField,
    }[typ](typ=typ, **attrs)
    return field


def extend_field(node: Node) -> FieldT:
    """
    Helper function to extend a node to field of appropriate type
    """
    # when validation (XEP-122) will go in, we could have another classes
    # like DateTimeField - so that dicts in create_field() and
    # extend_field() will be different...
    typ = node.getAttr("type")
    field = {
        "boolean": BooleanField,
        "fixed": StringField,
        "hidden": StringField,
        "text-private": StringField,
        "text-single": StringField,
        "jid-multi": JidMultiField,
        "jid-single": JidSingleField,
        "list-multi": ListMultiField,
        "list-single": ListSingleField,
        "text-multi": TextMultiField,
    }
    if typ not in field:
        typ = "text-single"
    return field[typ](extend=node)


def extend_form(node: Node) -> SimpleDataForm | MultipleDataForm:
    """
    Helper function to extend a node to form of appropriate type
    """
    if node.getTag("reported") is not None:
        return MultipleDataForm(extend=node)
    return SimpleDataForm(extend=node)


class DataField(ExtendedNode):
    """
    Keeps data about one field - var, field type, labels, instructions... Base
    class for different kinds of fields. Use create_field() function to
    construct one of these
    """

    def __init__(
        self,
        typ: str | None = None,
        var: str | None = None,
        value: str | None = None,
        label: str | None = None,
        desc: str | None = None,
        required: bool = False,
        options: list[tuple[str, str]] | None = None,
        extend: Node | None = None,
    ) -> None:

        if extend is None:
            ExtendedNode.__init__(self, "field")

            self.type_ = typ
            self.var = var
            if value is not None:
                self.value = value
            if label is not None:
                self.label = label
            if desc is not None:
                self.desc = desc
            self.required = required
            self.options = options

    @property
    def type_(self) -> str:
        """
        Type of field. Recognized values are: 'boolean', 'fixed', 'hidden',
        'jid-multi', 'jid-single', 'list-multi', 'list-single', 'text-multi',
        'text-private', 'text-single'. If you set this to something different,
        DataField will store given name, but treat all data as text-single
        """
        type_ = self.getAttr("type")
        if type_ is None:
            return "text-single"
        return type_

    @type_.setter
    def type_(self, value: str) -> None:
        assert isinstance(value, str)
        self.setAttr("type", value)

    @property
    def var(self) -> str:
        """
        Field identifier
        """
        return self.getAttr("var")

    @var.setter
    def var(self, value: str) -> None:
        assert isinstance(value, str)
        self.setAttr("var", value)

    @var.deleter
    def var(self) -> None:
        self.delAttr("var")

    @property
    def label(self) -> str:
        """
        Human-readable field name
        """
        label_ = self.getAttr("label")
        if not label_:
            label_ = self.var
        return label_

    @label.setter
    def label(self, value: str) -> None:
        assert isinstance(value, str)
        self.setAttr("label", value)

    @label.deleter
    def label(self) -> None:
        if self.getAttr("label"):
            self.delAttr("label")

    @property
    def description(self) -> str:
        """
        Human-readable description of field meaning
        """
        return self.getTagData("desc") or ""

    @description.setter
    def description(self, value: str) -> None:
        assert isinstance(value, str)
        if value == "":
            del self.description
        else:
            self.setTagData("desc", value)

    @description.deleter
    def description(self) -> None:
        desc = self.getTag("desc")
        if desc is not None:
            self.delChild(desc)

    @property
    def required(self) -> bool:
        """
        Controls whether this field required to fill. Boolean
        """
        return bool(self.getTag("required"))

    @required.setter
    def required(self, value: bool) -> None:
        required = self.getTag("required")
        if required and not value:
            self.delChild(required)
        elif not required and value:
            self.addChild("required")

    @property
    def media(self) -> Media | None:
        """
        Media data
        """
        media = self.getTag("media", namespace=Namespace.DATA_MEDIA)
        if media:
            return Media(media)
        return None

    @media.setter
    def media(self, value: Media) -> None:
        del self.media
        self.addChild(node=value)

    @media.deleter
    def media(self) -> None:
        media = self.getTag("media")
        if media is not None:
            self.delChild(media)

    def is_valid(self) -> tuple[bool, str]:
        return True, ""


class Uri(Node):
    def __init__(self, uri_tag: Node) -> None:
        Node.__init__(self, node=uri_tag)

    @property
    def type_(self) -> str | None:
        """
        uri type
        """
        return self.getAttr("type")

    @type_.setter
    def type_(self, value: str) -> None:
        self.setAttr("type", value)

    @type_.deleter
    def type_(self) -> None:
        self.delAttr("type")

    @property
    def uri_data(self) -> str:
        """
        uri data
        """
        return self.getData()

    @uri_data.setter
    def uri_data(self, value: str) -> None:
        self.setData(value)

    @uri_data.deleter
    def uri_data(self) -> None:
        self.setData(None)


class Media(Node):
    def __init__(self, media_tag: Node) -> None:
        Node.__init__(self, node=media_tag)

    @property
    def uris(self) -> list[Uri]:
        """
        URIs of the media element.
        """
        return list(map(Uri, self.getTags("uri")))

    @uris.setter
    def uris(self, value: list[Uri]) -> None:
        del self.uris
        for uri in value:
            self.addChild(node=uri)

    @uris.deleter
    def uris(self) -> None:
        for element in self.getTags("uri"):
            self.delChild(element)


class BooleanField(DataField):
    @property
    def value(self) -> bool:
        """
        Value of field. May contain True, False or None
        """
        value = self.getTagData("value")
        if value in ("0", "false"):
            return False
        if value in ("1", "true"):
            return True
        if value is None:
            return False  # default value is False
        raise WrongFieldValue

    @value.setter
    def value(self, value: bool) -> None:
        self.setTagData("value", (value and "1") or "0")

    @value.deleter
    def value(self) -> None:
        value = self.getTag("value")
        if value is not None:
            self.delChild(value)


class StringField(DataField):
    """
    Covers fields of types: fixed, hidden, text-private, text-single
    """

    @property
    def value(self) -> str:
        """
        Value of field. May be any string
        """
        return self.getTagData("value") or ""

    @value.setter
    def value(self, value: str) -> None:
        if value is None:  # type: ignore
            value = ""
        self.setTagData("value", value)

    @value.deleter
    def value(self) -> None:
        try:
            self.delChild(self.getTag("value"))  # type: ignore
        except ValueError:  # if there already were no value tag
            pass

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ""
        if not self.value:
            return False, ""
        return True, ""


class ListField(DataField):
    """
    Covers fields of types: jid-multi, jid-single, list-multi, list-single
    """

    @property
    def options(self) -> list[tuple[str, Any]]:
        """
        Options
        """
        options: list[tuple[str, Any]] = []
        for element in self.getTags("option"):
            value = element.getTagData("value")
            if value is None:
                raise WrongFieldValue
            label = element.getAttr("label")
            if not label:
                label = value
            options.append((label, value))
        return options

    @options.setter
    def options(self, values: list[tuple[Any, str]]) -> None:
        del self.options
        for value, label in values:
            self.addChild("option", {"label": label}).setTagData("value", value)

    @options.deleter
    def options(self) -> None:
        for element in self.getTags("option"):
            self.delChild(element)

    def iter_options(self) -> Iterator[tuple[Any, str]]:
        for element in self.iterTags("option"):
            value = element.getTagData("value")
            if value is None:
                raise WrongFieldValue
            label = element.getAttr("label")
            if not label:
                label = value
            yield (value, label)


class ListSingleField(ListField, StringField):
    """
    Covers list-single field
    """

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ""
        if not self.value:
            return False, ""
        return True, ""


class JidSingleField(ListSingleField):
    """
    Covers jid-single fields
    """

    def is_valid(self) -> tuple[bool, str]:
        if self.value:
            try:
                JID.from_string(self.value)
                return True, ""
            except Exception as error:
                return False, str(error)
        if self.required:
            return False, ""
        return True, ""


class ListMultiField(ListField):
    """
    Covers list-multi fields
    """

    @property
    def values(self) -> list[str]:
        """
        Values held in field
        """
        values: list[str] = []
        for element in self.getTags("value"):
            values.append(element.getData())
        return values

    @values.setter
    def values(self, values: list[Any]) -> None:
        del self.values
        for value in values:
            self.addChild("value").setData(value)

    @values.deleter
    def values(self) -> None:
        for element in self.getTags("value"):
            self.delChild(element)

    def iter_values(self) -> Iterator[str]:
        for element in self.getTags("value"):
            yield element.getData()

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ""
        if not self.values:
            return False, ""
        return True, ""


class JidMultiField(ListMultiField):
    """
    Covers jid-multi fields
    """

    def is_valid(self) -> tuple[bool, str]:
        if self.values:
            for value in self.values:
                try:
                    JID.from_string(value)
                except Exception as error:
                    return False, str(error)
            return True, ""
        if self.required:
            return False, ""
        return True, ""


class TextMultiField(DataField):
    @property
    def value(self) -> str:
        """
        Value held in field
        """
        value = ""
        for element in self.iterTags("value"):
            value += "\n" + element.getData()
        return value[1:]

    @value.setter
    def value(self, value: str) -> None:
        del self.value
        if value == "":
            return
        for line in value.split("\n"):
            self.addChild("value").setData(line)

    @value.deleter
    def value(self) -> None:
        for element in self.getTags("value"):
            self.delChild(element)

    def is_valid(self) -> tuple[bool, str]:
        if not self.required:
            return True, ""
        if not self.value:
            return False, ""
        return True, ""


class DataRecord(ExtendedNode):
    """
    The container for data fields - an xml element which has DataField elements
    as children
    """

    def __init__(
        self,
        fields: list[FieldT] | None = None,
        associated: SimpleDataForm | None = None,
        extend: Node | None = None,
    ) -> None:
        self.associated = associated
        self.vars: dict[str, FieldT] = {}
        if extend is None:
            # we have to build this object from scratch
            Node.__init__(self)

            if fields is not None:
                self.fields = fields
        else:
            # we already have nbxmpp.Node inside - try to convert all
            # fields into DataField objects
            if fields is None:
                for field in self.iterTags("field"):
                    if not isinstance(field, DataField):
                        extend_field(field)
                    self.vars[field.var] = field
            else:
                self.fields = fields

    @property
    def fields(self) -> list[FieldT]:
        """
        List of fields in this record
        """
        return self.getTags("field")

    @fields.setter
    def fields(self, fields: list[FieldT]) -> None:
        del self.fields
        for field in fields:
            if not isinstance(field, DataField):
                extend_field(field)
            self.addChild(node=field)
            self.vars[field.var] = field

    @fields.deleter
    def fields(self) -> None:
        for element in self.getTags("field"):
            self.delChild(element)
            self.vars.clear()

    def iter_fields(self) -> Iterator[FieldT]:
        """
        Iterate over fields in this record. Do not take associated into account
        """
        yield from self.iterTags("field")

    def iter_with_associated(self) -> Iterator[tuple[Node, FieldT]]:
        """
        Iterate over associated, yielding both our field and associated one
        together
        """
        for field in self.associated.iter_fields():
            yield self[field.var], field

    def __getitem__(self, item: str) -> FieldT:
        return self.vars[item]

    def is_valid(self) -> bool:
        return all(field.is_valid()[0] for field in self.iter_fields())

    def is_fake_form(self) -> bool:
        return bool(self.vars.get("fakeform", False))


class DataForm(ExtendedNode):
    def __init__(
        self,
        type_: str | None = None,
        title: str | None = None,
        instructions: str | None = None,
        extend: Node | None = None,
    ) -> None:
        if extend is None:
            # we have to build form from scratch
            Node.__init__(self, "x", attrs={"xmlns": Namespace.DATA})

        if type_ is not None:
            self.type_ = type_
        if title is not None:
            self.title = title
        if instructions is not None:
            self.instructions = instructions

    @property
    def type_(self) -> str | None:
        """
        Type of the form. Must be one of: 'form', 'submit', 'cancel', 'result'.
        'form' - this form is to be filled in; you will be able soon to do:
        filledform = DataForm(replyto=thisform)
        """
        return self.getAttr("type")

    @type_.setter
    def type_(self, type_: Literal["form", "submit", "cancel", "result"]) -> None:
        assert type_ in ("form", "submit", "cancel", "result")
        self.setAttr("type", type_)

    @property
    def title(self) -> str | None:
        """
        Title of the form

        Human-readable, should not contain any \\r\\n.
        """
        return self.getTagData("title")

    @title.setter
    def title(self, title: str) -> None:
        self.setTagData("title", title)

    @title.deleter
    def title(self) -> None:
        try:
            self.delChild("title")
        except ValueError:
            pass

    @property
    def instructions(self) -> str:
        """
        Instructions for this form

        Human-readable, may contain \\r\\n.
        """
        # TODO: the same code is in TextMultiField. join them
        value = ""
        for valuenode in self.getTags("instructions"):
            value += "\n" + valuenode.getData()
        return value[1:]

    @instructions.setter
    def instructions(self, value: str) -> None:
        del self.instructions
        if value == "":
            return
        for line in value.split("\n"):
            self.addChild("instructions").setData(line)

    @instructions.deleter
    def instructions(self) -> None:
        for value in self.getTags("instructions"):
            self.delChild(value)

    @property
    def is_reported(self) -> bool:
        return self.getTag("reported") is not None


class SimpleDataForm(DataForm, DataRecord):
    def __init__(
        self,
        type_: str | None = None,
        title: str | None = None,
        instructions: str | None = None,
        fields: list[FieldT] | None = None,
        extend: SimpleDataForm | Node | None = None,
    ) -> None:
        DataForm.__init__(
            self, type_=type_, title=title, instructions=instructions, extend=extend
        )
        DataRecord.__init__(self, fields=fields, extend=self, associated=self)

    def get_purged(self) -> SimpleDataForm:
        simple_form = SimpleDataForm(extend=self)
        del simple_form.title
        simple_form.instructions = ""
        to_be_removed: list[FieldT] = []
        for field in simple_form.iter_fields():
            if field.required:
                # add <value> if there is not
                if hasattr(field, "value") and not field.value:
                    field.value = ""
                # Keep all required fields
                continue
            if (hasattr(field, "value") and not field.value and field.value != 0) or (
                hasattr(field, "values") and not field.values
            ):
                to_be_removed.append(field)
            else:
                del field.label
                del field.description
                del field.media
        for field in to_be_removed:
            simple_form.delChild(field)
        return simple_form


class MultipleDataForm(DataForm):
    def __init__(
        self,
        type_: str | None = None,
        title: str | None = None,
        instructions: str | None = None,
        items: list[Node] | None = None,
        extend: Node | None = None,
    ) -> None:
        DataForm.__init__(
            self, type_=type_, title=title, instructions=instructions, extend=extend
        )
        # all records, recorded into DataRecords
        if extend is None:
            if items is not None:
                self.items = items
        else:
            # we already have nbxmpp.Node inside - try to convert all
            # fields into DataField objects
            if items is None:
                self.items = list(self.iterTags("item"))
            else:
                for item in self.getTags("item"):
                    self.delChild(item)
                self.items = items
        reported_tag = self.getTag("reported")
        self.reported = DataRecord(extend=reported_tag)

    @property
    def items(self) -> list[Node]:
        """
        A list of all records
        """
        return list(self.iter_records())

    @items.setter
    def items(self, records: list[DataRecord | Node]) -> None:
        del self.items
        for record in records:
            if not isinstance(record, DataRecord):
                DataRecord(extend=record)
            self.addChild(node=record)

    @items.deleter
    def items(self) -> None:
        for record in self.getTags("item"):
            self.delChild(record)

    def iter_records(self) -> Iterator[DataRecord | Node]:
        yield from self.getTags("item")
