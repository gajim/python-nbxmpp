##   auth_nb.py
##       based on auth.py, changes backported up to revision 1.41
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

"""
Provides plugs for SASL and NON-SASL authentication mechanisms.
Can be used both for client and transport authentication

See client_nb.py
"""

from __future__ import unicode_literals

from .protocol import NS_SASL, NS_SESSION, NS_STREAMS, NS_BIND, NS_AUTH
from .protocol import NS_STREAM_MGMT
from .protocol import Node, NodeProcessed, isResultNode, Iq, Protocol, JID
from .plugin import PlugIn
import sys
import re
import os
import binascii
import base64
from . import dispatcher_nb
import hmac
import hashlib

import logging
log = logging.getLogger('nbxmpp.auth_nb')

def HH(some): return hashlib.md5(some).hexdigest()
def H(some): return hashlib.md5(some).digest()
def C(some): return b':'.join(some)

try:
    kerberos = __import__('kerberos')
    have_kerberos = True
except ImportError:
    have_kerberos = False

GSS_STATE_STEP = 0
GSS_STATE_WRAP = 1
SASL_FAILURE_IN_PROGRESS = 'failure-in-process'
SASL_FAILURE = 'failure'
SASL_SUCCESS = 'success'
SASL_UNSUPPORTED = 'not-supported'
SASL_IN_PROCESS = 'in-process'

# compile the search regex for _challenge_splitter
_challenge_regex = re.compile("""
    (\w+)      # keyword
    =
    ("[^"]+"|[^,]+)   # value
    ,?         # optional comma separator
""", re.VERBOSE)

def _challenge_splitter(data):
    """
    Helper function that creates a dict from challenge string. Used
    for DIGEST-MD5 authentication.

    Sample challenge string:
      - username="example.org",realm="somerealm",
        nonce="OA6MG9tEQGm2hh",cnonce="OA6MHXh6VqTrRk",
        nc=00000001,qop="auth,auth-int,auth-conf",charset=utf-8

    Expected result for challan:
      - dict['qop'] = ('auth','auth-int','auth-conf')
      - dict['realm'] = 'somerealm'
    """
    dict_ = {}
    for match in _challenge_regex.finditer(data):
        k = match.group(1)
        v = match.group(2)
        if v.startswith('"'):
            v = v[1:-1] # Remove quote
        if v.find(',') >= 0:
            v = v.split(',') # Split using comma
        dict_[k] = v
    return dict_

def _scram_parse(chatter):
    """Helper function. Used for SCRAM-SHA-1, SCRAM-SHA-1-PLUS authentication"""
    return dict(s.split('=', 1) for s in chatter.split(','))

SASL_AUTHENTICATION_MECHANISMS = \
    set(['ANONYMOUS', 'EXTERNAL', 'GSSAPI', 'SCRAM-SHA-1-PLUS', 'SCRAM-SHA-1',
         'DIGEST-MD5', 'PLAIN', 'X-MESSENGER-OAUTH2'])

