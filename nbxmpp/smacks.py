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

import time
import logging

from nbxmpp.protocol import NS_STREAM_MGMT
from nbxmpp.protocol import NS_DELAY2
from nbxmpp.simplexml import Node
from nbxmpp.transports_nb import DISCONNECTING
from nbxmpp.plugin import PlugIn
from nbxmpp.const import Realm
from nbxmpp.const import Event


log = logging.getLogger('nbxmpp.smacks')


class Smacks(PlugIn):
    """
    This is Smacks is the Stream Management class. It takes care of requesting
    and sending acks. Also, it keeps track of the unhandled outgoing stanzas.

    The dispatcher has to be able to access this class to increment the
    number of handled stanzas
    """

    def __init__(self):
        PlugIn.__init__(self)
        self._out_h = 0  # Outgoing stanzas handled
        self._in_h = 0  # Incoming stanzas handled
        self._acked_h = 0  # Last acked stanza

        self._uqueue = []  # Unhandled stanzas queue
        self._old_uqueue = []  # Unhandled stanzas queue of the last session

        # Max number of stanzas in queue before making a request
        self.max_queue = 0

        self.enabled = False  # If SM is enabled
        self._enable_sent = False  # If we sent 'enable'
        self.resumed = False  # If the session was resumed
        self.resume_in_progress = False
        self.resume_supported = False  # Does the session support resume
        self._resume_jid = None  # The JID from the previous session

        self._session_id = None
        self._location = None

    def get_resume_data(self):
        if self.resume_supported:
            return {
                'out': self._out_h,
                'in': self._in_h,
                'session_id': self._session_id,
                'location': self._location,
                'uqueue': self._uqueue,
                'bound_jid': self._owner._registered_name
            }

    def set_resume_data(self, data):
        if data is None:
            return
        log.debug('Resume data set')
        self._out_h = data.get('out')
        self._in_h = data.get('in')
        self._session_id = data.get('session_id')
        self._location = data.get('location')
        self._old_uqueue = data.get('uqueue')
        self._resume_jid = data.get('bound_jid')
        self.resume_supported = True

    def register_handlers(self):
        self._owner.Dispatcher.RegisterNamespace(NS_STREAM_MGMT)
        self._owner.Dispatcher.RegisterHandler(
            'enabled', self._on_enabled, xmlns=NS_STREAM_MGMT)
        self._owner.Dispatcher.RegisterHandler(
            'r', self._send_ack, xmlns=NS_STREAM_MGMT)
        self._owner.Dispatcher.RegisterHandler(
            'a', self._on_ack, xmlns=NS_STREAM_MGMT)
        self._owner.Dispatcher.RegisterHandler(
            'resumed', self._on_resumed, xmlns=NS_STREAM_MGMT)
        self._owner.Dispatcher.RegisterHandler(
            'failed', self._on_failed, xmlns=NS_STREAM_MGMT)

    def send_enable(self):
        enable = Node(NS_STREAM_MGMT + ' enable', attrs={'resume': 'true'})
        self._owner.Connection.send(enable, now=False)
        log.debug('Send enable')
        self._enable_sent = True

    def _on_enabled(self, _disp, stanza):
        if self.enabled:
            log.error('Received "enabled", but SM is already enabled')
            return
        resume = stanza.getAttr('resume')
        if resume in ('true', 'True', '1'):
            self.resume_supported = True
            self._session_id = stanza.getAttr('id')

        self._location = stanza.getAttr('location')
        self.enabled = True
        log.info('Received enabled, location: %s, resume supported: %s, '
                 'session-id: %s', self._location, resume, self._session_id)

    def count_incoming(self, name):
        if not self.enabled:
            # Dont count while we didnt receive 'enabled'
            return
        if name in ('a', 'r', 'resumed', 'enabled'):
            return
        log.debug('IN, %s', name)
        self._in_h += 1

    def save_in_queue(self, stanza):
        if not self._enable_sent and not self.resumed:
            # We did not yet sent 'enable' so the server
            # will not count our stanzas
            return
        if (stanza.getName() == 'message' and
                stanza.getType() in ('chat', 'groupchat')):
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            attrs = {'stamp': timestamp}
            if stanza.getType() != 'groupchat':
                # Dont leak our JID to Groupchats
                attrs['from'] = stanza.getAttr('from')
            stanza.addChild('delay', namespace=NS_DELAY2, attrs=attrs)
        self._uqueue.append(stanza)
        log.debug('OUT, %s', stanza.getName())
        self._out_h += 1

        if len(self._uqueue) > self.max_queue:
            self._request_ack()
        # Send an ack after 100 unacked messages
        if (self._in_h - self._acked_h) > 100:
            self._send_ack()

    def _resend_queue(self):
        """
        Resends unsent stanzas when a new session is established.
        This way there won't be any lost outgoing messages even on failed
        smacks resumes (but message duplicates are possible).
        """
        if not self._old_uqueue:
            return
        log.info('Resend %s stanzas', len(self._old_uqueue))
        for stanza in self._old_uqueue:
            # Use dispatcher so we increment the counter
            self._owner.Dispatcher.send(stanza)
        self._old_uqueue = []

    def resume_request(self):
        if self._session_id is None:
            log.error('Attempted to resume without a valid session id')
            return

        # Save old messages in an extra "queue" to avoid race conditions
        # and to make it possible to replay stanzas even when resuming fails
        # Add messages here (instead of overwriting) so that repeated
        # connection errors don't delete unacked stanzas
        # (uqueue should be empty in this case anyways)
        self._old_uqueue += self._uqueue
        self._uqueue = []

        resume = Node(NS_STREAM_MGMT + ' resume',
                      attrs={'h': self._in_h, 'previd': self._session_id})

        self._acked_h = self._in_h
        self.resume_in_progress = True
        self._owner.Connection.send(resume, now=False)

    def _on_resumed(self, _disp, stanza):
        """
        Checks if the number of stanzas sent are the same as the
        number of stanzas received by the server. Resends stanzas not received
        by the server in the last session.
        """
        log.info('Session resumption succeeded, session-id: %s',
                 self._session_id)
        self._validate_ack(stanza, self._old_uqueue)
        # Set our out h to the h we received
        self._out_h = int(stanza.getAttr('h'))
        self.enabled = True
        self.resumed = True
        self.resume_in_progress = False
        self._owner.set_bound_jid(self._resume_jid)
        self._owner.Dispatcher.Event(Realm.CONNECTING, Event.RESUME_SUCCESSFUL)
        self._resend_queue()

    def _send_ack(self, *args):
        ack = Node(NS_STREAM_MGMT + ' a', attrs={'h': self._in_h})
        self._acked_h = self._in_h
        log.debug('Send ack, h: %s', self._in_h)
        self._owner.Connection.send(ack, now=False)

    def send_closing_ack(self):
        if self._owner.Connection.get_state() != DISCONNECTING:
            return
        ack = Node(NS_STREAM_MGMT + ' a', attrs={'h': self._in_h})
        log.debug('Send closing ack, h: %s', self._in_h)
        self._owner.Connection.send(ack, now=True)

    def _request_ack(self):
        request = Node(NS_STREAM_MGMT + ' r')
        log.debug('Request ack')
        self._owner.Connection.send(request, now=False)

    def _on_ack(self, _disp, stanza):
        log.debug('Ack received, h: %s', stanza.getAttr('h'))
        self._validate_ack(stanza, self._uqueue)

    def _validate_ack(self, stanza, queue):
        """
        Checks if the number of stanzas sent are the same as the
        number of stanzas received by the server. Pops stanzas that were
        handled by the server from the queue.
        """
        count_server = stanza.getAttr('h')
        if count_server is None:
            log.error('Server did not send h attribute')
            return

        count_server = int(count_server)
        diff = self._out_h - count_server
        queue_size = len(queue)
        if diff < 0:
            log.error('Mismatch detected, our h: %d, server h: %d, queue: %d',
                      self._out_h, count_server, queue_size)
            # Don't accumulate all messages in this case
            # (they would otherwise all be resent on the next reconnect)
            queue = []

        elif queue_size < diff:
            log.error('Mismatch detected, our h: %d, server h: %d, queue: %d',
                      self._out_h, count_server, queue_size)
        else:
            log.debug('Validate ack, our h: %d, server h: %d, queue: %d',
                      self._out_h, count_server, queue_size)
            log.debug('removing %d stanzas from queue', queue_size - diff)

            while len(queue) > diff:
                queue.pop(0)

    def _on_failed(self, _disp, stanza):
        '''
        This can be called after 'enable' and 'resume'
        '''

        log.info('Stream Management negotiation failed')
        error_text = stanza.getTagData('text')
        if error_text is not None:
            log.info(error_text)

        if stanza.getTag('item-not-found') is not None:
            log.info('Session timed out, last server h: %s',
                     stanza.getAttr('h'))
            self._validate_ack(stanza, self._old_uqueue)
        else:
            for tag in stanza.getTags():
                if tag.getName() != 'text':
                    log.info(tag.getName())

        if self.resume_in_progress:
            self._owner.Dispatcher.Event(Realm.CONNECTING, Event.RESUME_FAILED)
            # We failed while resuming
            self.resume_supported = False
            self._owner.bind()
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
