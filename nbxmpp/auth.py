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

from __future__ import annotations

from typing import Optional

import os
import hmac
import binascii
import logging
import hashlib
from hashlib import pbkdf2_hmac
from nbxmpp import types
from nbxmpp.client import Client

from nbxmpp.elements import Nonza
from nbxmpp.elements import register_class_lookup
from nbxmpp.namespaces import Namespace
from nbxmpp.const import SASL_ERROR_CONDITIONS
from nbxmpp.const import SASL_AUTH_MECHS
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.util import LogAdapter
from nbxmpp.const import StreamState
from nbxmpp.builder import E


log = logging.getLogger('nbxmpp.auth')

try:
    gssapi = __import__('gssapi')
    GSSAPI_AVAILABLE = True
except (ImportError, OSError) as error:
    log.warning('GSSAPI not available: %s', error)
    GSSAPI_AVAILABLE = False


def make_sasl_element(name: str,
                      mechanism: Optional[str] = None,
                      payload: Optional[str] = None):

    if mechanism is None:
        element = E(name, namespace=Namespace.XMPP_SASL)
    else:
        element = E(name, namespace=Namespace.XMPP_SASL, mechanism=mechanism)

    element.text = payload
    return element


class SASL:
    """
    Implements SASL authentication.
    """
    def __init__(self, client: Client):
        self._client = client

        self._allowed_mechs = None
        self._enabled_mechs = None
        self._method = None
        self._error = None

        self._log = LogAdapter(log, {'context': client.log_context})

    @property
    def error(self):
        return self._error

    def delegate(self, stanza):
        if stanza.namespace != Namespace.XMPP_SASL:
            return
        if stanza.localname == 'challenge':
            self._on_challenge(stanza)
        elif stanza.localname == 'failure':
            self._on_failure(stanza)
        elif stanza.localname == 'success':
            self._on_success(stanza)

    def start_auth(self, features):
        self._allowed_mechs = self._client.mechs
        self._enabled_mechs = self._allowed_mechs
        self._method = None
        self._error = None

        # -PLUS variants need TLS channel binding data
        # This is currently not supported via GLib
        self._enabled_mechs.discard('SCRAM-SHA-1-PLUS')
        self._enabled_mechs.discard('SCRAM-SHA-256-PLUS')
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

        if chosen_mechanism in ('SCRAM-SHA-256', 'SCRAM-SHA-1', 'PLAIN'):
            if not self._client.password:
                self._on_sasl_finished(False, 'no-password')
                return

        # if chosen_mechanism == 'SCRAM-SHA-256-PLUS':
        #     self._method = SCRAM_SHA_256_PLUS(self._client,
        #                                       channel_binding_data)
        #     self._method.initiate()

        # elif chosen_mechanism == 'SCRAM-SHA-1-PLUS':
        #     self._method = SCRAM_SHA_1_PLUS(self._client,
        #                                     channel_binding_data)
        #     self._method.initiate()

        if chosen_mechanism == 'SCRAM-SHA-256':
            self._method = SCRAM_SHA_256(self._client, None)
            self._method.initiate()

        elif chosen_mechanism == 'SCRAM-SHA-1':
            self._method = SCRAM_SHA_1(self._client, None)
            self._method.initiate()

        elif chosen_mechanism == 'PLAIN':
            self._method = PLAIN(self._client)
            self._method.initiate()

        elif chosen_mechanism == 'ANONYMOUS':
            self._method = ANONYMOUS(self._client)
            self._method.initiate()

        elif chosen_mechanism == 'EXTERNAL':
            self._method = EXTERNAL(self._client)
            self._method.initiate()

        elif chosen_mechanism == 'GSSAPI':
            self._method = GSSAPI(self._client)
            if domain_based_name:
                hostname = domain_based_name
            else:
                hostname = self._client.domain
            try:
                self._method.initiate(hostname)
            except AuthFail as error:
                self._log.error(error)
                self._abort_auth()
                return
        else:
            self._log.error('Unknown auth mech')

    def _on_challenge(self, stanza: types.Nonza):
        try:
            self._method.response(stanza.text or '')
        except AttributeError:
            self._log.info('Mechanism has no response method')
            self._abort_auth()
        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()

    def _on_success(self, stanza: types.Nonza):
        self._log.info('Successfully authenticated with remote server')
        try:
            self._method.success(stanza.text or '')
        except AttributeError:
            pass
        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()
            return

        self._on_sasl_finished(True, None, None)

    def _on_failure(self, stanza: types.Nonza):
        text = stanza.find_tag_text('text')
        reason = 'not-authorized'
        childs = stanza.get_children()
        for child in childs:
            name = child.localname
            if name == 'text':
                continue
            if name in SASL_ERROR_CONDITIONS:
                reason = name
                break

        self._log.info('Failed SASL authentification: %s %s', reason, text)
        self._abort_auth(reason, text)

    def _abort_auth(self,
                    reason: str = 'malformed-request',
                    text: Optional[str] = None):

        element = make_sasl_element('abort')
        self._client.send_nonza(element)
        self._on_sasl_finished(False, reason, text)

    def _on_sasl_finished(self,
                          successful: bool,
                          reason: str,
                          text: Optional[str] = None):

        if not successful:
            self._error = (reason, text)
            self._client.set_state(StreamState.AUTH_FAILED)
        else:
            self._client.set_state(StreamState.AUTH_SUCCESSFUL)


