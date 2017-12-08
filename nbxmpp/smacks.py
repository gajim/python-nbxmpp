from .protocol import Acks
from .protocol import NS_STREAM_MGMT
from .transports_nb import CONNECTED, CONNECTING, DISCONNECTED, DISCONNECTING
import logging
log = logging.getLogger('nbxmpp.smacks')


class Smacks(object):
    """
    This is Smacks is the Stream Management class. It takes care of requesting
    and sending acks. Also, it keeps track of the unhandled outgoing stanzas.

    The dispatcher has to be able to access this class to increment the
    number of handled stanzas
    """

    def __init__(self, con):
        self.con = con # Connection object
        self.out_h = 0 # Outgoing stanzas handled
        self.in_h = 0  # Incoming stanzas handled
        self.last_sent_in_h = 0 # Last acked stanza.
        self.uqueue = [] # Unhandled stanzas queue
        self.old_uqueue = [] # Unhandled stanzas queue of the last session
        self.session_id = None
        self.resumption = False # If server supports resume
        # Max number of stanzas in queue before making a request
        #be more agressive here (every message must be acked), this creates fewer message duplicates on failed resume)
        self.max_queue = 0
        self._owner = None
        self.resuming = False
        self.enabled = False # If SM is enabled
        self.location = None
        self.failed_resume = False # If last resuming attempt failed
        self.supports_sm = False # If server supports sm

    def set_owner(self, owner):
        self._owner = owner
        # Register handlers
        owner.Dispatcher.RegisterNamespace(NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('enabled', self._neg_response,
            xmlns=NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('r', self.send_ack,
            xmlns=NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('a', self.check_ack,
            xmlns=NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('resumed', self.check_resume,
            xmlns=NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('failed', self.error_handling,
            xmlns=NS_STREAM_MGMT)

    def _neg_response(self, disp, stanza):
        r = stanza.getAttr('resume')
        log.info("Session resumption: %s" % r)
        if r == 'true' or r == 'True' or r == '1':
            self.resumption = True
            self.session_id = stanza.getAttr('id')
        if r == 'false' or r == 'False' or r == '0':
            self.negociate(False)
        l = stanza.getAttr('location')
        if l:
            self.location = l
        if self.failed_resume:
            self.con._discover_server_at_connection(self.con.connection)
            self.failed_resume = False

    def negociate(self, resume=True):
        # Every time we attempt to negociate, we must erase all previous info
        # about any previous session
        log.debug("Clearing smacks uqueue")
        self.uqueue = []
        self.in_h = 0
        self.last_sent_in_h = 0
        self.out_h = 0
        self.session_id = None
        self.enabled = True

        stanza = Acks()
        stanza.buildEnable(resume)
        self._owner.Connection.send(stanza, now=True)

    def resend_queue(self):
        """
        Resends unsent stanzas when a new session is established.
        This way there won't be any lost outgoing messages even on failed smacks resumes (but message duplicates are possible).
        If your server supports revision 1.5 of smacks then even message duplicates are eliminated here :)
        """
        if self.old_uqueue:
            log.info('Session resumption failed, replaying %s stanzas anyways...' % len(self.old_uqueue))
            for i in self.old_uqueue:
                self._owner.Dispatcher.send(i, False)   #use this send so that our stanzas actually increment out_h
            self.old_uqueue = []
        
    def resume_request(self):
        if not self.session_id:
            self.resuming = False
            log.error('Attempted to resume without a valid session id ')
            return
        #save old messages in an extra "queue" to avoid race conditions and to make it possible to replay stanzas even when resuming fails
        #add messages here (instead of overwriting) so that repeated connection errors don't delete unacked stanzas (uqueue should be empty in this case anyways)
        self.old_uqueue += self.uqueue
        self.uqueue = []
        resume = Acks()
        resume.buildResume(self.in_h, self.session_id)
        self.last_sent_in_h = self.in_h
        self._owner.Connection.send(resume, False)

    def send_ack(self, disp=None, stanza=None):
        ack = Acks()
        ack.buildAnswer(self.in_h)
        self.last_sent_in_h = self.in_h
        self._owner.Connection.send(ack, False)
    
    def send_closing_ack(self):
        if self._owner.Connection.get_state() != DISCONNECTING:
            log.error("Not allowed to send closing smacks ack when not disconnecting!")
            return
        ack = Acks()
        ack.buildAnswer(self.in_h)
        self.last_sent_in_h = self.in_h
        self._owner.Connection.send(ack, True)

    def request_ack(self):
        r = Acks()
        r.buildRequest()
        self._owner.Connection.send(r, False)

    def check_ack(self, disp, stanza):
        """
        Checks if the number of stanzas sent are the same as the
        number of stanzas received by the server. Pops stanzas that were
        handled by the server from the queue.
        """
        h = stanza.getAttr('h')
        if not h:
            log.error('Server did not send h attribute')
            return
        h = int(h)
        diff = self.out_h - h

        if diff < 0:
            log.error('Server and client number of stanzas handled mismatch (our h: %d, server h: %d, #queue: %d)' % (self.out_h, h, len(self.uqueue)))
            while (len(self.uqueue)):        #don't accumulate all messages in this case (they would otherwise all be resent on the next reconnect)
                self.uqueue.pop(0)
        elif len(self.uqueue) < diff:
            log.error('Server and client number of stanzas handled mismatch (our h: %d, server h: %d, #queue: %d)' % (self.out_h, h, len(self.uqueue)))
        else:
            log.debug('Got ack for outgoing stanzas (our h: %d, server h: %d, #queue: %d), removing %d messages from queue...' % (self.out_h, h, len(self.uqueue), len(self.uqueue) - diff))
            while (len(self.uqueue) > diff):
                self.uqueue.pop(0)
                    
    def check_resume(self, disp, stanza):
        """
        Checks if the number of stanzas sent are the same as the
        number of stanzas received by the server. Resends stanzas not received
        by the server in the last session.
        """
        log.info("Session resumption succeeded")
        h = stanza.getAttr('h')
        if not h:
            log.error('Server did not send h attribute')
            return
        h = int(h)
        diff = self.out_h - h

        if diff < 0:
            log.error('Server and client number of stanzas handled mismatch on session resumption (our h: %d, server h: %d. #queue: %d)' % (self.out_h, h, len(self.old_uqueue)))
            self.old_uqueue = []        #that's weird, but we don't resend this stanzas if the server says we don't need to
        elif len(self.old_uqueue) < diff:
            log.error('Server and client number of stanzas handled mismatch on session resumption (our h: %d, server h: %d, #queue: %d)' % (self.out_h, h, len(self.old_uqueue)))
        else:
            log.info('Removing %d already acked stanzas from old outgoing queue (our h: %d, server h: %d, #queue: %d, remaining in queue: %d)' % (len(self.old_uqueue) - diff, self.out_h, h, len(self.old_uqueue), diff))
            while (len(self.old_uqueue) > diff):
                self.old_uqueue.pop(0)

        self.enabled = True
        self.resuming = True
        self.con.set_oldst()
        if self.old_uqueue:
            log.info('Session resumed, replaying %s stanzas...' % len(self.old_uqueue))
            for i in self.old_uqueue:
                self._owner.Connection.send(i, False)
            self.old_uqueue = []

    def error_handling(self, disp, stanza):
        # If the server doesn't recognize previd, forget about resuming
        # Ask for service discovery, etc..
        if stanza.getTag('item-not-found'):
            self.resuming = False
            self.enabled = False
            # we need to bind a resource
            self._owner.NonBlockingBind.resuming = False
            self._owner._on_auth_bind(None)
            self.failed_resume = True
            
            h = stanza.getAttr('h')
            log.info('Session resumption failed (item-not-found), server h: %s' % str(h))
            if not h:
                return
            #prepare old_queue to contain only unacked stanzas for later resend (which is happening after our session is established properly)
            h = int(h)
            diff = self.out_h - h

            if diff < 0:
                log.error('Server and client number of stanzas handled mismatch on session resumption (our h: %d, server h: %d, #queue: %d)' % (self.out_h, h, len(self.old_uqueue)))
                self.old_uqueue = []        #that's weird, but we don't resend this stanzas if the server says we don't need to
            elif len(self.old_uqueue) < diff:
                log.error('Server and client number of stanzas handled mismatch on session resumption (our h: %d, server h: %d, #queue: %d)' % (self.out_h, h, len(self.old_uqueue)))
            else:
                log.info('Removing %d already acked stanzas from old outgoing queue (our h: %d, server h: %d, #queue: %d, remaining in queue: %d)' % (len(self.old_uqueue) - diff, self.out_h, h, len(self.old_uqueue), diff))
                while (len(self.old_uqueue) > diff):
                    self.old_uqueue.pop(0)
            return

        # Doesn't support resumption
        if stanza.getTag('feature-not-implemented'):
            log.info('Session resumption failed (feature-not-implemented)')
            self.negociate(False)
            return

        if stanza.getTag('unexpected-request'):
            log.error('Gajim failed to negociate Stream Management')
            self.enabled = False
            return
