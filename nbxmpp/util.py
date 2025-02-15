# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import TYPE_CHECKING

import base64
import binascii
import hashlib
import logging
import os
import re
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from logging import LoggerAdapter

from gi.repository import Gio
from gi.repository import Soup
from packaging.version import Version

from nbxmpp.const import GIO_TLS_ERRORS
from nbxmpp.const import GLIB_VERSION
from nbxmpp.const import SOUP_ENCODING
from nbxmpp.modules.dataforms import DataForm
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import DiscoInfoMalformed
from nbxmpp.protocol import JID
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.protocol import StreamHeader
from nbxmpp.protocol import WebsocketOpenHeader
from nbxmpp.simplexml import Node
from nbxmpp.structs import CommonError
from nbxmpp.structs import DiscoIdentity
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import HTTPUploadError
from nbxmpp.structs import IqProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import Properties
from nbxmpp.structs import StanzaMalformedError
from nbxmpp.third_party import hsluv

if TYPE_CHECKING:
    from nbxmpp.protocol import Protocol

log = logging.getLogger("nbxmpp.util")


def b64decode(data: str | bytes) -> bytes:
    if not data:
        raise ValueError("No data to decode")

    if isinstance(data, str):
        data = data.encode()

    return base64.b64decode(data)


def b64encode(data: str | bytes) -> str:
    if not data:
        raise ValueError("No data to encode")

    if isinstance(data, str):
        data = data.encode()

    result = base64.b64encode(data)
    return result.decode()


def get_properties_struct(
    name: str, own_jid: JID
) -> MessageProperties | IqProperties | PresenceProperties | Properties:
    if name == "message":
        return MessageProperties(own_jid)
    if name == "iq":
        return IqProperties(own_jid)
    if name == "presence":
        return PresenceProperties(own_jid)
    return Properties()


def from_xs_boolean(value: str) -> bool:
    if value in ("1", "true", "True"):
        return True

    if value in ("0", "false", "False", ""):
        return False

    raise ValueError("Cant convert %s to python boolean" % value)


def to_xs_boolean(value: bool | None) -> Literal["true", "false"]:
    # Convert to xs:boolean ('true', 'false')
    # from a python boolean (True, False) or None
    if value is True:
        return "true"

    if value is False:
        return "false"

    if value is None:
        return "false"

    raise ValueError("Cant convert %s to xs:boolean" % value)


error_classes = {Namespace.HTTPUPLOAD_0: HTTPUploadError}


def error_factory(
    stanza: Protocol, condition: str | None = None, text: str | None = None
) -> Any:
    if condition == "stanza-malformed":
        return StanzaMalformedError(stanza, text)
    app_namespace = stanza.getAppErrorNamespace()
    return error_classes.get(app_namespace, CommonError)(stanza)


def clip_rgb(red: float, green: float, blue: float) -> tuple[float, float, float]:
    return (
        min(max(red, 0), 1),
        min(max(green, 0), 1),
        min(max(blue, 0), 1),
    )


def text_to_hue(text: str) -> float:
    hash_ = hashlib.sha1()
    hash_.update(text.encode())
    return int.from_bytes(hash_.digest()[:2], "little") / 65536 * 360


def hsluv_to_rgb(
    hue: float,
    saturation: float,
    lightness: float,
) -> tuple[float, float, float]:
    return clip_rgb(*hsluv.hsluv_to_rgb((hue, saturation, lightness)))  # type: ignore


@lru_cache(maxsize=1024)
def text_to_color(
    text: str,
    saturation: float,
    lightness: float,
) -> tuple[float, float, float]:
    """
    Combines algorithms from XEP-0392 (version 0.8.0
    <https://xmpp.org/extensions/attic/xep-0392-0.8.0.html>):
        5.1 Angle generation,
        5.4 RGB generation.

    Input:
        text: the subject to compute hue for,
        saturation ∈ [0, 100],
        lightness ∈ [0, 100].

    Returns color in sRGB color space: r, g, b ∈ [0, 1].
    """
    return hsluv_to_rgb(text_to_hue(text), saturation, lightness)