class SASL(PlugIn):
    """
    Implements SASL authentication. Can be plugged into NonBlockingClient
    to start authentication
    """

    def __init__(self, username, password, on_sasl, channel_binding,
                 auth_mechs):
        """
        :param username: XMPP username
        :param password: XMPP password
        :param on_sasl: Callback, will be called after each SASL auth-step.
        :param channel_binding: TLS channel binding data, None if the
               binding data is not available
        :param auth_mechs: Set of valid authentication mechanisms.
               Possible entries are:
               'ANONYMOUS', 'EXTERNAL', 'GSSAPI', 'SCRAM-SHA-1-PLUS',
               'SCRAM-SHA-1', 'DIGEST-MD5', 'PLAIN', 'X-MESSENGER-OAUTH2'
        """
        PlugIn.__init__(self)
        self.username = username
        self.password = password
        self.on_sasl = on_sasl
        self.channel_binding = channel_binding
        self.enabled_auth_mechs = auth_mechs
        self.realm = None

    def plugin(self, owner):
        if 'version' not in self._owner.Dispatcher.Stream._document_attrs:
            self.startsasl = SASL_UNSUPPORTED
        elif self._owner.Dispatcher.Stream.features:
            try:
                self.FeaturesHandler(self._owner.Dispatcher,
                    self._owner.Dispatcher.Stream.features)
            except NodeProcessed:
                pass
        else:
            self.startsasl = None

    def plugout(self):
        """
        Remove SASL handlers from owner's dispatcher. Used internally
        """
        if 'features' in  self._owner.__dict__:
            self._owner.UnregisterHandler('features', self.FeaturesHandler,
                xmlns=NS_STREAMS)
        if 'challenge' in  self._owner.__dict__:
            self._owner.UnregisterHandler('challenge', self.SASLHandler,
                xmlns=NS_SASL)
        if 'failure' in  self._owner.__dict__:
            self._owner.UnregisterHandler('failure', self.SASLHandler,
                xmlns=NS_SASL)
        if 'success' in  self._owner.__dict__:
            self._owner.UnregisterHandler('success', self.SASLHandler,
                xmlns=NS_SASL)

    def auth(self):
        """
        Start authentication. Result can be obtained via "SASL.startsasl"
        attribute and will be either SASL_SUCCESS or SASL_FAILURE

        Note that successful auth will take at least two Dispatcher.Process()
        calls.
        """
        if self.startsasl:
            pass
        elif self._owner.Dispatcher.Stream.features:
            try:
                self.FeaturesHandler(self._owner.Dispatcher,
                    self._owner.Dispatcher.Stream.features)
            except NodeProcessed:
                pass
        else:
            self._owner.RegisterHandler('features',
                self.FeaturesHandler, xmlns=NS_STREAMS)

    def FeaturesHandler(self, conn, feats):
        """
        Used to determine if server supports SASL auth. Used internally
        """
        if not feats.getTag('mechanisms', namespace=NS_SASL):
            self.startsasl='not-supported'
            log.info('SASL not supported by server')
            return

        self.mecs = set(
            mec.getData()
            for mec
            in feats.getTag('mechanisms', namespace=NS_SASL).getTags('mechanism')
        ) & self.enabled_auth_mechs

        # Password based authentication mechanism ordered by strength.
        # If the server supports a mechanism disable all weaker mechanisms.
        password_auth_mechs_strength = ['SCRAM-SHA-1-PLUS', 'SCRAM-SHA-1',
            'DIGEST-MD5', 'PLAIN', 'X-MESSENGER-OAUTH2']
        if self.channel_binding is None:
            password_auth_mechs_strength.remove('SCRAM-SHA-1-PLUS')
        for i in range(0, len(password_auth_mechs_strength)):
            if password_auth_mechs_strength[i] in self.mecs:
                for m in password_auth_mechs_strength[i + 1:]:
                    self.mecs.discard(m)
                break

        self._owner.RegisterHandler('challenge', self.SASLHandler,
            xmlns=NS_SASL)
        self._owner.RegisterHandler('failure', self.SASLHandler, xmlns=NS_SASL)
        self._owner.RegisterHandler('success', self.SASLHandler, xmlns=NS_SASL)
        self.MechanismHandler()

    def MechanismHandler(self):
        if 'ANONYMOUS' in self.mecs and self.username is None:
            self.mecs.remove('ANONYMOUS')
            node = Node('auth', attrs={'xmlns': NS_SASL,
                'mechanism': 'ANONYMOUS'})
            self.mechanism = 'ANONYMOUS'
            self.startsasl = SASL_IN_PROCESS
            self._owner.send(str(node))
            raise NodeProcessed
        if "EXTERNAL" in self.mecs:
            self.mecs.remove('EXTERNAL')
            sasl_data = '%s@%s' % (self.username, self._owner.Server)
            sasl_data = base64.b64encode(sasl_data.encode('utf-8')).decode(
                'utf-8').replace('\n', '')
            node = Node('auth', attrs={'xmlns': NS_SASL,
                'mechanism': 'EXTERNAL'}, payload=[sasl_data])
            self.mechanism = 'EXTERNAL'
            self.startsasl = SASL_IN_PROCESS
            self._owner.send(str(node))
            raise NodeProcessed
        if 'GSSAPI' in self.mecs and have_kerberos:
            self.mecs.remove('GSSAPI')
            try:
                self.gss_vc = kerberos.authGSSClientInit('xmpp@' + \
                    self._owner.xmpp_hostname)[1]
                kerberos.authGSSClientStep(self.gss_vc, '')
                response = kerberos.authGSSClientResponse(self.gss_vc)
                node=Node('auth', attrs={'xmlns': NS_SASL,
                    'mechanism': 'GSSAPI'}, payload=(response or ''))
                self.mechanism = 'GSSAPI'
                self.gss_step = GSS_STATE_STEP
                self.startsasl = SASL_IN_PROCESS
                self._owner.send(str(node))
                raise NodeProcessed
            except kerberos.GSSError as e:
                log.info('GSSAPI authentication failed: %s' % str(e))
        if 'SCRAM-SHA-1-PLUS' in self.mecs and self.channel_binding is not None:
            self.mecs.remove('SCRAM-SHA-1-PLUS')
            self.mechanism = 'SCRAM-SHA-1-PLUS'
            self._owner._caller.get_password(self.set_password, self.mechanism)
            self.scram_step = 0
            self.startsasl = SASL_IN_PROCESS
            raise NodeProcessed
        if 'SCRAM-SHA-1' in self.mecs:
            self.mecs.remove('SCRAM-SHA-1')
            self.mechanism = 'SCRAM-SHA-1'
            self._owner._caller.get_password(self.set_password, self.mechanism)
            self.scram_step = 0
            self.startsasl = SASL_IN_PROCESS
            raise NodeProcessed
        if 'DIGEST-MD5' in self.mecs:
            self.mecs.remove('DIGEST-MD5')
            node = Node('auth', attrs={'xmlns': NS_SASL,
                'mechanism': 'DIGEST-MD5'})
            self.mechanism = 'DIGEST-MD5'
            self.startsasl = SASL_IN_PROCESS
            self._owner.send(str(node))
            raise NodeProcessed
        if 'PLAIN' in self.mecs:
            self.mecs.remove('PLAIN')
            self.mechanism = 'PLAIN'
            self._owner._caller.get_password(self.set_password, self.mechanism)
            self.startsasl = SASL_IN_PROCESS
            raise NodeProcessed
        if 'X-MESSENGER-OAUTH2' in self.mecs:
            self.mecs.remove('X-MESSENGER-OAUTH2')
            self.mechanism = 'X-MESSENGER-OAUTH2'
            self._owner._caller.get_password(self.set_password, self.mechanism)
            self.startsasl = SASL_IN_PROCESS
            raise NodeProcessed
        self.startsasl = SASL_FAILURE
        log.info('I can only use ANONYMOUS, EXTERNAL, GSSAPI, SCRAM-SHA-1-PLUS,'
                 ' SCRAM-SHA-1, DIGEST-MD5, PLAIN and X-MESSENGER-OAUTH2'
                 ' mechanisms.')
        if self.on_sasl:
            self.on_sasl()
        return

    def SASLHandler(self, conn, challenge):
        """
        Perform next SASL auth step. Used internally
        """
        if challenge.getNamespace() != NS_SASL:
            return

        def scram_base64(s):
            try:
                s = s.encode('utf-8')
            except:
                pass
            return ''.join(base64.b64encode(s).decode('utf-8').\
                split('\n'))

        incoming_data = challenge.getData()
        data=base64.b64decode(incoming_data.encode('utf-8'))

        if self.mechanism != 'GSSAPI':
            data=data.decode('utf-8')

        ### Handle Auth result
        def on_auth_fail(reason):
            log.info('Failed SASL authentification: %s' % reason)
            self._owner.send(str(Node('abort', attrs={'xmlns': NS_SASL})))
            if len(self.mecs) > 0:
                # There are other mechanisms to test, but wait for <failure>
                # answer from server
                self.startsasl = SASL_FAILURE_IN_PROGRESS
                raise NodeProcessed
            if self.on_sasl:
                self.on_sasl()
            raise NodeProcessed

        if challenge.getName() == 'failure':
            if self.startsasl == SASL_FAILURE_IN_PROGRESS:
                self.MechanismHandler()
                raise NodeProcessed
            self.startsasl = SASL_FAILURE
            try:
                reason = challenge.getChildren()[0]
            except Exception:
                reason = challenge
            on_auth_fail(reason)
        elif challenge.getName() == 'success':
            if self.mechanism in ('SCRAM-SHA-1', 'SCRAM-SHA-1-PLUS'):
                # check data-with-success
                data = _scram_parse(data)
                if data['v'] != scram_base64(self.scram_ServerSignature):
                    on_auth_fail('ServerSignature is wrong')

            self.startsasl = SASL_SUCCESS
            log.info('Successfully authenticated with remote server.')
            handlers = self._owner.Dispatcher.dumpHandlers()

            # Bosh specific dispatcher replugging
            # save old features. They will be used in case we won't get response
            # on stream restart after SASL auth (happens with XMPP over BOSH
            # with Openfire)
            old_features = self._owner.Dispatcher.Stream.features
            self._owner.Dispatcher.PlugOut()
            dispatcher_nb.Dispatcher.get_instance().PlugIn(self._owner,
                after_SASL=True, old_features=old_features)
            self._owner.Dispatcher.restoreHandlers(handlers)
            self._owner.User = self.username

            if self.on_sasl:
                self.on_sasl()
            raise NodeProcessed

        ### Perform auth step
        if self.mechanism != 'GSSAPI':
            log.info('Got challenge:' + data)
        else:
            log.info('Got challenge')

        if self.mechanism == 'GSSAPI':
            if self.gss_step == GSS_STATE_STEP:
                rc = kerberos.authGSSClientStep(self.gss_vc, incoming_data)
                if rc != kerberos.AUTH_GSS_CONTINUE:
                    self.gss_step = GSS_STATE_WRAP
            elif self.gss_step == GSS_STATE_WRAP:
                rc = kerberos.authGSSClientUnwrap(self.gss_vc, incoming_data)
                response = kerberos.authGSSClientResponse(self.gss_vc)
                rc = kerberos.authGSSClientWrap(self.gss_vc, response,
                    kerberos.authGSSClientUserName(self.gss_vc))
            response = kerberos.authGSSClientResponse(self.gss_vc)
            if not response:
                response = ''
            self._owner.send(Node('response', attrs={'xmlns': NS_SASL},
                payload=response).__str__())
            raise NodeProcessed
        if self.mechanism in ('SCRAM-SHA-1', 'SCRAM-SHA-1-PLUS'):
            hashfn = hashlib.sha1

            def HMAC(k, s):
                return hmac.new(key=k, msg=s, digestmod=hashfn).digest()

            if sys.version_info[0] == 2:
                def XOR(x, y):
                    r = (chr(ord(px) ^ ord(py)) for px, py in zip(x, y))
                    return bytes(b''.join(r))
            else:
                def XOR(x, y):
                    r = [px ^ py for px, py in zip(x, y)]
                    return bytes(r)

            def Hi(s, salt, iters):
                ii = 1
                try:
                    s = s.encode('utf-8')
                except:
                    pass
                ui_1 = HMAC(s, salt + b'\0\0\0\01')
                ui = ui_1
                for i in range(iters - 1):
                    ii += 1
                    ui_1 = HMAC(s, ui_1)
                    ui = XOR(ui, ui_1)
                return ui

            def scram_H(s):
                return hashfn(s).digest()

            if self.scram_step == 0:
                self.scram_step = 1
                self.scram_soup += ',' + data + ','
                data = _scram_parse(data)
                # Check server nonce here.
                # The first part of server nonce muss be the nonce send by client.
                if (data['r'][:len(self.client_nonce)] != self.client_nonce):
                    on_auth_fail('Server nonce is incorrect')
                    raise NodeProcessed
                if self.mechanism == 'SCRAM-SHA-1':
                    r = 'c=' + scram_base64(self.scram_gs2)
                else:
                    # Channel binding data goes in here too.
                    r = 'c=' + scram_base64(self.scram_gs2.encode('utf-8')
                        + self.channel_binding)
                r += ',r=' + data['r']
                self.scram_soup += r
                self.scram_soup = self.scram_soup.encode('utf-8')
                salt = base64.b64decode(data['s'].encode('utf-8'))
                iter = int(data['i'])
                SaltedPassword = Hi(self.password, salt, iter)
                # TODO: Could cache this, along with salt+iter.
                ClientKey = HMAC(SaltedPassword, b'Client Key')
                StoredKey = scram_H(ClientKey)
                ClientSignature = HMAC(StoredKey, self.scram_soup)
                ClientProof = XOR(ClientKey, ClientSignature)
                r += ',p=' + scram_base64(ClientProof)
                ServerKey = HMAC(SaltedPassword, b'Server Key')
                self.scram_ServerSignature = HMAC(ServerKey, self.scram_soup)
                sasl_data = scram_base64(r)
                node = Node('response', attrs={'xmlns': NS_SASL},
                    payload=[sasl_data])
                self._owner.send(str(node))
                raise NodeProcessed

            if self.scram_step == 1:
                data = _scram_parse(data)
                if base64.b64decode(data['v'].encode('utf-8')).decode('utf-8') \
                != self.scram_ServerSignature:
                    # TODO: Not clear what to do here - need to abort.
                    raise Exception
                node = Node('response', attrs={'xmlns': NS_SASL});
                self._owner.send(str(node))
                raise NodeProcessed

        # DIGEST-MD5
        # magic foo...
        chal = _challenge_splitter(data)
        if not self.realm and 'realm' in chal:
            self.realm = chal['realm']
        if 'qop' in chal and ((chal['qop'] =='auth') or \
        (isinstance(chal['qop'], list) and 'auth' in chal['qop'])):
            self.resp = {'username': self.username,
                'nonce': chal['nonce'],
                'cnonce': '%x' % int(binascii.hexlify(os.urandom(24)), 16),
                'nc': ('00000001'),  # ToDo: Is this a tupel or only a string?
                'qop': 'auth',
                'digest-uri': 'xmpp/' + self._owner.Server,
                'charset': 'utf-8'
            }
            if self.realm:
                self.resp['realm'] = self.realm
            else:
                self.resp['realm'] = self._owner.Server
            # Password is now required
            self._owner._caller.get_password(self.set_password, self.mechanism)
        elif 'rspauth' in chal:
            # Check rspauth value
            if chal['rspauth'] != self.digest_rspauth:
                on_auth_fail('rspauth is wrong')
            self._owner.send(str(Node('response', attrs={'xmlns':NS_SASL})))
        else:
            self.startsasl = SASL_FAILURE
            log.info('Failed SASL authentification: unknown challenge')
        if self.on_sasl:
            self.on_sasl()
        raise NodeProcessed

    @staticmethod
    def _convert_to_iso88591(string):
        try:
            string = string.encode('iso-8859-1')
        except UnicodeEncodeError:
            pass
        return string

    def set_password(self, password):
        self.password = '' if password is None else password
        if self.mechanism in ('SCRAM-SHA-1', 'SCRAM-SHA-1-PLUS'):
            self.client_nonce = '%x' % int(binascii.hexlify(os.urandom(24)), 16)
            self.scram_soup = 'n=' + self.username + ',r=' + self.client_nonce
            if self.mechanism == 'SCRAM-SHA-1':
                if self.channel_binding is None:
                    # Client doesn't support Channel Binding
                    self.scram_gs2 = 'n,,' # No CB yet.
                else:
                    # Client supports CB, but server doesn't support CB
                    self.scram_gs2 = 'y,,'
            else:
                self.scram_gs2 = 'p=tls-unique,,'
            sasl_data = base64.b64encode((self.scram_gs2 + self.scram_soup).\
                encode('utf-8')).decode('utf-8').replace('\n', '')
            node = Node('auth', attrs={'xmlns': NS_SASL,
                'mechanism': self.mechanism}, payload=[sasl_data])
        elif self.mechanism == 'DIGEST-MD5':
            hash_username = self._convert_to_iso88591(self.resp['username'])
            hash_realm = self._convert_to_iso88591(self.resp['realm'])
            hash_password = self._convert_to_iso88591(self.password)
            A1 = C([H(C([hash_username, hash_realm, hash_password])),
                self.resp['nonce'].encode('utf-8'), self.resp['cnonce'].encode(
                'utf-8')])
            A2 = C([b'AUTHENTICATE', self.resp['digest-uri'].encode('utf-8')])
            response = HH(C([HH(A1).encode('utf-8'), self.resp['nonce'].encode(
                'utf-8'), self.resp['nc'].encode('utf-8'), self.resp['cnonce'].\
                encode('utf-8'), self.resp['qop'].encode('utf-8'), HH(A2).\
                encode('utf-8')]))
            A2 = C([b'', self.resp['digest-uri'].encode('utf-8')])
            self.digest_rspauth = HH(C([HH(A1).encode('utf-8'), self.resp[
                'nonce'].encode('utf-8'), self.resp['nc'].encode('utf-8'),
                self.resp['cnonce'].encode('utf-8'), self.resp['qop'].encode(
                'utf-8'), HH(A2).encode('utf-8')]))
            self.resp['response'] = response
            sasl_data = ''
            for key in ('charset', 'username', 'realm', 'nonce', 'nc', 'cnonce',
            'digest-uri', 'response', 'qop'):
                if key in ('nc', 'qop', 'response', 'charset'):
                    sasl_data += "%s=%s," % (key, self.resp[key])
                else:
                    sasl_data += '%s="%s",' % (key, self.resp[key])
            sasl_data = base64.b64encode(sasl_data[:-1].encode('utf-8')).\
                decode('utf-8').replace('\r', '').replace('\n', '')
            node = Node('response', attrs={'xmlns': NS_SASL},
                payload=[sasl_data])
        elif self.mechanism == 'PLAIN':
            sasl_data = '\x00%s\x00%s' % (self.username, self.password)
            sasl_data = base64.b64encode(sasl_data.encode('utf-8')).decode(
                'utf-8').replace('\n', '')
            node = Node('auth', attrs={'xmlns': NS_SASL, 'mechanism': 'PLAIN'},
                payload=[sasl_data])
        elif self.mechanism == 'X-MESSENGER-OAUTH2':
            node = Node('auth', attrs={'xmlns': NS_SASL,
                'mechanism': 'X-MESSENGER-OAUTH2'})
            node.addData(password)
        self._owner.send(str(node))


