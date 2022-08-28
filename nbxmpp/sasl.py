# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
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

from typing import Any
from typing import Optional

import os
import hmac
import binascii
import logging
import hashlib
from hashlib import pbkdf2_hmac

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Node
from nbxmpp.protocol import SASL_ERROR_CONDITIONS
from nbxmpp.protocol import SASL_AUTH_MECHS
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.util import LogAdapter
from nbxmpp.const import StreamState


log = logging.getLogger('nbxmpp.sasl')

try:
    gssapi = __import__('gssapi')
    GSSAPI_AVAILABLE = True
except (ImportError, OSError) as error:
    log.warning('GSSAPI not available: %s', error)
    GSSAPI_AVAILABLE = False


class SASL:
    """
    Implements SASL authentication.
    """
    def __init__(self, client):
        self._client = client

        self._password = None

        self._mechanism_classes = {
            'PLAIN': PLAIN,
            'EXTERNAL': EXTERNAL,
            'GSSAPI': GSSAPI,
            'SCRAM-SHA-1': SCRAM_SHA_1,
            'SCRAM-SHA-1-PLUS': SCRAM_SHA_1_PLUS,
            'SCRAM-SHA-256': SCRAM_SHA_256,
            'SCRAM-SHA-256-PLUS': SCRAM_SHA_256_PLUS,
            'SCRAM-SHA-512': SCRAM_SHA_512,
            'SCRAM-SHA-512-PLUS': SCRAM_SHA_512_PLUS
        }

        self._allowed_mechs = None
        self._enabled_mechs = None
        self._sasl_ns = None
        self._mechanism = None
        self._error = None

        self._log = LogAdapter(log, {'context': client.log_context})

    @property
    def error(self):
        return self._error

    def is_sasl2(self) -> bool:
        assert self._sasl_ns is not None
        return self._sasl_ns == Namespace.SASL2

    def set_password(self, password):
        self._password = password

    @property
    def password(self):
        return self._password

    def delegate(self, stanza):
        if stanza.getNamespace() != self._sasl_ns:
            return

        if stanza.getName() == 'challenge':
            self._on_challenge(stanza)
        elif stanza.getName() == 'failure':
            self._on_failure(stanza)
        elif stanza.getName() == 'success':
            self._on_success(stanza)

    def start_auth(self, features):
        self._allowed_mechs = self._client.mechs
        self._enabled_mechs = self._allowed_mechs
        self._mechanism = None

        self._sasl_ns = Namespace.SASL
        if features.has_sasl_2():
            self._sasl_ns = Namespace.SASL2

        self._error = None

        # -PLUS variants need TLS channel binding data
        # This is currently not supported via GLib
        self._enabled_mechs.discard('SCRAM-SHA-1-PLUS')
        self._enabled_mechs.discard('SCRAM-SHA-256-PLUS')
        self._enabled_mechs.discard('SCRAM-SHA-512-PLUS')
        # channel_binding_data = None

        if not GSSAPI_AVAILABLE:
            self._enabled_mechs.discard('GSSAPI')

        available_mechs = features.get_mechs() & self._enabled_mechs
        self._log.info('Available mechanisms: %s', available_mechs)

        domain_based_name = features.get_domain_based_name()
        if domain_based_name is not None:
            self._log.info('Found domain based name: %s', domain_based_name)

        if not available_mechs:
            self._log.error('No available auth mechanisms found')
            self._abort_auth('invalid-mechanism')
            return

        chosen_mechanism = None
        for mech in SASL_AUTH_MECHS:
            if mech in available_mechs:
                chosen_mechanism = mech
                break

        if chosen_mechanism is None:
            self._log.error('No available auth mechanisms found')
            self._abort_auth('invalid-mechanism')
            return

        self._log.info('Chosen auth mechanism: %s', chosen_mechanism)

        if chosen_mechanism in ('SCRAM-SHA-512',
                                'SCRAM-SHA-256',
                                'SCRAM-SHA-1',
                                'PLAIN'):
            if not self._password:
                self._on_sasl_finished(False, 'no-password')
                return

        mech_class = self._mechanism_classes[chosen_mechanism]
        self._mechanism = mech_class(self._client.username,
                                     self._password,
                                     domain_based_name or self._client.domain)

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

    def _on_challenge(self, stanza) -> None:
        assert self._mechanism is not None
        try:
            data = self._mechanism.get_response_data(stanza.getData())
        except AttributeError:
            self._log.info('Mechanism has no response method')
            self._abort_auth()
            return

        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()
            return

        nonza = get_response_nonza(self._sasl_ns, data)
        self._client.send_nonza(nonza)

    def _on_success(self, stanza):
        self._log.info('Successfully authenticated with remote server')
        data = get_success_data(stanza, self._sasl_ns)
        try:
            self._mechanism.validate_success_data(data)
        except Exception as error:
            self._log.error('Unable to validate success data: %s', error)
            self._abort_auth()
            return

        self._log.info('Validated success data')

        self._on_sasl_finished(True, None, None)

    def _on_failure(self, stanza):
        text = stanza.getTagData('text')
        reason = 'not-authorized'
        childs = stanza.getChildren()
        for child in childs:
            name = child.getName()
            if name == 'text':
                continue
            if name in SASL_ERROR_CONDITIONS:
                reason = name
                break

        self._log.info('Failed SASL authentification: %s %s', reason, text)
        self._abort_auth(reason, text)

    def _abort_auth(self, reason='malformed-request', text=None):
        node = Node('abort', attrs={'xmlns': self._sasl_ns})
        self._client.send_nonza(node)
        self._on_sasl_finished(False, reason, text)

    def _on_sasl_finished(self, successful, reason, text=None):
        if not successful:
            self._error = (reason, text)
            self._client.set_state(StreamState.AUTH_FAILED)
        else:
            self._client.set_state(StreamState.AUTH_SUCCESSFUL)