def compute_caps_hash(info: DiscoInfo, compare: bool = True) -> str:
    """
    Compute caps hash according to XEP-0115, V1.5
    https://xmpp.org/extensions/xep-0115.html#ver-proc

    :param: info    DiscoInfo
    :param: compare If True an exception is raised if the hash announced in
                    the node attr is not equal to what is calculated
    """
    # Initialize an empty string S.
    string_ = ""

    # Sort the service discovery identities by category and then by type and
    # then by xml:lang (if it exists), formatted as
    # CATEGORY '/' [TYPE] '/' [LANG] '/' [NAME]. Note that each slash is
    # included even if the LANG or NAME is not included (in accordance with
    # XEP-0030, the category and type MUST be included).
    # For each identity, append the 'category/type/lang/name' to S, followed by
    # the '<' character.
    # Sort the supported service discovery features.

    def sort_identities_key(i: DiscoIdentity) -> tuple[str, str, str]:
        return (i.category, i.type, i.lang or "")

    identities = sorted(info.identities, key=sort_identities_key)
    for identity in identities:
        string_ += "%s<" % str(identity)

    # If the response includes more than one service discovery identity with
    # the same category/type/lang/name, consider the entire response
    # to be ill-formed.
    if len(set(identities)) != len(identities):
        raise DiscoInfoMalformed("Non-unique identity found")

    # Sort the supported service discovery features.
    # For each feature, append the feature to S, followed by the '<' character.
    features = sorted(info.features)
    for feature in features:
        string_ += "%s<" % feature

    # If the response includes more than one service discovery feature with the
    # same XML character data, consider the entire response to be ill-formed.
    if len(set(features)) != len(features):
        raise DiscoInfoMalformed("Non-unique feature found")

    # If the response includes more than one extended service discovery
    # information form with the same FORM_TYPE or the FORM_TYPE field contains
    # more than one <value/> element with different XML character data,
    # consider the entire response to be ill-formed.

    # If the response includes an extended service discovery information form
    # where the FORM_TYPE field is not of type "hidden" or the form does not
    # include a FORM_TYPE field, ignore the form but continue processing.

    dataforms: list[DataForm] = []
    form_type_values: list[Any] = []
    for dataform in info.dataforms:
        form_type = dataform.vars.get("FORM_TYPE")
        if form_type is None:
            # Ignore dataform because of missing FORM_TYPE
            continue
        if form_type.type_ != "hidden":
            # Ignore dataform because of wrong type
            continue

        values = form_type.getTags("value")
        if len(values) != 1:
            raise DiscoInfoMalformed("Form should have exactly " "one FORM_TYPE value")
        value = values[0].getData()

        dataforms.append(dataform)
        form_type_values.append(value)

    if len(set(form_type_values)) != len(form_type_values):
        raise DiscoInfoMalformed("Non-unique FORM_TYPE value found")

    # If the service discovery information response includes XEP-0128 data
    # forms, sort the forms by the FORM_TYPE (i.e., by the XML character data
    # of the <value/> element).

    # For each extended service discovery information form:
    #   - Append the XML character data of the FORM_TYPE field's <value/>
    #     element, followed by the '<' character.
    #   - Sort the fields by the value of the "var" attribute.
    #   - For each field other than FORM_TYPE:
    #       - Append the value of the "var" attribute, followed by the
    #         '<' character.
    #       - Sort values by the XML character data of the <value/> element.
    #       - For each <value/> element, append the XML character data,
    #         followed by the '<' character.

    def sort_dataforms_key(dataform: DataForm):
        return dataform["FORM_TYPE"].getTagData("value")

    dataforms = sorted(dataforms, key=sort_dataforms_key)
    for dataform in dataforms:
        string_ += "%s<" % dataform["FORM_TYPE"].getTagData("value")

        fields = {}
        for field in dataform.iter_fields():
            if field.var == "FORM_TYPE":
                continue
            values = field.getTags("value")
            fields[field.var] = sorted([value.getData() for value in values])

        for var in sorted(fields.keys()):
            string_ += "%s<" % var
            for value in fields[var]:
                string_ += "%s<" % value

    hash_ = hashlib.sha1(string_.encode())
    b64hash = b64encode(hash_.digest())
    if compare and b64hash != info.get_caps_hash():
        raise DiscoInfoMalformed(
            "Caps hashes differ: %s != %s" % (b64hash, info.get_caps_hash())
        )
    return b64hash


def generate_id() -> str:
    return str(uuid.uuid4())


def get_form(stanza: Node, form_type: Any) -> Any:
    forms = stanza.getTags("x", namespace=Namespace.DATA)
    if not forms:
        return None

    for form in forms:
        form = extend_form(node=form)
        field = form.vars.get("FORM_TYPE")
        if field is None:
            continue

        if field.value == form_type:
            return form
    return None


def validate_stream_header(stanza: Node, domain: str, is_websocket: bool) -> str:
    attrs = stanza.getAttrs()
    if attrs.get("from") != domain:
        raise StanzaMalformed("Invalid from attr in stream header")

    if is_websocket:
        if attrs.get("xmlns") != Namespace.FRAMING:
            raise StanzaMalformed("Invalid namespace in stream header")
    else:
        if attrs.get("xmlns:stream") != Namespace.STREAMS:
            raise StanzaMalformed("Invalid stream namespace in stream header")
        if attrs.get("xmlns") != Namespace.CLIENT:
            raise StanzaMalformed("Invalid namespace in stream header")

    if attrs.get("version") != "1.0":
        raise StanzaMalformed("Invalid stream version in stream header")
    stream_id = attrs.get("id")
    if stream_id is None:
        raise StanzaMalformed("No stream id found in stream header")
    return stream_id


