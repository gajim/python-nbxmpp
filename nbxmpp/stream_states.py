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

from nbxmpp.elements import Nonza
from nbxmpp.elements import register_class_lookup
from nbxmpp.namespaces import Namespace
from nbxmpp.const import ConnectionType
from nbxmpp.const import StreamError
from nbxmpp.const import StreamState
from nbxmpp.exceptions import StanzaMalformed
from nbxmpp.modules.stream import Features, make_bind_request
from nbxmpp.util import validate_stream_header
from nbxmpp.builder import E
from nbxmpp.builder import Iq


if typing.TYPE_CHECKING:
    from nbxmpp import types


class State:

    def __init__(self, client: types.Client) -> None:
        self._client = client

    def handle(self, element: types.Base):
        pass

    @property
    def client(self) -> types.Client:
        return self._client

    @client.setter
    def client(self, client: types.Client):
        self._client = client

    def _start_stream(self):
        self._client._log.info('Start stream')
        self._client._stream_id = None
        self._client._dispatcher.reset_parser()
        self._client._con.start_stream(self._client.domain, lang=self._client._lang)
        self._client.state = StreamState.WAIT_FOR_STREAM_START

    def _start_tls(self):
        self._client.send_nonza(E('starttls', namespace=Namespace.TLS))
        self._client.state = StreamState.WAIT_FOR_TLS_PROCEED

    def _start_auth(self, features):
        if not features.has_sasl():
            self._client._log.error('Server does not support SASL')
            self._client._disconnect_with_error(StreamError.SASL,
                                        'sasl-not-supported')
            return
        self._client.state = StreamState.PROCEED_WITH_AUTH
        self._client._sasl.start_auth(features)

    def _start_bind(self):
        self._client._log.info('Send bind')

        bind_request = make_bind_request(self._client.resource)
        self._client.send_stanza(bind_request)
        self._client.state = StreamState.WAIT_FOR_BIND


class Connected(State):

    def handle(self, stanza: types.Base):
        self.client._dispatcher.set_dispatch_callback(self.client._xmpp_state_machine)
        if (self.client.current_connection_type == ConnectionType.DIRECT_TLS and
                not self.client.is_websocket):
            self.client._con.start_tls_negotiation()
            self.client._stream_secure = True
            self._start_stream()
            return

        self._start_stream()


class WaitForStreamStart(State):

    def handle(self, stanza: types.Base):
        try:
            self.client._stream_id = validate_stream_header(stanza,
                                                            self.client._domain,
                                                            self.client.is_websocket)
        except StanzaMalformed as error:
            self.client._log.error(error)
            self.client._disconnect_with_error(StreamError.STREAM,
                                        'stanza-malformed',
                                        'Invalid stream header')
            return

        if (self.client._stream_secure or
                self.client.current_connection_type == ConnectionType.PLAIN):
            # TLS Negotiation succeeded or we are connected PLAIN
            # We received the stream header and consider this as
            # successfully connected, this means we will not try
            # other connection methods if an error happensafterwards
            self.client._connect_successful = True

        self.client.state = StreamState.WAIT_FOR_FEATURES


class WaitForFeatures(State):

    def handle(self, element: types.Base):
        if not isinstance(element, Features):
            raise ValueError('invalid response')

        if element.localname != 'features':
            self.client._log.error('Invalid response: %s', element)
            self.client._disconnect_with_error(
                StreamError.STREAM,
                'stanza-malformed',
                'Invalid response, expected features')
            return

        features = element

        if self.client.is_stream_authenticated:
            self.client._stream_features = features
            self.client._smacks.sm_supported = features.has_sm()
            self.client._session_required = features.session_required()
            if self.client._smacks.resume_supported:
                self.client._smacks.resume_request()
                self.client.state = StreamState.WAIT_FOR_RESUMED
            else:
                self._start_bind()

        elif self.client.is_stream_secure:
            if self.client._mode.is_register:
                if features.has_register():
                    self.client.state = StreamState.ACTIVE
                    self.client._dispatcher.set_dispatch_callback(None)
                    self.client.notify('connected')
                else:
                    self.client._disconnect_with_error(StreamError.REGISTER,
                                                'register-not-supported')
                return

            if self.client._mode.is_anonymous_test:
                if features.has_anonymous():
                    self.client.notify('anonymous-supported')
                    self.client.disconnect()
                else:
                    self.client._disconnect_with_error(StreamError.SASL,
                                                'anonymous-not-supported')
                return

            self._start_auth(features)

        else:
            tls_supported, required = features.has_starttls()
            if self.client._current_address.type == ConnectionType.PLAIN:
                if tls_supported and required:
                    self.client._log.error('Server requires TLS')
                    self.client._disconnect_with_error(StreamError.TLS, 'tls-required')
                    return
                self._start_auth(features)
                return

            if not tls_supported:
                self.client._log.error('Server does not support TLS')
                self.client._disconnect_with_error(StreamError.TLS,
                                            'tls-not-supported')
                return

            self._start_tls()


