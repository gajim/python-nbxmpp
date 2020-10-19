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


log = logging.getLogger('nbxmpp.auth')

try:
    gssapi = __import__('gssapi')
    GSSAPI_AVAILABLE = True
except ImportError:
    GSSAPI_AVAILABLE = False


class SASL:
    """
    Implements SASL authentication.
    """
    def __init__(self, client):
        self._client = client

        self._password = None

        self._allowed_mechs = None
        self._enabled_mechs = None
        self._method = None
        self._error = None

        self._log = LogAdapter(log, {'context': client.log_context})

    @property
    def error(self):
        return self._error

    def set_password(self, password):
        self._password = password

    @property
    def password(self):
        return self._password

    def delegate(self, stanza):
        if stanza.getNamespace() != Namespace.SASL:
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
            if not self._password:
                self._on_sasl_finished(False, 'no-password')
                return

        # if chosen_mechanism == 'SCRAM-SHA-256-PLUS':
        #     self._method = SCRAM_SHA_256_PLUS(self._client,
        #                                       channel_binding_data)
        #     self._method.initiate(self._client.username, self._password)

        # elif chosen_mechanism == 'SCRAM-SHA-1-PLUS':
        #     self._method = SCRAM_SHA_1_PLUS(self._client,
        #                                     channel_binding_data)
        #     self._method.initiate(self._client.username, self._password)

        if chosen_mechanism == 'SCRAM-SHA-256':
            self._method = SCRAM_SHA_256(self._client, None)
            self._method.initiate(self._client.username, self._password)

        elif chosen_mechanism == 'SCRAM-SHA-1':
            self._method = SCRAM_SHA_1(self._client, None)
            self._method.initiate(self._client.username, self._password)

        elif chosen_mechanism == 'PLAIN':
            self._method = PLAIN(self._client)
            self._method.initiate(self._client.username, self._password)

        elif chosen_mechanism == 'ANONYMOUS':
            self._method = ANONYMOUS(self._client)
            self._method.initiate()

        elif chosen_mechanism == 'EXTERNAL':
            self._method = EXTERNAL(self._client)
            self._method.initiate(self._client.username, self._client.Server)

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

    def _on_challenge(self, stanza):
        try:
            self._method.response(stanza.getData())
        except AttributeError:
            self._log.info('Mechanism has no response method')
            self._abort_auth()
        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()

    def _on_success(self, stanza):
        self._log.info('Successfully authenticated with remote server')
        try:
            self._method.success(stanza.getData())
        except AttributeError:
            pass
        except AuthFail as error:
            self._log.error(error)
            self._abort_auth()
            return

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
        node = Node('abort', attrs={'xmlns': Namespace.SASL})
        self._client.send_nonza(node)
        self._on_sasl_finished(False, reason, text)

    def _on_sasl_finished(self, successful, reason, text=None):
        if not successful:
            self._error = (reason, text)
            self._client.set_state(StreamState.AUTH_FAILED)
        else:
            self._client.set_state(StreamState.AUTH_SUCCESSFUL)


class PLAIN:

    _mechanism = 'PLAIN'

    def __init__(self, client):
        self._client = client

    def initiate(self, username, password):
        payload = b64encode('\x00%s\x00%s' % (username, password))
        node = Node('auth',
                    attrs={'xmlns': Namespace.SASL, 'mechanism': 'PLAIN'},
                    payload=[payload])
        self._client.send_nonza(node)


class EXTERNAL:

    _mechanism = 'EXTERNAL'

    def __init__(self, client):
        self._client = client

    def initiate(self, username, server):
        payload = b64encode('%s@%s' % (username, server))
        node = Node('auth',
                    attrs={'xmlns': Namespace.SASL, 'mechanism': 'EXTERNAL'},
                    payload=[payload])
        self._client.send_nonza(node)


class ANONYMOUS:

    _mechanism = 'ANONYMOUS'

    def __init__(self, client):
        self._client = client

    def initiate(self):
        node = Node('auth', attrs={'xmlns': Namespace.SASL,
                                   'mechanism': 'ANONYMOUS'})
        self._client.send_nonza(node)


class GSSAPI:

    # See https://tools.ietf.org/html/rfc4752#section-3.1

    _mechanism = 'GSSAPI'

    def __init__(self, client):
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
        node = Node('auth',
                    attrs={'xmlns': Namespace.SASL, 'mechanism': 'GSSAPI'},
                    payload=b64encode(token))
        self._client.send_nonza(node)

    def response(self, server_message, *args, **kwargs):
        server_message = b64decode(server_message, bytes)
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
        response = b64encode(output_token)
        node = Node('response',
                    attrs={'xmlns': Namespace.SASL},
                    payload=response)
        self._client.send_nonza(node)


class SCRAM:

    _mechanism = ''
    _channel_binding = ''
    _hash_method = ''

    def __init__(self, client, channel_binding):
        self._client = client
        self._channel_binding_data = channel_binding
        self._client_nonce = '%x' % int(binascii.hexlify(os.urandom(24)), 16)
        self._client_first_message_bare = None
        self._server_signature = None
        self._password = None

    @property
    def nonce_length(self):
        return len(self._client_nonce)

    @property
    def _b64_channel_binding_data(self):
        if self._mechanism.endswith('PLUS'):
            return b64encode(b'%s%s' % (self._channel_binding.encode(),
                                        self._channel_binding_data))
        return b64encode(self._channel_binding)

    @staticmethod
    def _scram_parse(scram_data):
        return dict(s.split('=', 1) for s in scram_data.split(','))

    def initiate(self, username, password):
        self._password = password
        self._client_first_message_bare = 'n=%s,r=%s' % (username,
                                                         self._client_nonce)
        client_first_message = '%s%s' % (self._channel_binding,
                                         self._client_first_message_bare)

        payload = b64encode(client_first_message)
        node = Node('auth',
                    attrs={'xmlns': Namespace.SASL,
                           'mechanism': self._mechanism},
                    payload=[payload])
        self._client.send_nonza(node)

    def response(self, server_first_message):
        server_first_message = b64decode(server_first_message)
        challenge = self._scram_parse(server_first_message)

        client_nonce = challenge['r'][:self.nonce_length]
        if client_nonce != self._client_nonce:
            raise AuthFail('Invalid client nonce received from server')

        salt = b64decode(challenge['s'], bytes)
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

        payload = b64encode(client_finale_message)
        node = Node('response',
                    attrs={'xmlns': Namespace.SASL},
                    payload=[payload])
        self._client.send_nonza(node)

    def success(self, server_last_message):
        server_last_message = b64decode(server_last_message)
        success = self._scram_parse(server_last_message)
        server_signature = b64decode(success['v'], bytes)
        if server_signature != self._server_signature:
            raise AuthFail('Invalid server signature')

    def _hmac(self, key, message):
        return hmac.new(key=key,
                        msg=message.encode(),
                        digestmod=self._hash_method).digest()

    @staticmethod
    def _xor(x, y):
        return bytes([px ^ py for px, py in zip(x, y)])

    def _h(self, data):
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