class PLAIN:

    _mechanism = 'PLAIN'

    def __init__(self, client: Client):
        self._client = client

    def initiate(self):
        payload = b64encode('\x00%s\x00%s' % (self._client.username,
                                              self._client.password))
        element = make_sasl_element('auth', mechanism='PLAIN', payload=payload)
        self._client.send_nonza(element)


class EXTERNAL:

    _mechanism = 'EXTERNAL'

    def __init__(self, client: Client):
        self._client = client

    def initiate(self):
        payload = b64encode('%s@%s' % (self._client.username,
                                       self._client.domain))
        element = make_sasl_element('auth',
                                    mechanism='EXTERNAL',
                                    payload=payload)
        self._client.send_nonza(element)


class ANONYMOUS:

    _mechanism = 'ANONYMOUS'

    def __init__(self, client: Client):
        self._client = client

    def initiate(self):
        element = make_sasl_element('auth', mechanism='ANONYMOUS')
        self._client.send_nonza(element)


class GSSAPI:

    # See https://tools.ietf.org/html/rfc4752#section-3.1

    _mechanism = 'GSSAPI'

    def __init__(self, client: Client):
        self._client = client

    def initiate(self, hostname):
        service = gssapi.Name(
            'xmpp@%s' % hostname, name_type=gssapi.NameType.hostbased_service)
        try:
            self.ctx = gssapi.SecurityContext(
                name=service, usage="initiate",
                flags=gssapi.RequirementFlag.integrity)
            token = self.ctx.step()
        except (gssapi.exceptions.GeneralError, gssapi.raw.misc.GSSError) as e:
            raise AuthFail(e)

        element = make_sasl_element('auth',
                                    mechanism='GSSAPI',
                                    payload=b64encode(token))
        self._client.send_nonza(element)

    def response(self, server_message, *args, **kwargs):
        server_message = b64decode(server_message)
        try:
            if not self.ctx.complete:
                output_token = self.ctx.step(server_message)
            else:
                result = self.ctx.unwrap(server_message)
                # TODO(jelmer): Log result.message
                data = b'\x00\x00\x00\x00' + bytes(self.ctx.initiator_name)
                output_token = self.ctx.wrap(data, False).message
        except (gssapi.exceptions.GeneralError, gssapi.raw.misc.GSSError) as e:
            raise AuthFail(e)
        payload = b64encode(output_token)

        element = make_sasl_element('response', payload=payload)
        self._client.send_nonza(element)


class SCRAM:

    _mechanism = ''
    _channel_binding = ''
    _hash_method = ''

    def __init__(self, client: Client, channel_binding: Optional[bytes]):
        self._client = client
        self._channel_binding_data = channel_binding
        self._client_nonce = '%x' % int(binascii.hexlify(os.urandom(24)), 16)
        self._client_first_message_bare = None
        self._server_signature = None

    @property
    def nonce_length(self) -> int:
        return len(self._client_nonce)

    @property
    def _b64_channel_binding_data(self) -> str:
        if self._mechanism.endswith('PLUS'):
            return b64encode(b'%s%s' % (self._channel_binding.encode(),
                                        self._channel_binding_data))
        return b64encode(self._channel_binding)

    @staticmethod
    def _scram_parse(scram_data: str) -> dict[str, str]:
        return dict(s.split('=', 1) for s in scram_data.split(','))

    def initiate(self):
        self._client_first_message_bare = 'n=%s,r=%s' % (self._client.username,
                                                         self._client_nonce)
        client_first_message = '%s%s' % (self._channel_binding,
                                         self._client_first_message_bare)

        element = make_sasl_element('auth',
                                    mechanism=self._mechanism,
                                    payload=b64encode(client_first_message))

        self._client.send_nonza(element)

    def response(self, server_first_message: str):
        server_first_message = b64decode(server_first_message).decode()
        challenge = self._scram_parse(server_first_message)

        client_nonce = challenge['r'][:self.nonce_length]
        if client_nonce != self._client_nonce:
            raise AuthFail('Invalid client nonce received from server')

        salt = b64decode(challenge['s'])
        iteration_count = int(challenge['i'])

        if iteration_count < 4096:
            raise AuthFail('Salt iteration count to low: %s' % iteration_count)

        salted_password = pbkdf2_hmac(self._hash_method,
                                      self._client.password.encode('utf8'),
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

        element = make_sasl_element('response',
                                    payload=b64encode(client_finale_message))

        self._client.send_nonza(element)

    def success(self, server_last_message: str):
        server_last_message = b64decode(server_last_message).decode()
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

    _mechanism = 'SCRAM-SHA-1'
    _channel_binding = 'n,,'
    _hash_method = 'sha1'


class SCRAM_SHA_1_PLUS(SCRAM_SHA_1):

    _mechanism = 'SCRAM-SHA-1-PLUS'
    _channel_binding = 'p=tls-unique,,'


class SCRAM_SHA_256(SCRAM):

    _mechanism = 'SCRAM-SHA-256'
    _channel_binding = 'n,,'
    _hash_method = 'sha256'


class SCRAM_SHA_256_PLUS(SCRAM_SHA_256):

    _mechanism = 'SCRAM-SHA-256-PLUS'
    _channel_binding = 'p=tls-unique,,'


class AuthFail(Exception):
    pass


register_class_lookup('challenge', Namespace.XMPP_SASL, Nonza)
register_class_lookup('failure', Namespace.XMPP_SASL, Nonza)
register_class_lookup('success', Namespace.XMPP_SASL, Nonza)