def get_initiate_nonza(ns: str,
                       mechanism: str,
                       data: Optional[str]) -> Any:

    if ns == Namespace.SASL:
        node = Node('auth', attrs={'xmlns': ns, 'mechanism': mechanism})
        if data is not None:
            node.setData(data)

    else:
        node = Node('authenticate', attrs={'xmlns': ns, 'mechanism': mechanism})
        if data is not None:
            node.setTagData('initial-response', data)

    return node


def get_response_nonza(ns: str, data: str) -> Any:
    return Node('response', attrs={'xmlns': ns}, payload=[data])


def get_success_data(stanza: Any, ns: str) -> Optional[str]:
    if ns == Namespace.SASL2:
        return stanza.getTagData('additional-data')
    return stanza.getData()


class BaseMechanism:

    name: str

    def __init__(self, username: str, password: str, domain: str):
        self._username = username
        self._password = password
        self._domain = domain

    def get_initiate_data(self) -> Optional[str]:
        raise NotImplementedError

    def get_response_data(self, data: str) -> str:
        raise NotImplementedError

    def validate_success_data(self, _data: str) -> None:
        return None


class PLAIN(BaseMechanism):

    name = 'PLAIN'

    def get_initiate_data(self) -> str:
        return b64encode('\x00%s\x00%s' % (self._username, self._password))


class EXTERNAL(BaseMechanism):

    name = 'EXTERNAL'

    def get_initiate_data(self) -> str:
        return b64encode('%s@%s' % (self._username, self._domain))


class ANONYMOUS(BaseMechanism):

    name = 'ANONYMOUS'

    def get_initiate_data(self) -> None:
        return None


class GSSAPI(BaseMechanism):

    # See https://tools.ietf.org/html/rfc4752#section-3.1

    name = 'GSSAPI'

    def get_initiate_data(self) -> str:
        service = gssapi.Name(
            'xmpp@%s' % self._domain,
            name_type=gssapi.NameType.hostbased_service)
        try:
            self.ctx = gssapi.SecurityContext(
                name=service, usage="initiate",
                flags=gssapi.RequirementFlag.integrity)
            token = self.ctx.step()
        except (gssapi.exceptions.GeneralError, gssapi.raw.misc.GSSError) as e:
            raise AuthFail(e)

        return b64encode(token)

    def get_response_data(self, data: str) -> str:
        byte_data = b64decode(data)
        try:
            if not self.ctx.complete:
                output_token = self.ctx.step(byte_data)
            else:
                _result = self.ctx.unwrap(byte_data)
                # TODO(jelmer): Log result.message
                data = b'\x00\x00\x00\x00' + bytes(self.ctx.initiator_name)
                output_token = self.ctx.wrap(data, False).message
        except (gssapi.exceptions.GeneralError, gssapi.raw.misc.GSSError) as e:
            raise AuthFail(e)

        return b64encode(output_token)


