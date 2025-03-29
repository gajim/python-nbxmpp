# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import Optional
from typing import TYPE_CHECKING

import binascii
import hashlib
import hmac
import logging
import os
from hashlib import pbkdf2_hmac

from gi.repository import Gio

from nbxmpp.const import StreamState
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Node
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import SASL_AUTH_MECHS
from nbxmpp.protocol import SASL_ERROR_CONDITIONS
from nbxmpp.structs import ChannelBindingData
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.util import LogAdapter

if TYPE_CHECKING:
    from nbxmpp.client import Client
    from nbxmpp.protocol import Features

log = logging.getLogger("nbxmpp.sasl")

try:
    gssapi = __import__("gssapi")
    gssapi_available = True
except (ImportError, OSError) as error:
    log.info("GSSAPI not available: %s", error)
    gssapi_available = False

GSSAPI_AVAILABLE = gssapi_available


class SASL:
    """
    Implements SASL authentication.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

        self._password: str | None = None

        self._mechanism_classes = {
            "ANONYMOUS": ANONYMOUS,
            "PLAIN": PLAIN,
            "EXTERNAL": EXTERNAL,
            "GSSAPI": GSSAPI,
            "SCRAM-SHA-1": SCRAM_SHA_1,
            "SCRAM-SHA-1-PLUS": SCRAM_SHA_1_PLUS,
            "SCRAM-SHA-256": SCRAM_SHA_256,
            "SCRAM-SHA-256-PLUS": SCRAM_SHA_256_PLUS,
            "SCRAM-SHA-512": SCRAM_SHA_512,
            "SCRAM-SHA-512-PLUS": SCRAM_SHA_512_PLUS,
        }

        self._allowed_mechs: set[str] | None = None
        self._enabled_mechs: set[str] | None = None
        self._sasl_ns: str | None = None
        self._mechanism: BaseMechanism | None = None
        self._error: tuple[str | None, str | None] | None = None

        self._log = LogAdapter(log, {"context": client.log_context})

    @property
    def error(self) -> tuple[str | None, str | None] | None:
        return self._error

    def is_sasl2(self) -> bool:
        assert self._sasl_ns is not None
        return self._sasl_ns == Namespace.SASL2

    def set_password(self, password: str | None):
        self._password = password

    @property
    def password(self) -> str | None:
        return self._password

    def delegate(self, stanza: Protocol) -> None:
        if stanza.getNamespace() != self._sasl_ns:
            return

        if stanza.getName() == "challenge":
            self._on_challenge(stanza)
        elif stanza.getName() == "failure":
            self._on_failure(stanza)
        elif stanza.getName() == "success":
            self._on_success(stanza)

    def _get_channel_binding_data(
        self, features: Features
    ) -> Optional[ChannelBindingData]:
        if self._client.tls_version != Gio.TlsProtocolVersion.TLS_1_3:
            return None

        binding_type = features.get_channel_binding_type()
        if binding_type is None:
            return None

        channel_binding_data = self._client.get_channel_binding_data(binding_type)
        if channel_binding_data is None:
            return None

        return ChannelBindingData(binding_type, channel_binding_data)

    def start_auth(self, features: Features) -> None:
        self._mechanism = None
        self._allowed_mechs = self._client.mechs
        self._enabled_mechs = self._allowed_mechs

        self._sasl_ns = Namespace.SASL
        if features.has_sasl_2():
            self._sasl_ns = Namespace.SASL2

        self._log.info("Using %s", self._sasl_ns)
        self._log.info("Allowed mechanisms: %s", self._allowed_mechs)

        self._error = None

        channel_binding_data = None
        # Segfaults see https://gitlab.gnome.org/GNOME/pygobject/-/issues/603
        # So for now channel binding is deactivated
        # channel_binding_data = self._get_channel_binding_data(features)
        if channel_binding_data is None:
            self._enabled_mechs.discard("SCRAM-SHA-1-PLUS")
            self._enabled_mechs.discard("SCRAM-SHA-256-PLUS")
            self._enabled_mechs.discard("SCRAM-SHA-512-PLUS")

        if not GSSAPI_AVAILABLE:
            self._enabled_mechs.discard("GSSAPI")

        feature_mechs = features.get_mechs()

        self._log.info("Enabled mechanisms: %s", self._enabled_mechs)
        self._log.info("Server mechanisms: %s", feature_mechs)

        available_mechs = feature_mechs & self._enabled_mechs
        self._log.info("Available mechanisms: %s", available_mechs)

        domain_based_name = features.get_domain_based_name()
        if domain_based_name is not None:
            self._log.info("Found domain based name: %s", domain_based_name)

        if not available_mechs:
            self._log.error("No available auth mechanisms found")
            self._abort_auth("invalid-mechanism")
            return

        chosen_mechanism = None
        for mech in SASL_AUTH_MECHS:
            if mech in available_mechs:
                chosen_mechanism = mech
                break

        if chosen_mechanism is None:
            self._log.error("No available auth mechanisms found")
            self._abort_auth("invalid-mechanism")
            return

        self._log.info("Chosen auth mechanism: %s", chosen_mechanism)

        if chosen_mechanism.startswith(("SCRAM", "PLAIN")):
            if not self._password:
                self._on_sasl_finished(False, "no-password")
                return

        mech_class = self._mechanism_classes[chosen_mechanism]
        self._mechanism = mech_class(
            self._client.username,
            self._password,
            domain_based_name or self._client.domain,
        )

        if isinstance(self._mechanism, SCRAM) and channel_binding_data is not None:
            self._mechanism.set_channel_binding_data(channel_binding_data)

        try:
            self._send_initiate()
        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()
            return

    def _send_initiate(self) -> None:
        assert self._mechanism is not None
        data = self._mechanism.get_initiate_data()
        nonza = get_initiate_nonza(self._sasl_ns, self._mechanism.name, data)
        self._client.send_nonza(nonza)

    def _on_challenge(self, stanza: Protocol) -> None:
        assert self._mechanism is not None
        try:
            data = self._mechanism.get_response_data(stanza.getData())
        except AttributeError:
            self._log.info("Mechanism has no response method")
            self._abort_auth()
            return

        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()
            return

        nonza = get_response_nonza(self._sasl_ns, data)
        self._client.send_nonza(nonza)

    def _on_success(self, stanza: Protocol) -> None:
        self._log.info("Successfully authenticated with remote server")
        data = get_success_data(stanza, self._sasl_ns)
        try:
            self._mechanism.validate_success_data(data)
        except Exception as error:
            self._log.error("Unable to validate success data: %s", error)
            self._abort_auth()
            return

        self._log.info("Validated success data")

        self._on_sasl_finished(True, None, None)

    def _on_failure(self, stanza: Protocol) -> None:
        text = stanza.getTagData("text")
        reason = "not-authorized"
        childs = stanza.getChildren()
        for child in childs:
            name = child.getName()
            if name == "text":
                continue
            if name in SASL_ERROR_CONDITIONS:
                reason = name
                break

        self._log.info("Failed SASL authentification: %s %s", reason, text)
        self._abort_auth(reason, text)

    def _abort_auth(
        self, reason: str = "malformed-request", text: str | None = None
    ) -> None:
        node = Node("abort", attrs={"xmlns": self._sasl_ns})
        self._client.send_nonza(node)
        self._on_sasl_finished(False, reason, text)

    def _on_sasl_finished(
        self, successful: bool, reason: str | None, text: str | None = None
    ) -> None:
        if not successful:
            self._error = (reason, text)
            self._client.set_state(StreamState.AUTH_FAILED)
        else:
            self._client.set_state(StreamState.AUTH_SUCCESSFUL)


def get_initiate_nonza(ns: str, mechanism: str, data: str | None) -> Node:

    if ns == Namespace.SASL:
        node = Node("auth", attrs={"xmlns": ns, "mechanism": mechanism})
        if data is not None:
            node.setData(data)

    else:
        node = Node("authenticate", attrs={"xmlns": ns, "mechanism": mechanism})
        if data is not None:
            node.setTagData("initial-response", data)

    return node


def get_response_nonza(ns: str, data: str) -> Node:
    return Node("response", attrs={"xmlns": ns}, payload=[data])


def get_success_data(stanza: Protocol, ns: str) -> str | None:
    if ns == Namespace.SASL2:
        return stanza.getTagData("additional-data")
    return stanza.getData()


class BaseMechanism:

    name: str

    def __init__(self, username: str, password: str, domain: str) -> None:
        self._username = username
        self._password = password
        self._domain = domain

    def get_initiate_data(self) -> str | None:
        raise NotImplementedError

    def get_response_data(self, data: str) -> str:
        raise NotImplementedError

    def validate_success_data(self, _data: str) -> None:
        return None


class PLAIN(BaseMechanism):

    name = "PLAIN"

    def get_initiate_data(self) -> str:
        return b64encode("\x00%s\x00%s" % (self._username, self._password))


class EXTERNAL(BaseMechanism):

    name = "EXTERNAL"

    def get_initiate_data(self) -> str:
        return b64encode("%s@%s" % (self._username, self._domain))


class ANONYMOUS(BaseMechanism):

    name = "ANONYMOUS"

    def get_initiate_data(self) -> None:
        return None


class GSSAPI(BaseMechanism):

    # See https://tools.ietf.org/html/rfc4752#section-3.1

    name = "GSSAPI"

    def get_initiate_data(self) -> str:
        service = gssapi.Name(
            "xmpp@%s" % self._domain, name_type=gssapi.NameType.hostbased_service
        )
        try:
            self.ctx = gssapi.SecurityContext(
                name=service, usage="initiate", flags=gssapi.RequirementFlag.integrity
            )
            token = self.ctx.step()
        except (gssapi.exceptions.GeneralError, gssapi.raw.misc.GSSError) as e:
            raise AuthFail(e)

        return b64encode(token)

    def get_response_data(self, data: str | bytes) -> str:
        byte_data = b64decode(data)
        try:
            if not self.ctx.complete:
                output_token = self.ctx.step(byte_data)
            else:
                _result = self.ctx.unwrap(byte_data)
                # TODO(jelmer): Log result.message
                data = b"\x00\x00\x00\x00" + bytes(self.ctx.initiator_name)
                output_token = self.ctx.wrap(data, False).message
        except (gssapi.exceptions.GeneralError, gssapi.raw.misc.GSSError) as e:
            raise AuthFail(e)

        return b64encode(output_token)


class SCRAM(BaseMechanism):

    name = ""
    _hash_method = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        BaseMechanism.__init__(self, *args, **kwargs)
        self._channel_binding_data: ChannelBindingData | None = None
        self._gs2_header = "n,,"
        self._client_nonce = "%x" % int(binascii.hexlify(os.urandom(24)), 16)
        self._client_first_message_bare = None
        self._server_signature = None

    def set_channel_binding_data(self, data: ChannelBindingData) -> None:
        self._channel_binding_data = data
        self._gs2_header = f"p={data.type},,"

    @property
    def nonce_length(self) -> int:
        return len(self._client_nonce)

    @property
    def _b64_channel_binding_data(self) -> str:
        if self.name.endswith("PLUS"):
            assert self._channel_binding_data is not None
            return b64encode(
                b"%s%s" % (self._gs2_header.encode(), self._channel_binding_data.data)
            )
        return b64encode(self._gs2_header)

    @staticmethod
    def _scram_parse(scram_data: str) -> dict[str, str]:
        return dict(s.split("=", 1) for s in scram_data.split(","))

    def get_initiate_data(self) -> str:
        self._client_first_message_bare = "n=%s,r=%s" % (
            self._username,
            self._client_nonce,
        )

        client_first_message = "%s%s" % (
            self._gs2_header,
            self._client_first_message_bare,
        )

        return b64encode(client_first_message)

    def get_response_data(self, data: str | bytes) -> str:
        server_first_message = b64decode(data).decode()
        challenge = self._scram_parse(server_first_message)

        client_nonce = challenge["r"][: self.nonce_length]
        if client_nonce != self._client_nonce:
            raise AuthFail("Invalid client nonce received from server")

        salt = b64decode(challenge["s"])
        iteration_count = int(challenge["i"])

        if iteration_count < 4096:
            raise AuthFail("Salt iteration count to low: %s" % iteration_count)

        salted_password = pbkdf2_hmac(
            self._hash_method, self._password.encode("utf8"), salt, iteration_count
        )

        client_final_message_wo_proof = "c=%s,r=%s" % (
            self._b64_channel_binding_data,
            challenge["r"],
        )

        client_key = self._hmac(salted_password, "Client Key")
        stored_key = self._h(client_key)
        auth_message = "%s,%s,%s" % (
            self._client_first_message_bare,
            server_first_message,
            client_final_message_wo_proof,
        )
        client_signature = self._hmac(stored_key, auth_message)
        client_proof = self._xor(client_key, client_signature)

        client_finale_message = "c=%s,r=%s,p=%s" % (
            self._b64_channel_binding_data,
            challenge["r"],
            b64encode(client_proof),
        )

        server_key = self._hmac(salted_password, "Server Key")
        self._server_signature = self._hmac(server_key, auth_message)

        return b64encode(client_finale_message)

    def validate_success_data(self, data: str) -> None:
        server_last_message = b64decode(data).decode()
        success = self._scram_parse(server_last_message)
        server_signature = b64decode(success["v"])
        if server_signature != self._server_signature:
            raise AuthFail("Invalid server signature")

    def _hmac(self, key: bytes, message: str) -> bytes:
        return hmac.new(
            key=key, msg=message.encode(), digestmod=self._hash_method
        ).digest()

    @staticmethod
    def _xor(x: bytes, y: bytes) -> bytes:
        return bytes([px ^ py for px, py in zip(x, y, strict=False)])

    def _h(self, data: bytes) -> bytes:
        return hashlib.new(self._hash_method, data).digest()


class SCRAM_SHA_1(SCRAM):

    name = "SCRAM-SHA-1"
    _hash_method = "sha1"


class SCRAM_SHA_1_PLUS(SCRAM_SHA_1):

    name = "SCRAM-SHA-1-PLUS"


class SCRAM_SHA_256(SCRAM):

    name = "SCRAM-SHA-256"
    _hash_method = "sha256"


class SCRAM_SHA_256_PLUS(SCRAM_SHA_256):

    name = "SCRAM-SHA-256-PLUS"


class SCRAM_SHA_512(SCRAM):

    name = "SCRAM-SHA-512"
    _hash_method = "sha512"


class SCRAM_SHA_512_PLUS(SCRAM_SHA_512):

    name = "SCRAM-SHA-512-PLUS"


class AuthFail(Exception):
    pass