class NonBlockingNonSASL(PlugIn):
    """
    Implements old Non-SASL (XEP-0078) authentication used in jabberd1.4 and
    transport authentication
    """

    def __init__(self, user, password, resource, on_auth):
        """
        Caches username, password and resource for auth
        """
        PlugIn.__init__(self)
        self.user = user
        if password is None:
            self.password = ''
        else:
            self.password = password
        self.resource = resource
        self.on_auth = on_auth

    def plugin(self, owner):
        """
        Determine the best auth method (digest/0k/plain) and use it for auth.
        Returns used method name on success. Used internally
        """
        log.info('Querying server about possible auth methods')
        self.owner = owner

        owner.Dispatcher.SendAndWaitForResponse(
            Iq('get', NS_AUTH, payload=[Node('username', payload=[self.user])]),
            func=self._on_username)

    def _on_username(self, resp):
        if not isResultNode(resp):
            log.info('No result node arrived! Aborting...')
            return self.on_auth(None)

        iq=Iq(typ='set', node=resp)
        query = iq.getTag('query')
        query.setTagData('username', self.user)
        query.setTagData('resource', self.resource)

        if query.getTag('digest'):
            log.info("Performing digest authentication")
            query.setTagData('digest',
                hashlib.sha1(self.owner.Dispatcher.Stream._document_attrs['id']
                + self.password).hexdigest())
            if query.getTag('password'):
                query.delChild('password')
            self._method = 'digest'
        elif query.getTag('token'):
            token = query.getTagData('token')
            seq = query.getTagData('sequence')
            log.info("Performing zero-k authentication")

            def hasher(s):
                return hashlib.sha1(s).hexdigest()

            def hash_n_times(s, count):
                return count and hasher(hash_n_times(s, count-1)) or s

            hash_ = hash_n_times(hasher(hasher(self.password) + token),
                int(seq))
            query.setTagData('hash', hash_)
            self._method='0k'
        else:
            log.warning("Secure methods unsupported, performing plain text \
                authentication")
            self._method = 'plain'
            self._owner._caller.get_password(self._on_password, self._method)
            return
        resp = self.owner.Dispatcher.SendAndWaitForResponse(iq,
            func=self._on_auth)

    def _on_password(self, password):
        self.password = '' if password is None else password
        iq=Iq('set', NS_AUTH)
        query = iq.getTag('query')
        query.setTagData('username', self.user)
        query.setTagData('resource', self.resource)
        query.setTagData('password', self.password)
        resp = self.owner.Dispatcher.SendAndWaitForResponse(iq,
            func=self._on_auth)

    def _on_auth(self, resp):
        if isResultNode(resp):
            log.info('Sucessfully authenticated with remote host.')
            self.owner.User = self.user
            self.owner.Resource = self.resource
            self.owner._registered_name = self.owner.User + '@' + \
                self.owner.Server+ '/' + self.owner.Resource
            return self.on_auth(self._method)
        log.info('Authentication failed!')
        return self.on_auth(None)


