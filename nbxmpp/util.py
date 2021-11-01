# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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

import typing
from typing import Any
from typing import Optional
from typing import Callable
from typing import Literal
from typing import Union
from typing import cast

import base64
import hashlib
import uuid
import binascii
import os
import re
import logging
from logging import LoggerAdapter
from collections import defaultdict

from functools import lru_cache

from gi.repository import Gio

from nbxmpp.elements import Base
from nbxmpp.exceptions import DiscoInfoMalformed
from nbxmpp.const import GIO_TLS_ERRORS
from nbxmpp.namespaces import Namespace
from nbxmpp.exceptions import StanzaMalformed
from nbxmpp.structs import Properties
from nbxmpp.structs import IqProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import CommonError
from nbxmpp.structs import HTTPUploadError
from nbxmpp.structs import StanzaMalformedError
from nbxmpp.elements import Base
from nbxmpp.third_party.hsluv import hsluv_to_rgb

if typing.TYPE_CHECKING:
    from nbxmpp import types

log = logging.getLogger('nbxmpp.util')


def b64decode(data: Union[str, bytes]) -> bytes:
    if not data:
        raise ValueError('No data to decode')

    if isinstance(data, str):
        data = data.encode()

    return base64.b64decode(data)


def b64encode(data: Union[str, bytes]) -> str:
    if not data:
        raise ValueError('No data to encode')

    if isinstance(data, str):
        data = data.encode()

    result = base64.b64encode(data)
    return result.decode()


def get_properties_struct(name, own_jid):
    if name == 'message':
        return MessageProperties(own_jid)
    if name == 'iq':
        return IqProperties(own_jid)
    if name == 'presence':
        return PresenceProperties(own_jid)
    return Properties()


def from_xs_boolean(value: str) -> bool:
    if value in ('1', 'true', 'True'):
        return True

    if value in ('0', 'false', 'False', ''):
        return False

    raise ValueError('Cant convert %s to python boolean' % value)


def to_xs_boolean(value: bool) -> Literal['true', 'false']:
    # Convert to xs:boolean ('true', 'false')
    # from a python boolean (True, False) or None
    if value is True:
        return 'true'

    if value is False:
        return 'false'

    if value is None:
        return 'false'

    raise ValueError(
        'Cant convert %s to xs:boolean' % value)


error_classes = {
    Namespace.HTTPUPLOAD_0: HTTPUploadError
}

def error_factory(stanza: Node,
                  condition: Optional[str] = None,
                  text: Optional[str] = None) -> Any:
    if condition == 'stanza-malformed':
        return StanzaMalformedError(stanza, text)
    app_namespace = stanza.getAppErrorNamespace()
    return error_classes.get(app_namespace, CommonError)(stanza)


def clip_rgb(red, green, blue):
    return (
        min(max(red, 0), 1),
        min(max(green, 0), 1),
        min(max(blue, 0), 1),
    )


@lru_cache(maxsize=1024)
def text_to_color(text, background_color):
    # background color = (rb, gb, bb)
    hash_ = hashlib.sha1()
    hash_.update(text.encode())
    hue = int.from_bytes(hash_.digest()[:2], 'little') / 65536

    red, green, blue = clip_rgb(*hsluv_to_rgb((hue * 360, 100, 50)))

    rb, gb, bb = background_color

    rb_inv = 1 - rb
    gb_inv = 1 - gb
    bb_inv = 1 - bb

    rc = 0.2 * rb_inv + 0.8 * red
    gc = 0.2 * gb_inv + 0.8 * green
    bc = 0.2 * bb_inv + 0.8 * blue

    return rc, gc, bc


