# Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
# Copyright (C)           Dimitur Kirov <dkirov AT gmail.com>
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

import logging

from nbxmpp.plugin import PlugIn
from nbxmpp.protocol import NS_BIND
from nbxmpp.protocol import NS_SESSION
from nbxmpp.protocol import NS_STREAMS
from nbxmpp.protocol import NS_STREAM_MGMT
from nbxmpp.protocol import Node
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import Protocol
from nbxmpp.const import Realm
from nbxmpp.const import Event

log = logging.getLogger('nbxmpp.bind')


class NonBlockingBind(PlugIn):
    """
    Bind some JID to the current connection to allow router know of our
    location. Must be plugged after successful SASL auth
    """

    def __init__(self):
        PlugIn.__init__(self)
        self._session_required = False

    def plugin(self, _owner):
        self._owner.RegisterHandler(
            'features', self._on_features, xmlns=NS_STREAMS)

        feats = self._owner.Dispatcher.Stream.features
        if feats is not None:
            if feats.getTag('bind', namespace=NS_BIND) is not None:
                # We already received the features
                self._on_features(None, feats)

    def _on_features(self, _con, feats):
        """
        Determine if server supports resource binding and set some internal
        attributes accordingly.
        """
        if not feats or not feats.getTag('bind', namespace=NS_BIND):
            return

        session = feats.getTag('session', namespace=NS_SESSION)
        if session is not None:
            if session.getTag('optional') is None:
                self._session_required = True

        self._bind()

    def plugout(self):
        """
        Remove Bind handler from owner's dispatcher. Used internally
        """
        self._owner.UnregisterHandler(
            'features', self._on_features, xmlns=NS_STREAMS)

    def _bind(self):
        """
        Perform binding. Use provided resource name or random (if not provided).
        """
        log.info('Send bind')
        resource = []
        if self._owner._Resource:
            resource = [Node('resource', payload=[self._owner._Resource])]

        payload = Node('bind', attrs={'xmlns': NS_BIND}, payload=resource)
        node = Protocol('iq', typ='set', payload=[payload])

        self._owner.Dispatcher.SendAndCallForResponse(node, func=self._on_bind)

    def _on_bind(self, _client, stanza):
        if isResultNode(stanza):
            bind = stanza.getTag('bind')
            if bind is not None:
                jid = bind.getTagData('jid')
                log.info('Successfully bound %s', jid)
                self._owner.set_bound_jid(jid)

                if not self._session_required:
                    # Server don't want us to initialize a session
                    log.info('No session required')
                    self._on_bind_successful()
                else:
                    node = Node('session', attrs={'xmlns':NS_SESSION})
                    iq = Protocol('iq', typ='set', payload=[node])
                    self._owner.SendAndCallForResponse(
                        iq, func=self._on_session)
                return
        if stanza:
            log.error('Binding failed: %s.', stanza.getTag('error'))
        else:
            log.error('Binding failed: timeout expired')
        self._owner.Connection.start_disconnect()
        self._owner.Dispatcher.Event(Realm.CONNECTING, Event.BIND_FAILED)
        self.PlugOut()

    def _on_session(self, _client, stanza):
        if isResultNode(stanza):
            log.info('Successfully started session')
            self._on_bind_successful()
        else:
            log.error('Session open failed')
            self._owner.Connection.start_disconnect()
            self._owner.Dispatcher.Event(Realm.CONNECTING, Event.SESSION_FAILED)
            self.PlugOut()

    def _on_bind_successful(self):
        feats = self._owner.Dispatcher.Stream.features
        if feats.getTag('sm', namespace=NS_STREAM_MGMT):
            self._owner.Smacks.send_enable()
        self._owner.Dispatcher.Event(Realm.CONNECTING, Event.CONNECTION_ACTIVE)
        self.PlugOut()
