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

import time
import logging
from copy import deepcopy

from nbxmpp.namespaces import Namespace
from nbxmpp.const import StreamState
from nbxmpp.util import LogAdapter
from nbxmpp.structs import StanzaHandler
from nbxmpp.builder import E

if typing.TYPE_CHECKING:
    from nbxmpp import types
    from nbxmpp.client import Client


log = logging.getLogger('nbxmpp.smacks')


def make_sm_element(tag: str, **kwargs: Any):
    return E(tag, namespace=Namespace.STREAM_MGMT, **kwargs)


class Smacks:
    """
    This is Smacks is the Stream Management class. It takes care of requesting
    and sending acks. Also, it keeps track of the unhandled outgoing stanzas.

    The dispatcher has to be able to access this class to increment the
    number of handled stanzas
    """

    def __init__(self, client: Client):
        self._client = client
        self._out_h = 0  # Outgoing stanzas handled
        self._in_h = 0  # Incoming stanzas handled
        self._acked_h = 0  # Last acked stanza

        self._uqueue: list[types.Base] = []  # Unhandled stanzas queue
        self._old_uqueue: list[types.Base] = []  # Unhandled stanzas queue of the last session

        # Max number of stanzas in queue before making a request
        self.max_queue = 0

        self._sm_supported = False
        self.enabled = False  # If SM is enabled
        self._enable_sent = False  # If we sent 'enable'
        self.resumed = False  # If the session was resumed
        self.resume_in_progress = False
        self.resume_supported = False  # Does the session support resume

        self._session_id = None
        self._location = None

        self._log = LogAdapter(log, {'context': client.log_context})

        self.register_handlers()

    @property
    def sm_supported(self) -> bool:
        return self._sm_supported

    @sm_supported.setter
    def sm_supported(self, value: bool):
        self._log.info('Server support detected: %s', value)
        self._sm_supported = value

    def delegate(self, stanza: types.Base):
        if stanza.namespace != Namespace.STREAM_MGMT:
            return
        if stanza.localname == 'resumed':
            self._on_resumed(stanza)
        elif stanza.localname == 'failed':
            self._on_failed(None, stanza, None)

    def register_handlers(self):
        handlers = [
            StanzaHandler(name='enabled',
                          callback=self._on_enabled,
                          xmlns=Namespace.STREAM_MGMT),
            StanzaHandler(name='failed',
                          callback=self._on_failed,
                          xmlns=Namespace.STREAM_MGMT),
            StanzaHandler(name='r',
                          callback=self._send_ack,
                          xmlns=Namespace.STREAM_MGMT),
            StanzaHandler(name='a',
                          callback=self._on_ack,
                          xmlns=Namespace.STREAM_MGMT)
        ]

        for handler in handlers:
            self._client.register_handler(handler)

    def send_enable(self):
        if not self.sm_supported:
            return

        if self._client.sm_disabled:
            return

        element = make_sm_element('enable', resume='true')
        self._client.send_nonza(element, now=False)
        self._log.debug('Send enable')
        self._enable_sent = True

    def _on_enabled(self,
                    _client: Client,
                    stanza: types.Base,
                    _properties: Any):

        if self.enabled:
            self._log.error('Received "enabled", but SM is already enabled')
            return

        resume = stanza.get('resume')
        if resume in ('true', 'True', '1'):
            self.resume_supported = True
            self._session_id = stanza.get('id')

        self._location = stanza.get('location')
        self.enabled = True
        self._log.info(
            'Received enabled, location: %s, resume supported: %s, '
            'session-id: %s', self._location, resume, self._session_id)

    def count_incoming(self, name: str):
        if not self.enabled:
            # Dont count while we didnt receive 'enabled'
            return

        if name in ('a', 'r', 'resumed', 'enabled'):
            return

        self._log.debug('IN, %s', name)
        self._in_h += 1

    def save_in_queue(self, stanza: types.Base):
        if not self._enable_sent and not self.resumed:
            # We did not yet sent 'enable' so the server
            # will not count our stanzas
            return

        # Make a full copy so we dont run into problems when
        # the stanza is modified after sending for some reason
        stanza = deepcopy(stanza)

        self._add_delay(stanza)

        self._uqueue.append(stanza)
        self._log.debug('OUT, %s', stanza.localname)
        self._out_h += 1

        if len(self._uqueue) > self.max_queue:
            self._request_ack()
        # Send an ack after 100 unacked messages
        if (self._in_h - self._acked_h) > 100:
            self._send_ack()

    def _add_delay(self, stanza: types.Base):
        if stanza.localname != 'message':
            return

        if stanza.get('type') not in ('chat', 'groupchat'):
            return

        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        attrs = {'stamp': timestamp}

        if stanza.get('type') != 'groupchat':
            # Dont leak our JID to Groupchats
            attrs['from'] = str(self._client.get_bound_jid())

        stanza.add_tag('delay', namespace=Namespace.DELAY2, **attrs)

    def _resend_queue(self):
        """
        Resends unsent stanzas when a new session is established.
        This way there won't be any lost outgoing messages even on failed
        smacks resumes (but message duplicates are possible).
        """
        if not self._old_uqueue:
            return
        self._log.info('Resend %s stanzas', len(self._old_uqueue))
        for stanza in self._old_uqueue:
            # Use dispatcher so we increment the counter
            self._client.send_stanza(stanza)
        self._old_uqueue = []

    def resume_request(self):
        if self._session_id is None:
            self._log.error('Attempted to resume without a valid session id')
            return

        # Save old messages in an extra "queue" to avoid race conditions
        # and to make it possible to replay stanzas even when resuming fails
        # Add messages here (instead of overwriting) so that repeated
        # connection errors don't delete unacked stanzas
        # (uqueue should be empty in this case anyways)
        self._old_uqueue += self._uqueue
        self._uqueue = []

        element = make_sm_element('resume',
                                  h=self._in_h,
                                  previd=self._session_id)

        self._acked_h = self._in_h
        self.resume_in_progress = True
        self._client.send_nonza(element, now=False)

    def _on_resumed(self, stanza: types.Base):
        """
        Checks if the number of stanzas sent are the same as the
        number of stanzas received by the server. Resends stanzas not received
        by the server in the last session.
        """
        self._log.info('Session resumption succeeded, session-id: %s',
                       self._session_id)
        self._validate_ack(stanza, self._old_uqueue)
        # Set our out h to the h we received
        self._out_h = int(stanza.get('h'))
        self.enabled = True
        self.resumed = True
        self.resume_in_progress = False
        self._client.set_state(StreamState.RESUME_SUCCESSFUL)
        self._resend_queue()

    def _send_ack(self, *args: Any):
        element = make_sm_element('a', h=self._in_h)
        self._acked_h = self._in_h
        self._log.debug('Send ack, h: %s', self._in_h)
        self._client.send_nonza(element, now=False)

    def close_session(self):
        # We end the connection deliberately
        # Reset the state -> no resume
        self._log.info('Close session')
        self._reset_state()

    def _request_ack(self):
        element = make_sm_element('r')
        self._log.debug('Request ack')
        self._client.send_nonza(element, now=False)

    def _on_ack(self,
                _client: Client,
                stanza: types.Base,
                _properties: Any):

        if not self.enabled:
            return

        self._log.debug('Ack received, h: %s', stanza.get('h'))
        self._validate_ack(stanza, self._uqueue)

    def _validate_ack(self,
                      stanza: types.Base,
                      queue: list[types.Base]):
        """
        Checks if the number of stanzas sent are the same as the
        number of stanzas received by the server. Pops stanzas that were
        handled by the server from the queue.
        """
        count_server = stanza.get('h')
        if count_server is None:
            self._log.error('Server did not send h attribute')
            return

        count_server = int(count_server)
        diff = self._out_h - count_server
        queue_size = len(queue)
        if diff < 0:
            self._log.error(
                'Mismatch detected, our h: %d, server h: %d, queue: %d',
                self._out_h, count_server, queue_size)
            # Don't accumulate all messages in this case
            # (they would otherwise all be resent on the next reconnect)
            queue = []

        elif queue_size < diff:
            self._log.error(
                'Mismatch detected, our h: %d, server h: %d, queue: %d',
                self._out_h, count_server, queue_size)
        else:
            self._log.debug('Validate ack, our h: %d, server h: %d, queue: %d',
                            self._out_h, count_server, queue_size)
            self._log.debug('Removing %d stanzas from queue', queue_size - diff)

            while len(queue) > diff:
                queue.pop(0)

    def _on_failed(self,
                   _client: Client,
                   stanza: types.Base,
                   _properties: Any):
        '''
        This can be called after 'enable' and 'resume'
        '''

        self._log.info('Negotiation failed')
        error_text = stanza.find_tag_text('text')
        if error_text is not None:
            self._log.info(error_text)

        if stanza.find_tag('item-not-found') is not None:
            self._log.info('Session timed out, last server h: %s',
                           stanza.get('h'))
            self._validate_ack(stanza, self._old_uqueue)
        else:
            for tag in stanza.get_children():
                if tag.localname != 'text':
                    self._log.info(tag.localname)

        if self.resume_in_progress:
            # Reset state before sending Bind, because otherwise stanza
            # will be counted and ack will be requested.
            # _reset_state() also resets resume_in_progress
            self._reset_state()
            self._client.set_state(StreamState.RESUME_FAILED)

        self._reset_state()

    def _reset_state(self):
        # Reset all values to default
        self._out_h = 0
        self._in_h = 0
        self._acked_h = 0

        self._uqueue = []
        self._old_uqueue = []

        self.enabled = False
        self._enable_sent = False
        self.resumed = False
        self.resume_in_progress = False
        self.resume_supported = False

        self._session_id = None
        self._location = None
        self._enable_sent = False