class NonBlockingBind(PlugIn):
    """
    Bind some JID to the current connection to allow router know of our
    location. Must be plugged after successful SASL auth
    """

    def __init__(self):
        PlugIn.__init__(self)
        self.bound = None
        self.supports_sm = False
        self.resuming = False

    def plugin(self, owner):
        """ Start resource binding, if allowed at this time. Used internally. """
        if self._owner.Dispatcher.Stream.features:
            try:
                self.FeaturesHandler(self._owner.Dispatcher,
                    self._owner.Dispatcher.Stream.features)
            except NodeProcessed:
                pass
        else:
            self._owner.RegisterHandler('features', self.FeaturesHandler,
                xmlns=NS_STREAMS)

    def FeaturesHandler(self, conn, feats):
        """
        Determine if server supports resource binding and set some internal
        attributes accordingly.

        It also checks if server supports stream management
        """

        if feats.getTag('sm', namespace=NS_STREAM_MGMT):
            self.supports_sm = True # server supports stream management
            if self.resuming:
                self._owner._caller.sm.resume_request()

        if not feats.getTag('bind', namespace=NS_BIND):
            log.info('Server does not requested binding.')
            # we try to bind resource anyway
            #self.bound='failure'
            self.bound = []
            return

        self.session = -1
        session = feats.getTag('session', namespace=NS_SESSION)
        if session is not None:
            if session.getTag('optional') is None:
                self.session = 1

        self.bound = []

    def plugout(self):
        """
        Remove Bind handler from owner's dispatcher. Used internally
        """
        self._owner.UnregisterHandler('features', self.FeaturesHandler,
            xmlns=NS_STREAMS)

    def NonBlockingBind(self, resource=None, on_bound=None):
        """
        Perform binding. Use provided resource name or random (if not provided).
        """
        if self.resuming: # We don't bind if we resume the stream
            return
        self.on_bound = on_bound
        self._resource = resource
        if self._resource:
            self._resource = [Node('resource', payload=[self._resource])]
        else:
            self._resource = []

        self._owner.onreceive(None)
        self._owner.Dispatcher.SendAndWaitForResponse(
            Protocol('iq', typ='set', payload=[Node('bind',
            attrs={'xmlns': NS_BIND}, payload=self._resource)]),
            func=self._on_bound)

    def _on_bound(self, resp):
        if isResultNode(resp):
            if resp.getTag('bind') and resp.getTag('bind').getTagData('jid'):
                self.bound.append(resp.getTag('bind').getTagData('jid'))
                log.info('Successfully bound %s.' % self.bound[-1])
                jid = JID(resp.getTag('bind').getTagData('jid'))
                self._owner._registered_name = jid
                self._owner.User = jid.getNode()
                self._owner.Resource = jid.getResource()
                # Only negociate stream management after bounded
                if self.supports_sm:
                    # starts negociation
                    sm = self._owner._caller.sm
                    sm.supports_sm = True
                    sm.set_owner(self._owner)
                    sm.negociate()
                    self._owner.Dispatcher.sm = sm

                if hasattr(self, 'session') and self.session == -1:
                    # Server don't want us to initialize a session
                    log.info('No session required.')
                    self._owner._caller.sm.resend_queue()   #resend old messages still in the smacks queue
                    self.on_bound('ok')
                else:
                    self._owner.SendAndWaitForResponse(Protocol('iq', typ='set',
                        payload=[Node('session', attrs={'xmlns':NS_SESSION})]),
                        func=self._on_session)
                return
        if resp:
            log.info('Binding failed: %s.' % resp.getTag('error'))
            self.on_bound(None)
        else:
            log.info('Binding failed: timeout expired.')
            self.on_bound(None)

    def _on_session(self, resp):
        self._owner.onreceive(None)
        if isResultNode(resp):
            log.info('Successfully opened session.')
            self.session = 1
            self._owner._caller.sm.resend_queue()   #resend old messages still in the smacks queue
            self.on_bound('ok')
        else:
            log.error('Session open failed.')
            self.session = 0
            self.on_bound(None)