def get_stream_header(domain: str, lang: str, is_websocket: bool) -> str:
    if is_websocket:
        return str(WebsocketOpenHeader(domain, lang))
    header = StreamHeader(domain, lang)
    return "<?xml version='1.0'?>%s>" % str(header)[:-3]


def utf8_decode(data: bytes) -> tuple[str, bytes]:
    """
    Decodes utf8 byte string to unicode string
    Does handle invalid utf8 sequences by splitting
    the invalid sequence at the end

    returns (decoded unicode string, invalid byte sequence)
    """
    try:
        return data.decode(), b""
    except UnicodeDecodeError:
        for i in range(-1, -4, -1):
            char = data[i]
            if char & 0xC0 == 0x80:
                continue
            return data[:i].decode(), data[i:]
        raise


def get_rand_number() -> int:
    return int(binascii.hexlify(os.urandom(6)), 16)


def get_invalid_xml_regex() -> re.Pattern[str]:
    # \ufddo -> \ufdef range
    c = "\ufdd0"
    r = c
    while c < "\ufdef":
        c = chr(ord(c) + 1)
        r += "|" + c

    # \ufffe-\uffff, \u1fffe-\u1ffff, ..., \u10fffe-\u10ffff
    c = "\ufffe"
    r += "|" + c
    r += "|" + chr(ord(c) + 1)
    while c < "\U0010fffe":
        c = chr(ord(c) + 0x10000)
        r += "|" + c
        r += "|" + chr(ord(c) + 1)

    return re.compile(r)


def get_tls_error_phrase(tls_error: Gio.TlsCertificateFlags) -> str | None:
    phrase = GIO_TLS_ERRORS.get(tls_error)
    if phrase is None:
        return GIO_TLS_ERRORS.get(Gio.TlsCertificateFlags.GENERIC_ERROR)
    return phrase


def convert_tls_error_flags(
    flags: Gio.TlsCertificateFlags | None,
) -> set[Gio.TlsCertificateFlags]:
    if not flags:
        return set()

    # If GLib ever adds more flags GIO_TLS_ERRORS have to
    # be extended, otherwise errors go unnoticed
    if Gio.TlsCertificateFlags.VALIDATE_ALL != 127:
        raise ValueError

    return set(filter(lambda error: error & flags, GIO_TLS_ERRORS.keys()))


def convert_soup_encoding(flags: int) -> set[Soup.Encoding]:
    return set(filter(lambda enc: enc & flags, SOUP_ENCODING))


def get_websocket_close_string(websocket: Soup.WebsocketConnection) -> str:
    data = websocket.get_close_data()
    code = websocket.get_close_code()

    if code is None and data is None:
        return ""
    return " Data: %s Code: %s" % (data, code)


def is_websocket_close(stanza: Node) -> bool:
    return stanza.getName() == "close" and stanza.getNamespace() == Namespace.FRAMING


def is_websocket_stream_error(stanza: Node) -> bool:
    return stanza.getName() == "error" and stanza.getNamespace() == Namespace.STREAMS


def min_version(name: str, min_version: str) -> bool:
    if name == "GLib":
        return GLIB_VERSION >= Version(min_version)
    raise ValueError("Unknown library name")


class Observable:
    def __init__(self, log_: logging.Logger | LogAdapter) -> None:
        self._log = log_
        self._frozen = False
        self._callbacks: defaultdict[str, list[Callable[..., Any]]] = defaultdict(list)

    def remove_subscriptions(self) -> None:
        self._callbacks = defaultdict(list)

    def subscribe(self, signal_name: str, func: Callable[..., Any]) -> None:
        self._callbacks[signal_name].append(func)

    def notify(self, signal_name: str, *args: Any, **kwargs: dict[str, Any]) -> None:
        if self._frozen:
            self._frozen = False
            return

        self._log.info("Signal: %s", signal_name)
        callbacks = self._callbacks.get(signal_name, [])
        for func in callbacks:
            func(self, signal_name, *args, **kwargs)


class LogAdapter(LoggerAdapter):

    def set_context(self, context: str) -> None:
        self.extra["context"] = context

    def process(self, msg: str, kwargs: Any) -> str:
        return "(%s) %s" % (self.extra["context"], msg), kwargs


def parse_websocket_uri(data: str) -> str:
    """
    Example:
    <?xml version='1.0' encoding='utf-8'?>
    <XRD xmlns='http://docs.oasis-open.org/ns/xri/xrd-1.0'>
      <Link rel='urn:xmpp:alt-connections:xbosh'
            href='https://bosh.domain.org/'/>
      <Link rel='urn:xmpp:alt-connections:websocket'
            href='wss://ws.domain.org/'/>
    </XRD>
    """
    host_meta_xml = ET.fromstring(data)
    for link in host_meta_xml.findall(f"{{{Namespace.XRD}}}Link"):
        if link.attrib.get("rel") == "urn:xmpp:alt-connections:websocket":
            href = link.attrib.get("href")
            if href is None:
                raise ValueError("No href attr found")
            return href
    raise ValueError("no websocket uri found")
