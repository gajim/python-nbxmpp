# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
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
from functools import partial

from nbxmpp.plugin import PlugIn
from nbxmpp.protocol import NS_SASL
from nbxmpp.protocol import Node
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import SASL_ERROR_CONDITIONS
from nbxmpp.protocol import SASL_AUTH_MECHS
from nbxmpp.protocol import NS_DOMAIN_BASED_NAME
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.const import GSSAPIState


log = logging.getLogger('nbxmpp.auth')

try:
    kerberos = __import__('kerberos')
    KERBEROS_AVAILABLE = True
except ImportError:
    KERBEROS_AVAILABLE = False


class SASL(PlugIn):
    """
    Implements SASL authentication. Can be plugged into NonBlockingClient
    to start authentication
    """

    _default_mechs = set(['SCRAM-SHA-256-PLUS',
                          'SCRAM-SHA-256',
                          'SCRAM-SHA-1-PLUS',
                          'SCRAM-SHA-1',
                          'PLAIN'])

    def __init__(self, username, auth_mechs, get_password, on_finished):
        """
        :param username: XMPP username
        :param auth_mechs: Set of valid authentication mechanisms.
               Possible entries are:
               'ANONYMOUS', 'EXTERNAL', 'GSSAPI', 'SCRAM-SHA-1-PLUS',
               'SCRAM-SHA-1', 'SCRAM-SHA-256', 'SCRAM-SHA-256-PLUS', 'PLAIN'
        :param on_finished: Callback after SASL is finished
        :param get_password: Callback that must return the password for the
                             chosen mechanism
        """
        PlugIn.__init__(self)
        self.username = username
        self._on_finished = on_finished
        self._get_password = get_password

        self._prefered_mechs = auth_mechs
        self._enabled_mechs = self._prefered_mechs or self._default_mechs
        self._chosen_mechanism = None
        self._method = None

        self._channel_binding = None
        self._domain_based_name = None

    def _setup_mechs(self):
        if self._owner.connected in ('ssl', 'tls'):
            if self._owner.protocol_type == 'BOSH':
                # PLUS would break if the server uses any kind of reverse proxy
                self._enabled_mechs.discard('SCRAM-SHA-1-PLUS')
                self._enabled_mechs.discard('SCRAM-SHA-256-PLUS')
            else:
                self._channel_binding = self._owner.Connection.NonBlockingTLS.get_channel_binding()
                # TLS handshake is finished so channel binding data muss exist
                if self._channel_binding is None:
                    raise ValueError('No channel binding data found')

        else:
            self._enabled_mechs.discard('SCRAM-SHA-1-PLUS')
            self._enabled_mechs.discard('SCRAM-SHA-256-PLUS')
            if self._prefered_mechs is None:
                # if the client didnt specify any auth mechs avoid
                # sending the password over a plain connection
                self._enabled_mechs.discard('PLAIN')

        if not KERBEROS_AVAILABLE:
            self._enabled_mechs.discard('GSSAPI')

    def plugin(self, _owner):
        self._setup_mechs()
        self._owner.RegisterHandler(
            'challenge', self._on_challenge, xmlns=NS_SASL)
        self._owner.RegisterHandler(
            'failure', self._on_failure, xmlns=NS_SASL)
        self._owner.RegisterHandler(
            'success', self._on_success, xmlns=NS_SASL)

        # Execute the Handler manually, we already received the features
        self._on_features(None, self._owner.Dispatcher.Stream.features)

    def plugout(self):
        """
        Remove SASL handlers from owner's dispatcher. Used internally
        """
        self._owner.UnregisterHandler(
            'challenge', self._on_challenge, xmlns=NS_SASL)
        self._owner.UnregisterHandler(
            'failure', self._on_failure, xmlns=NS_SASL)
        self._owner.UnregisterHandler(
            'success', self._on_success, xmlns=NS_SASL)

    def _on_features(self, _con, stanza):
        """
        Used to determine if server supports SASL auth. Used internally
        """
        if not stanza.getTag('mechanisms', namespace=NS_SASL):
            return

        mechanisms = stanza.getTag('mechanisms', namespace=NS_SASL)
        mechanisms = mechanisms.getTags('mechanism')

        mechs = set(mech.getData() for mech in mechanisms)
        available_mechs = mechs & self._enabled_mechs

        log.info('Available mechanisms: %s', available_mechs)

        hostname = stanza.getTag('hostname', namespace=NS_DOMAIN_BASED_NAME)
        if hostname is not None:
            self._domain_based_name = hostname.getData()
            log.info('Found domain based name: %s', self._domain_based_name)

        if not available_mechs:
            log.error('No available auth mechanisms found')
            self._abort_auth('invalid-mechanism')
            return

        for mech in SASL_AUTH_MECHS:
            if mech in available_mechs:
                self._chosen_mechanism = mech
                break

        if self._chosen_mechanism is None:
            log.error('No available auth mechanisms found')
            self._abort_auth('invalid-mechanism')
            return

        log.info('Chosen auth mechanism: %s', self._chosen_mechanism)
        self._auth()

    def _auth(self):
        password_cb = partial(self._on_password, self.username)

        if self._chosen_mechanism == 'SCRAM-SHA-256-PLUS':
            self._method = SCRAM_SHA_256_PLUS(self._owner.Connection,
                                              self._channel_binding)
            self._get_password(self._chosen_mechanism, password_cb)

        elif self._chosen_mechanism == 'SCRAM-SHA-256':
            self._method = SCRAM_SHA_256(self._owner.Connection, None)
            self._get_password(self._chosen_mechanism, password_cb)

        elif self._chosen_mechanism == 'SCRAM-SHA-1-PLUS':
            self._method = SCRAM_SHA_1_PLUS(self._owner.Connection,
                                            self._channel_binding)
            self._get_password(self._chosen_mechanism, password_cb)

        elif self._chosen_mechanism == 'SCRAM-SHA-1':
            self._method = SCRAM_SHA_1(self._owner.Connection, None)
            self._get_password(self._chosen_mechanism, password_cb)

        elif self._chosen_mechanism == 'PLAIN':
            self._method = PLAIN(self._owner.Connection)
            self._get_password(self._chosen_mechanism, password_cb)

        elif self._chosen_mechanism == 'ANONYMOUS':
            self._method = ANONYMOUS(self._owner.Connection)
            self._method.initiate()

        elif self._chosen_mechanism == 'EXTERNAL':
            self._method = EXTERNAL(self._owner.Connection)
            self._method.initiate(self.username, self._owner.Server)

        elif self._chosen_mechanism == 'GSSAPI':
            self._method = GSSAPI(self._owner.Connection)
            self._method.initiate(self._domain_based_name or
                                  self._owner.xmpp_hostname)

        else:
            log.error('Unknown auth mech')

    def _on_password(self, username, password):
        if password is None:
            log.warning('No password supplied')
            return
        self._method.initiate(username, password)

    def _on_challenge(self, _con, stanza):
        try:
            self._method.response(stanza.getData())
        except AttributeError:
            log.info('Mechanism has no response method')
            self._abort_auth()
        except AuthFail as error:
            log.error(error)
            self._abort_auth()
        raise NodeProcessed

    def _on_success(self, _con, stanza):
        log.info('Successfully authenticated with remote server')
        try:
            self._method.success(stanza.getData())
        except AttributeError:
            pass
        except AuthFail as error:
            log.error(error)
            self._abort_auth()
            raise NodeProcessed

        self._on_finished(True, None, None)
        raise NodeProcessed

    def _on_failure(self, _con, stanza):
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

        log.info('Failed SASL authentification: %s %s', reason, text)
        self._abort_auth(reason, text)
        raise NodeProcessed

    def _abort_auth(self, reason='malformed-request', text=None):
        node = Node('abort', attrs={'xmlns': NS_SASL})
        self._owner.send(node)
        self._owner.Connection.start_disconnect()
        self._on_finished(False, reason, text)


