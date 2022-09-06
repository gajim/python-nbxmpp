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

import logging
from typing import Any
from typing import Optional

from gi.repository import GLib

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Features
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.protocol import SessionRequest
from nbxmpp.protocol import BindRequest
from nbxmpp.protocol import TLSRequest
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import JID
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import WebsocketCloseHeader
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.errors import CancelledError
from nbxmpp.addresses import ServerAddresses
from nbxmpp.addresses import NoMoreAddresses
from nbxmpp.tcp import TCPConnection
from nbxmpp.websocket import WebsocketConnection
from nbxmpp.smacks import Smacks
from nbxmpp.sasl import SASL
from nbxmpp.const import StreamState
from nbxmpp.const import StreamError
from nbxmpp.const import ConnectionType
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import Mode
from nbxmpp.dispatcher import StanzaDispatcher
from nbxmpp.util import get_stream_header
from nbxmpp.util import generate_id
from nbxmpp.util import Observable
from nbxmpp.util import validate_stream_header
from nbxmpp.util import LogAdapter

log = logging.getLogger('nbxmpp.stream')


class Client(Observable):
    def __init__(self, log_context=None):
        '''
        Signals:
            resume-failed
            resume-successful
            login-successful
            anonymous-supported
            disconnected
            connected
            connection-failed
            stanza-sent
            stanza-received
        '''

        self._log_context = log_context
        if log_context is None:
            self._log_context = str(id(self))

        self._log = LogAdapter(log, {'context': self._log_context})

        Observable.__init__(self, self._log)

        self._jid = None
        self._lang = 'en'
        self._domain = None
        self._username = None
        self._resource = None

        self._custom_host = None

        self._addresses = None
        self._current_address = None
        self._address_generator = None

        self._client_cert = None
        self._client_cert_pass = None
        self._proxy = None

        self._allowed_con_types = None
        self._allowed_protocols = None
        self._allowed_mechs = None

        self._sm_disabled = False

        self._stream_id = None
        self._stream_secure = False
        self._stream_authenticated = False
        self._stream_features = None
        self._session_required = False
        self._connect_successful = False
        self._stream_close_initiated = False
        self._ping_task = None
        self._error = None, None, None

        self._ignored_tls_errors = set()
        self._ignore_tls_errors = False
        self._accepted_certificates = []
        self._peer_certificate = None
        self._peer_certificate_errors = None

        self._con = None
        self._local_address = None
        self._remote_address = None
        self._mode = Mode.CLIENT

        self._ping_source_id = None
        self._tasks = []

        self._dispatcher = StanzaDispatcher(self)
        self._dispatcher.subscribe('before-dispatch', self._on_before_dispatch)
        self._dispatcher.subscribe('parsing-error', self._on_parsing_error)
        self._dispatcher.subscribe('stream-end', self._on_stream_end)

        self._smacks = Smacks(self)
        self._sasl = SASL(self)

        self._state = StreamState.DISCONNECTED

    def add_task(self, task):
        self._tasks.append(task)

    def remove_task(self, task, _context):
        try:
            self._tasks.remove(task)
        except Exception:
            pass

    @property
    def log_context(self):
        return self._log_context

    @property
    def features(self):
        return self._stream_features

    @property
    def resumeable(self):
        return self._smacks.resumeable

    @property
    def sm_supported(self):
        return self._smacks.sm_supported

    @property
    def lang(self):
        return self._lang

    @property
    def username(self):
        return self._username

    @property
    def domain(self):
        return self._domain

    @property
    def resource(self):
        return self._resource

    def set_username(self, username):
        self._username = username

    def set_domain(self, domain):
        self._domain = domain

    def set_resource(self, resource):
        self._resource = resource

    def set_mode(self, mode):
        self._mode = mode

    @property
    def custom_host(self):
        return self._custom_host

    def set_custom_host(self, host_or_uri, protocol, type_):
        if self._domain is None:
            raise ValueError('Call set_domain() first before set_custom_host()')
        self._custom_host = (host_or_uri, protocol, type_)

    def set_accepted_certificates(self, certificates):
        self._accepted_certificates = certificates

    @property
    def ignored_tls_errors(self):
        return self._ignored_tls_errors

    def set_ignored_tls_errors(self, errors):
        if errors is None:
            errors = set()
        self._ignored_tls_errors = errors

    @property
    def ignore_tls_errors(self):
        return self._ignore_tls_errors

    @property
    def tls_version(self):
        return self._con.tls_version

    @property
    def ciphersuite(self):
        return self._con.ciphersuite

    def set_ignore_tls_errors(self, ignore):
        self._ignore_tls_errors = ignore

    def set_password(self, password):
        self._sasl.set_password(password)

    @property
    def password(self):
        return self._sasl.password

    @property
    def peer_certificate(self):
        return self._peer_certificate, self._peer_certificate_errors

    @property
    def current_address(self):
        return self._current_address

    @property
    def current_connection_type(self):
        return self._current_address.type

    @property
    def is_websocket(self):
        return self._current_address.protocol == ConnectionProtocol.WEBSOCKET

    @property
    def stream_id(self):
        return self._stream_id

    @property
    def is_stream_secure(self):
        direct_tls = self.current_connection_type == ConnectionType.DIRECT_TLS
        return self._stream_secure or direct_tls

    @property
    def is_stream_authenticated(self):
        return self._stream_authenticated

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self._log.info('Set state: %s', value)

    def set_state(self, state):
        self.state = state
        self._xmpp_state_machine()

    @property
    def local_address(self):
        return self._local_address

    @property
    def remote_address(self):
        return self._remote_address

    @property
    def connection_types(self):
        if self._custom_host is not None:
            return [self._custom_host[2]]
        return list(self._allowed_con_types or [ConnectionType.DIRECT_TLS,
                                                ConnectionType.START_TLS])

    def set_connection_types(self, con_types):
        self._allowed_con_types = con_types

    @property
    def mechs(self):
        return set(self._allowed_mechs or set(['SCRAM-SHA-512',
                                               'SCRAM-SHA-256',
                                               'SCRAM-SHA-1',
                                               'PLAIN']))

    def set_mechs(self, mechs):
        self._allowed_mechs = mechs

    @property
    def protocols(self):
        if self._custom_host is not None:
            return [self._custom_host[1]]
        return list(self._allowed_protocols or [ConnectionProtocol.TCP,
                                                ConnectionProtocol.WEBSOCKET])

    def set_protocols(self, protocols):
        self._allowed_protocols = protocols

    def set_sm_disabled(self, value):
        self._sm_disabled = value

    @property
    def sm_disabled(self):
        return self._sm_disabled

    @property
    def client_cert(self):
        return self._client_cert, self._client_cert_pass

    def set_client_cert(self, client_cert, client_cert_pass):
        self._client_cert = client_cert
        self._client_cert_pass = client_cert_pass

    def set_proxy(self, proxy):
        self._proxy = proxy
        self._dispatcher.get_module('Muclumbus').set_proxy(proxy)

    @property
    def proxy(self):
        return self._proxy

    def get_bound_jid(self):
        return self._jid

    def _set_bound_jid(self, jid):
        self._jid = JID.from_string(jid)

    @property
    def has_error(self):
        return self._error[0] is not None

    def get_error(self):
        return self._error

    def _reset_error(self):
        self._error = None, None, None

    def _set_error(self, domain, error, text=None):
        self._log.info('Set error: %s, %s, %s', domain, error, text)
        self._error = domain, error, text

    def _connect(self):
        if self._state not in (StreamState.DISCONNECTED, StreamState.RESOLVED):
            self._log.error('Stream can\'t connect, stream state: %s',
                            self._state)
            return

        self.state = StreamState.CONNECTING
        self._reset_error()

        self._con = self._get_connection(self._log_context,
                                         self._current_address,
                                         self._accepted_certificates,
                                         self._ignore_tls_errors,
                                         self._ignored_tls_errors,
                                         self.client_cert)

        self._con.subscribe('connected', self._on_connected)
        self._con.subscribe('connection-failed', self._on_connection_failed)
        self._con.subscribe('disconnected', self._on_disconnected)
        self._con.subscribe('data-sent', self._on_data_sent)
        self._con.subscribe('data-received', self._on_data_received)
        self._con.subscribe('bad-certificate', self._on_bad_certificate)
        self._con.subscribe('certificate-set', self._on_certificate_set)
        self._con.connect()

    def _get_connection(self, *args):
        if self.is_websocket:
            return WebsocketConnection(*args)
        return TCPConnection(*args)

    def connect(self):
        if self._state != StreamState.DISCONNECTED:
            self._log.error('Stream can\'t reconnect, stream state: %s',
                            self._state)
            return

        if self._connect_successful:
            self._log.info('Reconnect')
            self._connect()
            return

        self._log.info('Connect')
        self._reset_error()
        self.state = StreamState.RESOLVE

        self._addresses = ServerAddresses(self._domain)
        self._addresses.set_custom_host(self._custom_host)
        self._addresses.set_proxy(self._proxy)
        self._addresses.subscribe('resolved', self._on_addresses_resolved)
        self._addresses.resolve()

    def _on_addresses_resolved(self, _addresses, _signal_name):
        self._log.info('Domain resolved')
        self._log.info(self._addresses)
        self.state = StreamState.RESOLVED
        self._address_generator = self._addresses.get_next_address(
            self.connection_types,
            self.protocols)

        self._try_next_ip()

    def _try_next_ip(self, *args):
        try:
            self._current_address = next(self._address_generator)
        except NoMoreAddresses:
            self._current_address = None
            self.state = StreamState.DISCONNECTED
            self._log.error('Unable to connect to %s', self._addresses.domain)
            self._set_error(StreamError.CONNECTION_FAILED,
                            'connection-failed',
                            'Unable to connect to %s' % self._addresses.domain)
            self.notify('connection-failed')
            return

        self._log.info('Current address: %s', self._current_address)
        self._connect()

    def disconnect(self, immediate=False):
        if self._state == StreamState.RESOLVE:
            self._addresses.cancel_resolve()
            self.state = StreamState.DISCONNECTED
            return

        if self._state == StreamState.CONNECTING:
            self._disconnect()
            return

        if self._state in (StreamState.DISCONNECTED,
                           StreamState.DISCONNECTING):
            self._log.warning('Stream can\'t disconnect, stream state: %s',
                              self._state)
            return

        self._disconnect(immediate=immediate)

    def _disconnect(self, immediate=True):
        self.state = StreamState.DISCONNECTING
        self._remove_ping_timer()
        self._cancel_ping_task()

        if not immediate:
            self._stream_close_initiated = True
            self._smacks.close_session()
            self._end_stream()
            self._con.shutdown_output()
        else:
            self._con.disconnect()

    def send(self, stanza, *args, **kwargs):
        # Alias for backwards compat
        return self.send_stanza(stanza)

    def _on_connected(self, connection, _signal_name):
        self.set_state(StreamState.CONNECTED)
        self._local_address = connection.local_address
        self._remote_address = connection.remote_address

    def _on_disconnected(self, _connection, _signal_name):
        self.state = StreamState.DISCONNECTED
        for task in self._tasks:
            task.cancel()
        self._remove_ping_timer()
        self._cancel_ping_task()
        self._reset_stream()
        self.notify('disconnected')

    def _on_connection_failed(self, _connection, _signal_name):
        self.state = StreamState.DISCONNECTED
        self._reset_stream()
        if not self._connect_successful:
            self._try_next_ip()
        else:
            self._set_error(StreamError.CONNECTION_FAILED,
                            'connection-failed',
                            ('Unable to connect to last '
                             f'successful address: {self._current_address}'))
            self.notify('connection-failed')

    def _disconnect_with_error(self, error_domain, error, text=None):
        self._set_error(error_domain, error, text)
        self.disconnect()

    def _on_parsing_error(self, _dispatcher, _signal_name, error):
        if self._state == StreamState.DISCONNECTING:
            # Don't notify about parsing errors if we already ended the stream
            return
        self._disconnect_with_error(StreamError.PARSING, 'parsing-error', error)

    def _on_stream_end(self, _dispatcher, _signal_name, error):
        if not self.has_error:
            self._set_error(StreamError.STREAM, error or 'stream-end')

        self._con.shutdown_input()
        if not self._stream_close_initiated:
            self.state = StreamState.DISCONNECTING
            self._remove_ping_timer()
            self._cancel_ping_task()
            self._smacks.close_session()
            self._end_stream()
            self._con.shutdown_output()

    def _reset_stream(self):
        self._stream_id = None
        self._stream_secure = False
        self._stream_authenticated = False
        self._stream_features = None
        self._session_required = False
        self._con = None

    def _end_stream(self):
        if self.is_websocket:
            nonza = WebsocketCloseHeader()
        else:
            nonza = '</stream:stream>'
        self.send_nonza(nonza)

    def get_module(self, name):
        return self._dispatcher.get_module(name)

    def _on_bad_certificate(self, connection, _signal_name):
        self._peer_certificate, self._peer_certificate_errors = \
            connection.peer_certificate
        self._set_error(StreamError.BAD_CERTIFICATE, 'bad certificate')

    def _on_certificate_set(self, connection, _signal_name):
        self._peer_certificate, self._peer_certificate_errors = \
            connection.peer_certificate

    def accept_certificate(self):
        self._log.info('Certificate accepted')
        self._accepted_certificates.append(self._peer_certificate)
        self._connect()

    def _on_data_sent(self, _connection, _signal_name, data):
        self.notify('stanza-sent', data)

    def _on_before_dispatch(self, _dispatcher, _signal_name, data):
        self.notify('stanza-received', data)

    def _on_data_received(self, _connection, _signal_name, data):
        self._dispatcher.process_data(data)
        self._reset_ping_timer()

    def _reset_ping_timer(self):
        if self.is_websocket:
            return

        if not self._mode.is_client:
            return

        if self.state != StreamState.ACTIVE:
            return

        if self._ping_source_id is not None:
            self._log.info('Remove ping timer')
            GLib.source_remove(self._ping_source_id)
            self._ping_source_id = None

        self._log.info('Start ping timer')
        self._ping_source_id = GLib.timeout_add_seconds(180, self._ping)

    def _remove_ping_timer(self):
        if self._ping_source_id is None:
            return
        self._log.info('Remove ping timer')
        GLib.source_remove(self._ping_source_id)
        self._ping_source_id = None

    def send_stanza(self,
                    stanza: Protocol,
                    now: bool = False,
                    callback: Optional[Any] = None,
                    timeout: Optional[int] = None,
                    user_data: Optional[Any] = None) -> str:

        if user_data is not None and not isinstance(user_data, dict):
            raise ValueError('arg user_data must be of dict type')

        if not isinstance(stanza, Protocol):
            raise ValueError('Nonzas not allowed, use send_nonza()')

        id_ = stanza.getID()
        if id_ is None:
            id_ = generate_id()
            stanza.setID(id_)

        if callback is not None:
            self._dispatcher.add_callback_for_id(
                id_, callback, timeout, user_data)
        self._con.send(stanza, now)
        self._smacks.save_in_queue(stanza)
        return id_

    def SendAndCallForResponse(self, stanza, callback, user_data=None):
        self.send_stanza(stanza, callback=callback, user_data=user_data)

    def send_nonza(self, nonza, now=False):
        self._con.send(nonza, now)

    def _xmpp_state_machine(self, stanza=None):
        self._log.info('Execute state machine')
        if stanza is not None:
            if stanza.getName() == 'error':
                self._log.info('Stream error')
                # TODO:
                # self._disconnect_with_error(StreamError.SASL,
                #                             stanza.get_condition())
                return

        if self.state == StreamState.CONNECTED:
            self._dispatcher.set_dispatch_callback(self._xmpp_state_machine)
            if (self.current_connection_type == ConnectionType.DIRECT_TLS and
                    not self.is_websocket):
                self._con.start_tls_negotiation()
                self._stream_secure = True
                self._start_stream()
                return

            self._start_stream()

        elif self.state == StreamState.WAIT_FOR_STREAM_START:
            try:
                self._stream_id = validate_stream_header(stanza,
                                                         self._domain,
                                                         self.is_websocket)
            except StanzaMalformed as error:
                self._log.error(error)
                self._disconnect_with_error(StreamError.STREAM,
                                            'stanza-malformed',
                                            'Invalid stream header')
                return

            if (self._stream_secure or
                    self.current_connection_type == ConnectionType.PLAIN):
                # TLS Negotiation succeeded or we are connected PLAIN
                # We received the stream header and consider this as
                # successfully connected, this means we will not try
                # other connection methods if an error happensafterwards
                self._connect_successful = True

            if self._stream_authenticated and self._mode.is_login_test:
                self.notify('login-successful')
                self.disconnect()
                return

            self.state = StreamState.WAIT_FOR_FEATURES

        elif self.state == StreamState.WAIT_FOR_FEATURES:
            if stanza.getName() != 'features':
                self._log.error('Invalid response: %s', stanza)
                self._disconnect_with_error(
                    StreamError.STREAM,
                    'stanza-malformed',
                    'Invalid response, expected features')
                return
            self._on_stream_features(Features(stanza))

        elif self.state == StreamState.WAIT_FOR_TLS_PROCEED:
            if stanza.getNamespace() != Namespace.TLS:
                self._disconnect_with_error(
                    StreamError.TLS,
                    'stanza-malformed',
                    'Invalid namespace for TLS response')
                return

            if stanza.getName() == 'failure':
                self._disconnect_with_error(StreamError.TLS,
                                            'negotiation-failed')
                return

            if stanza.getName() == 'proceed':
                self._con.start_tls_negotiation()
                self._stream_secure = True
                self._start_stream()
                return

            self._log.error('Invalid response')
            self._disconnect_with_error(StreamError.TLS,
                                        'stanza-malformed',
                                        'Invalid TLS response')
            return

        elif self.state == StreamState.PROCEED_WITH_AUTH:
            self._sasl.delegate(stanza)

        elif self.state == StreamState.AUTH_SUCCESSFUL:
            self._stream_authenticated = True
            if self._sasl.is_sasl2():
                self.state = StreamState.WAIT_FOR_FEATURES
            else:
                self._start_stream()

        elif self.state == StreamState.AUTH_FAILED:
            self._disconnect_with_error(StreamError.SASL,
                                        *self._sasl.error)

        elif self.state == StreamState.WAIT_FOR_BIND:
            self._on_bind(stanza)

        elif self.state == StreamState.BIND_SUCCESSFUL:
            self._dispatcher.clear_iq_callbacks()
            self._dispatcher.set_dispatch_callback(None)
            self._smacks.send_enable()
            self.state = StreamState.ACTIVE
            self.notify('connected')

        elif self.state == StreamState.WAIT_FOR_SESSION:
            self._on_session(stanza)

        elif self.state == StreamState.WAIT_FOR_RESUMED:
            self._smacks.delegate(stanza)

        elif self.state == StreamState.RESUME_FAILED:
            self.notify('resume-failed')
            self._start_bind()

        elif self.state == StreamState.RESUME_SUCCESSFUL:
            self._dispatcher.set_dispatch_callback(None)
            self.state = StreamState.ACTIVE
            self.notify('resume-successful')

    def _on_stream_features(self, features):
        if self.is_stream_authenticated:
            self._stream_features = features
            self._smacks.sm_supported = features.has_sm()
            self._session_required = features.session_required()
            if self._smacks.resume_supported:
                self._smacks.resume_request()
                self.state = StreamState.WAIT_FOR_RESUMED
            else:
                self._start_bind()

        elif self.is_stream_secure:
            if self._mode.is_register:
                if features.has_register():
                    self.state = StreamState.ACTIVE
                    self._dispatcher.set_dispatch_callback(None)
                    self.notify('connected')
                else:
                    self._disconnect_with_error(StreamError.REGISTER,
                                                'register-not-supported')
                return

            if self._mode.is_anonymous_test:
                if features.has_anonymous():
                    self.notify('anonymous-supported')
                    self.disconnect()
                else:
                    self._disconnect_with_error(StreamError.SASL,
                                                'anonymous-not-supported')
                return

            self._start_auth(features)

        else:
            tls_supported, required = features.has_starttls()
            if self._current_address.type == ConnectionType.PLAIN:
                if tls_supported and required:
                    self._log.error('Server requires TLS')
                    self._disconnect_with_error(StreamError.TLS, 'tls-required')
                    return
                self._start_auth(features)
                return

            if not tls_supported:
                self._log.error('Server does not support TLS')
                self._disconnect_with_error(StreamError.TLS,
                                            'tls-not-supported')
                return
            self._start_tls()

    def _start_stream(self):
        self._log.info('Start stream')
        self._stream_id = None
        self._dispatcher.reset_parser()
        header = get_stream_header(self._domain, self._lang, self.is_websocket)
        self.send_nonza(header)
        self.state = StreamState.WAIT_FOR_STREAM_START

    def _start_tls(self):
        self.send_nonza(TLSRequest())
        self.state = StreamState.WAIT_FOR_TLS_PROCEED

    def _start_auth(self, features):
        if not features.has_sasl() and not features.has_sasl_2():
            self._log.error('Server does not support SASL')
            self._disconnect_with_error(StreamError.SASL,
                                        'sasl-not-supported')
            return
        self.state = StreamState.PROCEED_WITH_AUTH
        self._sasl.start_auth(features)

    def _start_bind(self):
        self._log.info('Send bind')
        bind_request = BindRequest(self.resource)
        self.send_stanza(bind_request)
        self.state = StreamState.WAIT_FOR_BIND

    def _on_bind(self, stanza):
        if not isResultNode(stanza):
            self._disconnect_with_error(StreamError.BIND,
                                        stanza.getError(),
                                        stanza.getErrorMsg())
            return

        jid = stanza.getTag('bind').getTagData('jid')
        self._log.info('Successfully bound %s', jid)
        self._set_bound_jid(jid)

        if not self._session_required:
            # Server don't want us to initialize a session
            self._log.info('No session required')
            self.set_state(StreamState.BIND_SUCCESSFUL)
        else:
            session_request = SessionRequest()
            self.send_stanza(session_request)
            self.state = StreamState.WAIT_FOR_SESSION

    def _on_session(self, stanza):
        if isResultNode(stanza):
            self._log.info('Successfully started session')
            self.set_state(StreamState.BIND_SUCCESSFUL)
        else:
            self._log.error('Session open failed')
            self._disconnect_with_error(StreamError.SESSION,
                                        stanza.getError(),
                                        stanza.getErrorMsg())

    def _ping(self):
        self._ping_source_id = None
        self._ping_task = self.get_module('Ping').ping(
            self.domain,
            timeout=10,
            callback=self._on_pong)

    def _on_pong(self, task):
        self._ping_task = None

        try:
            task.finish()
        except TimeoutStanzaError:
            self._log.info('Ping timeout')
            self._disconnect(immediate=True)
            return

        except CancelledError:
            return

        except StanzaError:
            pass

        self._log.info('Pong')

    def _cancel_ping_task(self):
        if self._ping_task is not None:
            self._ping_task.cancel()

    def register_handler(self, *args, **kwargs):
        self._dispatcher.register_handler(*args, **kwargs)

    def unregister_handler(self, *args, **kwargs):
        self._dispatcher.unregister_handler(*args, **kwargs)

    def destroy(self):
        for task in self._tasks:
            task.cancel()
        self._remove_ping_timer()
        self._smacks = None
        self._sasl = None
        self._dispatcher.cleanup()
        self._dispatcher = None
        self.remove_subscriptions()