class WaitForTlsProceed(State):

    def handle(self, stanza: types.Base):
        if stanza.namespace != Namespace.TLS:
            self.client._disconnect_with_error(
                StreamError.TLS,
                'stanza-malformed',
                'Invalid namespace for TLS response')
            return

        if stanza.localname == 'failure':
            self.client._disconnect_with_error(StreamError.TLS,
                                        'negotiation-failed')
            return

        if stanza.localname == 'proceed':
            self.client._con.start_tls_negotiation()
            self.client._stream_secure = True
            self._start_stream()
            return

        self.client._log.error('Invalid response')
        self.client._disconnect_with_error(StreamError.TLS,
                                    'stanza-malformed',
                                    'Invalid TLS response')
        return


class ProceedWithAuth(State):

    def handle(self, stanza: types.Base):

        self.client._sasl.delegate(stanza)


class AuthSuccessful(State):

    def handle(self, stanza: types.Base):

        self.client._stream_authenticated = True
        if self.client._mode.is_login_test:
            self.client.notify('login-successful')
            # Reset parser because we will receive a new stream header
            # which will otherwise lead to a parsing error
            self.client._dispatcher.reset_parser()
            self.client.disconnect()
            return

        self._start_stream()


class AuthFailed(State):

    def handle(self, stanza: types.Base):

        self.client._disconnect_with_error(StreamError.SASL,
                                    *self.client._sasl.error)


class WaitForBind(State):

    def handle(self, stanza: types.Base):
        if not stanza.is_result():
            self.client._disconnect_with_error(StreamError.BIND,
                                        stanza.getError(),
                                        stanza.getErrorMsg())
            return

        jid = stanza.find_tag('bind', namespace=Namespace.BIND).find_tag_text('jid')
        self.client._log.info('Successfully bound %s', jid)
        self.client._set_bound_jid(jid)

        if not self.client._session_required:
            # Server don't want us to initialize a session
            self.client._log.info('No session required')
            self.client.set_state(StreamState.BIND_SUCCESSFUL)
        else:
            iq = Iq(type='set')
            iq.add_tag('session', namespace=Namespace.SESSION)
            self.client.send_stanza(iq)
            self.client.state = StreamState.WAIT_FOR_SESSION


class BindSuccessful(State):

    def handle(self, stanza: types.Base):
        self.client._dispatcher.clear_iq_callbacks()
        self.client._dispatcher.set_dispatch_callback(None)
        self.client._smacks.send_enable()
        self.client.state = StreamState.ACTIVE
        self.client.notify('connected')


class WaitForSession(State):

    def handle(self, stanza: types.Base):
        if stanza.is_result():
            self.client._log.info('Successfully started session')
            self.client.set_state(StreamState.BIND_SUCCESSFUL)
        else:
            self.client._log.error('Session open failed')
            self.client._disconnect_with_error(StreamError.SESSION,
                                        stanza.getError(),
                                        stanza.getErrorMsg())


class WaitForResumed(State):

    def handle(self, stanza: types.Base):
        self.client._smacks.delegate(stanza)


class ResumeFailed(State):

    def handle(self, stanza: types.Base):
        self.client.notify('resume-failed')
        self._start_bind()


class ResumeSuccessful(State):

    def handle(self, stanza: types.Base):
        self.client._dispatcher.set_dispatch_callback(None)
        self.client.state = StreamState.ACTIVE
        self.client.notify('resume-successful')


register_class_lookup('proceed', Namespace.TLS, Nonza)