def compute_caps_hash(info, compare=True):
    """
    Compute caps hash according to XEP-0115, V1.5
    https://xmpp.org/extensions/xep-0115.html#ver-proc

    :param: info    DiscoInfo
    :param: compare If True an exception is raised if the hash announced in
                    the node attr is not equal to what is calculated
    """
    # Initialize an empty string S.
    string_ = ''

    # Sort the service discovery identities by category and then by type and
    # then by xml:lang (if it exists), formatted as
    # CATEGORY '/' [TYPE] '/' [LANG] '/' [NAME]. Note that each slash is
    # included even if the LANG or NAME is not included (in accordance with
    # XEP-0030, the category and type MUST be included).
    # For each identity, append the 'category/type/lang/name' to S, followed by
    # the '<' character.
    # Sort the supported service discovery features.

    def sort_identities_key(i):
        return (i.category, i.type, i.lang or '')

    identities = sorted(info.identities, key=sort_identities_key)
    for identity in identities:
        string_ += '%s<' % str(identity)

    # If the response includes more than one service discovery identity with
    # the same category/type/lang/name, consider the entire response
    # to be ill-formed.
    if len(set(identities)) != len(identities):
        raise DiscoInfoMalformed('Non-unique identity found')

    # Sort the supported service discovery features.
    # For each feature, append the feature to S, followed by the '<' character.
    features = sorted(info.features)
    for feature in features:
        string_ += '%s<' % feature

    # If the response includes more than one service discovery feature with the
    # same XML character data, consider the entire response to be ill-formed.
    if len(set(features)) != len(features):
        raise DiscoInfoMalformed('Non-unique feature found')

    # If the response includes more than one extended service discovery
    # information form with the same FORM_TYPE or the FORM_TYPE field contains
    # more than one <value/> element with different XML character data,
    # consider the entire response to be ill-formed.

    # If the response includes an extended service discovery information form
    # where the FORM_TYPE field is not of type "hidden" or the form does not
    # include a FORM_TYPE field, ignore the form but continue processing.

    dataforms = []
    form_type_values = []
    for dataform in info.dataforms:
        form_type = dataform.vars.get('FORM_TYPE')
        if form_type is None:
            # Ignore dataform because of missing FORM_TYPE
            continue
        if form_type.type_ != 'hidden':
            # Ignore dataform because of wrong type
            continue

        values = form_type.find_tags('value')
        if len(values) != 1:
            raise DiscoInfoMalformed('Form should have exactly '
                                     'one FORM_TYPE value')
        value = values[0].text or ''

        dataforms.append(dataform)
        form_type_values.append(value)

    if len(set(form_type_values)) != len(form_type_values):
        raise DiscoInfoMalformed('Non-unique FORM_TYPE value found')

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

    def sort_dataforms_key(dataform):
        return dataform['FORM_TYPE'].find_tag_text('value')

    dataforms = sorted(dataforms, key=sort_dataforms_key)
    for dataform in dataforms:
        string_ += '%s<' % dataform['FORM_TYPE'].find_tag_text('value')

        fields = {}
        for field in dataform.iter_fields():
            if field.var == 'FORM_TYPE':
                continue
            values = field.find_tags('value')
            fields[field.var] = sorted([value.text or '' for value in values])

        for var in sorted(fields.keys()):
            string_ += '%s<' % var
            for value in fields[var]:
                string_ += '%s<' % value

    hash_ = hashlib.sha1(string_.encode())
    b64hash = b64encode(hash_.digest())
    if compare and b64hash != info.get_caps_hash():
        raise DiscoInfoMalformed('Caps hashes differ: %s != %s' % (
            b64hash, info.get_caps_hash()))
    return b64hash


def generate_id() -> str:
    return str(uuid.uuid4())


def get_dataform(element: types.Base, type_: str) -> Optional[types.DataForm]:
    forms = element.find_tags('x', namespace=Namespace.DATA)
    if not forms:
        return None

    for form in forms:
        if form.type_is(type_):
            return form
    return None


def validate_stream_header(stanza: Base, domain: str, is_websocket: bool) -> str:
    if stanza.get('from') != domain:
        raise StanzaMalformed('Invalid from attr in stream header')

    if is_websocket:
        if stanza.default_namespace != Namespace.FRAMING:
            raise StanzaMalformed('Invalid namespace in stream header')
    else:
        if stanza.namespace != Namespace.STREAMS:
            raise StanzaMalformed('Invalid stream namespace in stream header')
        if stanza.default_namespace != Namespace.CLIENT:
            raise StanzaMalformed('Invalid namespace in stream header')

    if stanza.get('version') != '1.0':
        raise StanzaMalformed('Invalid stream version in stream header')
    stream_id = stanza.get('id')
    if stream_id is None:
        raise StanzaMalformed('No stream id found in stream header')
    return stream_id