class PLAIN:

    _mechanism = 'PLAIN'

    def __init__(self, con):
        self._con = con

    def initiate(self, username, password):
        payload = b64encode('\x00%s\x00%s' % (username, password))
        node = Node('auth',
                    attrs={'xmlns': NS_SASL, 'mechanism': 'PLAIN'},
                    payload=[payload])
        self._con.send(node)


class EXTERNAL:

    _mechanism = 'EXTERNAL'

    def __init__(self, con):
        self._con = con

    def initiate(self, username, server):
        payload = b64encode('%s@%s' % (username, server))
        node = Node('auth',
                    attrs={'xmlns': NS_SASL, 'mechanism': 'EXTERNAL'},
                    payload=[payload])
        self._con.send(node)


class ANONYMOUS:

    _mechanism = 'ANONYMOUS'

    def __init__(self, con):
        self._con = con

    def initiate(self):
        node = Node('auth', attrs={'xmlns': NS_SASL, 'mechanism': 'ANONYMOUS'})
        self._con.send(node)


class GSSAPI:

    _mechanism = 'GSSAPI'

    def __init__(self, con):
        self._con = con
        self._gss_vc = None
        self._state = GSSAPIState.STEP

    def initiate(self, hostname):
        self._gss_vc = kerberos.authGSSClientInit('xmpp@%s' % hostname)[1]
        kerberos.authGSSClientStep(self._gss_vc, '')
        response = kerberos.authGSSClientResponse(self._gss_vc)
        node = Node('auth',
                    attrs={'xmlns': NS_SASL, 'mechanism': 'GSSAPI'},
                    payload=(response or ''))
        self._con.send(node)

    def response(self, server_message, *args, **kwargs):
        server_message = b64decode(server_message, bytes)
        if self._state == GSSAPIState.STEP:
            rc = kerberos.authGSSClientStep(self._gss_vc, server_message)
            if rc != kerberos.AUTH_GSS_CONTINUE:
                self._state = GSSAPIState.WRAP
        elif self._state == GSSAPIState.WRAP:
            rc = kerberos.authGSSClientUnwrap(self._gss_vc, server_message)
            response = kerberos.authGSSClientResponse(self._gss_vc)
            rc = kerberos.authGSSClientWrap(
                self._gss_vc,
                response,
                kerberos.authGSSClientUserName(self._gss_vc))
        response = kerberos.authGSSClientResponse(self._gss_vc)
        if not response:
            response = ''

        node = Node('response',
                    attrs={'xmlns': NS_SASL},
                    payload=response)
        self._con.send(node)


class SCRAM:

    _mechanism = ''
    _channel_binding = ''
    _hash_method = ''

    def __init__(self, con, channel_binding):
        self._con = con
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
                    attrs={'xmlns': NS_SASL, 'mechanism': self._mechanism},
                    payload=[payload])
        self._con.send(node)

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

        log.debug('Response: %s', client_finale_message)
        payload = b64encode(client_finale_message)
        node = Node('response',
                    attrs={'xmlns': NS_SASL},
                    payload=[payload])
        self._con.send(node)

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
    _channel_binding = 'y,,'
    _hash_method = 'sha1'


class SCRAM_SHA_1_PLUS(SCRAM_SHA_1):

    _mechanism = 'SCRAM-SHA-1-PLUS'
    _channel_binding = 'p=tls-unique,,'


class SCRAM_SHA_256(SCRAM):

    _mechanism = 'SCRAM-SHA-256'
    _channel_binding = 'y,,'
    _hash_method = 'sha256'


class SCRAM_SHA_256_PLUS(SCRAM_SHA_256):

    _mechanism = 'SCRAM-SHA-256-PLUS'
    _channel_binding = 'p=tls-unique,,'


class AuthFail(Exception):
    pass