class SCRAM(BaseMechanism):

    name = ''
    _channel_binding = ''
    _hash_method = ''

    def __init__(self, *args, **kwargs) -> None:
        BaseMechanism.__init__(self, *args, **kwargs)
        self._channel_binding_data = None
        self._client_nonce = '%x' % int(binascii.hexlify(os.urandom(24)), 16)
        self._client_first_message_bare = None
        self._server_signature = None

    def set_channel_binding_data(self, data: bytes) -> None:
        self._channel_binding_data = data

    @property
    def nonce_length(self) -> int:
        return len(self._client_nonce)

    @property
    def _b64_channel_binding_data(self) -> str:
        if self.name.endswith('PLUS'):
            return b64encode(b'%s%s' % (self._channel_binding.encode(),
                                        self._channel_binding_data))
        return b64encode(self._channel_binding)

    @staticmethod
    def _scram_parse(scram_data: str) -> dict[str, str]:
        return dict(s.split('=', 1) for s in scram_data.split(','))

    def get_initiate_data(self) -> str:
        self._client_first_message_bare = 'n=%s,r=%s' % (self._username,
                                                         self._client_nonce)
        client_first_message = '%s%s' % (self._channel_binding,
                                         self._client_first_message_bare)

        return b64encode(client_first_message)

    def get_response_data(self, data) -> str:
        server_first_message = b64decode(data).decode()
        challenge = self._scram_parse(server_first_message)

        client_nonce = challenge['r'][:self.nonce_length]
        if client_nonce != self._client_nonce:
            raise AuthFail('Invalid client nonce received from server')

        salt = b64decode(challenge['s'])
        iteration_count = int(challenge['i'])

        if iteration_count < 4096:
            raise AuthFail('Salt iteration count to low: %s' % iteration_count)

        salted_password = pbkdf2_hmac(self._hash_method,
                                      self._password.encode('utf8'),
                                      salt,
                                      iteration_count)

        client_final_message_wo_proof = 'c=%s,r=%s' % (
            self._b64_channel_binding_data,
            challenge['r']
        )

        client_key = self._hmac(salted_password, 'Client Key')
        stored_key = self._h(client_key)
        auth_message = '%s,%s,%s' % (self._client_first_message_bare,
                                     server_first_message,
                                     client_final_message_wo_proof)
        client_signature = self._hmac(stored_key, auth_message)
        client_proof = self._xor(client_key, client_signature)

        client_finale_message = 'c=%s,r=%s,p=%s' % (
            self._b64_channel_binding_data,
            challenge['r'],
            b64encode(client_proof)
        )

        server_key = self._hmac(salted_password, 'Server Key')
        self._server_signature = self._hmac(server_key, auth_message)

        return b64encode(client_finale_message)

    def validate_success_data(self, data: str) -> None:
        server_last_message = b64decode(data).decode()
        success = self._scram_parse(server_last_message)
        server_signature = b64decode(success['v'])
        if server_signature != self._server_signature:
            raise AuthFail('Invalid server signature')

    def _hmac(self, key: bytes, message: str) -> bytes:
        return hmac.new(key=key,
                        msg=message.encode(),
                        digestmod=self._hash_method).digest()

    @staticmethod
    def _xor(x: bytes, y: bytes) -> bytes:
        return bytes([px ^ py for px, py in zip(x, y)])

    def _h(self, data: bytes) -> bytes:
        return hashlib.new(self._hash_method, data).digest()


class SCRAM_SHA_1(SCRAM):

    name = 'SCRAM-SHA-1'
    _channel_binding = 'n,,'
    _hash_method = 'sha1'


class SCRAM_SHA_1_PLUS(SCRAM_SHA_1):

    name = 'SCRAM-SHA-1-PLUS'
    _channel_binding = 'p=tls-unique,,'


class SCRAM_SHA_256(SCRAM):

    name = 'SCRAM-SHA-256'
    _channel_binding = 'n,,'
    _hash_method = 'sha256'


class SCRAM_SHA_256_PLUS(SCRAM_SHA_256):

    name = 'SCRAM-SHA-256-PLUS'
    _channel_binding = 'p=tls-unique,,'


class SCRAM_SHA_512(SCRAM):

    name = 'SCRAM-SHA-512'
    _channel_binding = 'n,,'
    _hash_method = 'sha512'


class SCRAM_SHA_512_PLUS(SCRAM_SHA_512):

    name = 'SCRAM-SHA-512-PLUS'
    _channel_binding = 'p=tls-unique,,'


class AuthFail(Exception):
    pass