def get_stream_header(domain: str, lang: str, is_websocket: bool) -> str:
    if is_websocket:
        return str(WebsocketOpenHeader(domain, lang))
    header = StreamHeader(domain, lang)
    return "<?xml version='1.0'?>%s>" % str(header)[:-3]


def utf8_decode(data: bytes) -> tuple[str, bytes]:
    '''
    Decodes utf8 byte string to unicode string
    Does handle invalid utf8 sequences by splitting
    the invalid sequence at the end

    returns (decoded unicode string, invalid byte sequence)
    '''
    try:
        return data.decode(), b''
    except UnicodeDecodeError:
        for i in range(-1, -4, -1):
            char = data[i]
            if char & 0xc0 == 0x80:
                continue
            return data[:i].decode(), data[i:]
        raise


def get_rand_number() -> int:
    return int(binascii.hexlify(os.urandom(6)), 16)


def get_invalid_xml_regex():
    # \ufddo -> \ufdef range
    c = '\ufdd0'
    r = c
    while c < '\ufdef':
        c = chr(ord(c) + 1)
        r += '|' + c

    # \ufffe-\uffff, \u1fffe-\u1ffff, ..., \u10fffe-\u10ffff
    c = '\ufffe'
    r += '|' + c
    r += '|' + chr(ord(c) + 1)
    while c < '\U0010fffe':
        c = chr(ord(c) + 0x10000)
        r += '|' + c
        r += '|' + chr(ord(c) + 1)

    return re.compile(r)


def get_tls_error_phrase(tls_error: Gio.TlsCertificateFlags) -> str:
    phrase = GIO_TLS_ERRORS.get(tls_error)
    if phrase is None:
        return cast(str, GIO_TLS_ERRORS.get(Gio.TlsCertificateFlags.GENERIC_ERROR))
    return phrase


def convert_tls_error_flags(flags: Gio.TlsCertificateFlags) -> set[Gio.TlsCertificateFlags]:
    if not flags:
        return set()

    # If GLib ever adds more flags GIO_TLS_ERRORS have to
    # be extended, otherwise errors go unnoticed
    if Gio.TlsCertificateFlags.VALIDATE_ALL != 127:
        raise ValueError

    return set(filter(lambda error: error & flags, GIO_TLS_ERRORS.keys()))


def get_websocket_close_string(websocket: Any) -> str:
    data = websocket.get_close_data()
    code = websocket.get_close_code()

    if code is None and data is None:
        return ''
    return ' Data: %s Code: %s' % (data, code)


def is_websocket_close(stanza: Node) -> bool:
    return (stanza.localname == 'close' and
            stanza.namespace == Namespace.FRAMING)


def is_websocket_stream_error(stanza: Node) -> bool:
    return (stanza.localname == 'error' and
            stanza.namespace == Namespace.STREAMS)


class Observable:
    def __init__(self, log_: logging.Logger):
        self._log = log_
        self._frozen = False
        self._callbacks: defaultdict[str, list[Callable[..., Any]]] = defaultdict(list)

    def remove_subscriptions(self):
        self._callbacks = defaultdict(list)

    def subscribe(self, signal_name: str, func: Callable[..., Any]):
        self._callbacks[signal_name].append(func)

    def notify(self, signal_name: str, *args: Any, **kwargs: dict[str, Any]):
        if self._frozen:
            self._frozen = False
            return

        self._log.info('Signal: %s', signal_name)
        callbacks = self._callbacks.get(signal_name, [])
        for func in callbacks:
            func(self, signal_name, *args, **kwargs)


class LogAdapter(LoggerAdapter):

    def set_context(self, context):
        self.extra['context'] = context

    def process(self, msg, kwargs):
        return '(%s) %s' % (self.extra['context'], msg), kwargs


def get_child_namespaces(element: Base) -> set[Base]:
    return {ele.namespace for ele in element.iterchildren()}
