# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
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
import time
import random
import string

from nbxmpp.protocol import NS_OPENPGP
from nbxmpp.protocol import NS_OPENPGP_PK
from nbxmpp.protocol import NS_OPENPGP_SK
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import NS_CLIENT
from nbxmpp.protocol import NS_EME
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Node
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import JID
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.util import raise_error
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PGPKeyMetadata
from nbxmpp.structs import PGPPublicKey
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.pubsub import get_pubsub_request

log = logging.getLogger('nbxmpp.m.openpgp')


class OpenPGP:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_openpgp,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_openpgp_message,
                          ns=NS_OPENPGP,
                          priority=7),
        ]

    def _process_openpgp_message(self, _con, stanza, properties):
        openpgp = stanza.getTag('openpgp', namespace=NS_OPENPGP)
        if openpgp is None:
            log.warning('No openpgp node found')
            log.warning(stanza)
            return

        data = openpgp.getData()
        if not data:
            log.warning('No data in openpgp node found')
            log.warning(stanza)
            return

        log.info('Encrypted message received')
        try:
            properties.openpgp = b64decode(data, return_type=bytes)
        except Exception:
            log.warning('b64decode failed')
            log.warning(stanza)
            return

    def _process_pubsub_openpgp(self, _con, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_OPENPGP_PK:
            return

        '''
        <item>
            <public-keys-list xmlns='urn:xmpp:openpgp:0'>
              <pubkey-metadata
                v4-fingerprint='1357B01865B2503C18453D208CAC2A9678548E35'
                date='2018-03-01T15:26:12Z'
                />
              <pubkey-metadata
                v4-fingerprint='67819B343B2AB70DED9320872C6464AF2A8E4C02'
                date='1953-05-16T12:00:00Z'
                />
            </public-keys-list>
          </item>
        '''
        if properties.pubsub_event.retracted:
            # Retracts should not happen and its unclear how we should react
            raise NodeProcessed

        if properties.pubsub_event.deleted:
            log.info('Keylist node deleted by %s', properties.jid)
            return

        item = properties.pubsub_event.item
        try:
            data = self._parse_keylist(properties.jid, item)
        except StanzaMalformed as error:
            log.warning(error)
            log.warning(stanza)
            raise NodeProcessed

        if data is None:
            pubsub_event = properties.pubsub_event._replace(empty=True)
            log.info('Received PGP keylist: %s - no keys set', properties.jid)
        else:
            pubsub_event = properties.pubsub_event._replace(data=data)
            log.info('Received PGP keylist: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @staticmethod
    def _parse_keylist(jid, item):
        if item is None:
            return []

        keylist_node = item.getTag('public-keys-list', namespace=NS_OPENPGP)
        if keylist_node is None:
            raise StanzaMalformed('No public-keys-list node found')

        metadata = keylist_node.getTags('pubkey-metadata')
        if not metadata:
            return []

        data = []
        for key in metadata:
            fingerprint = key.getAttr('v4-fingerprint')
            date = key.getAttr('date')
            if fingerprint is None or date is None:
                raise StanzaMalformed('Invalid metadata node')

            timestamp = parse_datetime(date, epoch=True)
            if timestamp is None:
                raise StanzaMalformed('Invalid date timestamp: %s' % date)

            data.append(PGPKeyMetadata(jid, fingerprint, timestamp))
        return data

    def set_keylist(self, keylist):
        item = Node('public-keys-list', {'xmlns': NS_OPENPGP})
        if keylist is not None:
            for key in keylist:
                date = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                     time.gmtime(key.date))
                attrs = {'v4-fingerprint': key.fingerprint,
                         'date': date}
                item.addChild('pubkey-metadata', attrs=attrs)

        log.info('Set keylist: %s', keylist)
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_OPENPGP_PK, item, id_='current')

    def set_public_key(self, key, fingerprint, date):
        date = time.strftime(
            '%Y-%m-%dT%H:%M:%SZ', time.gmtime(date))
        item = Node('pubkey', attrs={'xmlns': NS_OPENPGP,
                                     'date': date})
        data = item.addChild('data')
        data.addData(b64encode(key))
        node = '%s:%s' % (NS_OPENPGP_PK, fingerprint)

        log.info('Set public key')
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, node, item, id_='current')

    @call_on_response('_public_key_received')
    def request_public_key(self, jid, fingerprint):
        log.info('Request public key from: %s %s', jid, fingerprint)
        node = '%s:%s' % (NS_OPENPGP_PK, fingerprint)
        return get_pubsub_request(jid, node, max_items=1)

    @callback
    def _public_key_received(self, stanza):
        jid = JID(stanza.getFrom().getBare())

        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        pubsub_node = stanza.getTag('pubsub')
        items_node = pubsub_node.getTag('items')
        item = items_node.getTag('item')

        pub_key = item.getTag('pubkey', namespace=NS_OPENPGP)
        if pub_key is None:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               'PGP public key has no pubkey node')

        date = parse_datetime(pub_key.getAttr('date'), epoch=True)

        data = pub_key.getTag('data')
        if data is None:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               'PGP public key has no data node')

        try:
            key = b64decode(data.getData(), return_type=bytes)
        except Exception as error:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               str(error))

        key = PGPPublicKey(jid, key, date)
        log.info('Received public key: %s %s', key.jid, key.date)
        return key

    @call_on_response('_keylist_received')
    def request_keylist(self, jid):
        log.info('Request keylist from: %s', jid)
        return get_pubsub_request(jid, NS_OPENPGP_PK, max_items=1)

    @callback
    def _keylist_received(self, stanza):
        jid = JID(stanza.getFrom().getBare())

        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        pubsub_node = stanza.getTag('pubsub')
        items_node = pubsub_node.getTag('items')
        item = items_node.getTag('item')

        try:
            keylist = self._parse_keylist(jid, item)
        except StanzaMalformed as error:
            return raise_error(log.warning, stanza,
                               'stanza-malformed', str(error))
        log.info('Received keylist: %s', keylist)
        return keylist

    @call_on_response('_secret_key_received')
    def request_secret_key(self):
        log.info('Request secret key')
        jid = self._client.get_bound_jid().getBare()
        return get_pubsub_request(jid, NS_OPENPGP_SK, max_items=1)

    @callback
    def _secret_key_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        pubsub_node = stanza.getTag('pubsub')
        items_node = pubsub_node.getTag('items')
        item = items_node.getTag('item')

        sec_key = item.getTag('secretkey', namespace=NS_OPENPGP)
        if sec_key is None:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               'PGP secretkey node not found')

        data = sec_key.getData()
        if not data:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               'PGP secretkey has no data')

        try:
            key = b64decode(data.getData(), return_type=bytes)
        except Exception as error:
            return raise_error(log.warning, stanza, 'stanza-malformed',
                               str(error))
        log.info('Received secret key')
        return key

    def set_secret_key(self, secret_key):
        item = Node('secretkey', {'xmlns': NS_OPENPGP})
        if secret_key is not None:
            item.setData(b64encode(secret_key))

        log.info('Set secret key')
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_OPENPGP_SK, item, id_='current')


def parse_signcrypt(stanza):
    '''
    <signcrypt xmlns='urn:xmpp:openpgp:0'>
      <to jid='juliet@example.org'/>
      <time stamp='2014-07-10T17:06:00+02:00'/>
      <rpad>
        f0rm1l4n4-mT8y33j!Y%fRSrcd^ZE4Q7VDt1L%WEgR!kv
      </rpad>
      <payload>
        <body xmlns='jabber:client'>
          This is a secret message.
        </body>
      </payload>
    </signcrypt>
    '''
    if stanza.getName() != 'signcrypt' or stanza.getNamespace() != NS_OPENPGP:
        raise StanzaMalformed('Invalid signcrypt node')

    to = stanza.getTagAttr('to', 'jid')
    if to is None:
        raise StanzaMalformed('Invalid to attr')

    timestamp = stanza.getTagAttr('time', 'stamp')
    if timestamp is None:
        raise StanzaMalformed('Invalid timestamp')

    payload = stanza.getTag('payload')
    if payload is None or payload.getChildren() is None:
        raise StanzaMalformed('Invalid payload node')
    return payload.getChildren(), to, timestamp


def create_signcrypt_node(stanza, not_encrypted_nodes):
    '''
    <signcrypt xmlns='urn:xmpp:openpgp:0'>
      <to jid='juliet@example.org'/>
      <time stamp='2014-07-10T17:06:00+02:00'/>
      <rpad>
        f0rm1l4n4-mT8y33j!Y%fRSrcd^ZE4Q7VDt1L%WEgR!kv
      </rpad>
      <payload>
        <body xmlns='jabber:client'>
          This is a secret message.
        </body>
      </payload>
    </signcrypt>
    '''
    encrypted_nodes = []
    child_nodes = list(stanza.getChildren())
    for node in child_nodes:
        if (node.getName(), node.getNamespace()) not in not_encrypted_nodes:
            if not node.getNamespace():
                node.setNamespace(NS_CLIENT)
            encrypted_nodes.append(node)
            stanza.delChild(node)

    signcrypt = Node('signcrypt', attrs={'xmlns': NS_OPENPGP})
    signcrypt.addChild('to', attrs={'jid': stanza.getTo().getBare()})

    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    signcrypt.addChild('time', attrs={'stamp': timestamp})

    signcrypt.addChild('rpad').addData(get_rpad())

    payload = signcrypt.addChild('payload')

    for node in encrypted_nodes:
        payload.addChild(node=node)

    return signcrypt


def get_rpad():
    rpad_range = random.randint(30, 50)
    return ''.join(
        random.choice(string.ascii_letters) for _ in range(rpad_range))


def create_message_stanza(stanza, encrypted_payload, with_fallback_text):
    b64encoded_payload = b64encode(encrypted_payload)

    openpgp_node = Node('openpgp', attrs={'xmlns': NS_OPENPGP})
    openpgp_node.addData(b64encoded_payload)
    stanza.addChild(node=openpgp_node)

    eme_node = Node('encryption', attrs={'xmlns': NS_EME,
                                         'namespace': NS_OPENPGP})
    stanza.addChild(node=eme_node)

    if with_fallback_text:
        stanza.setBody(
            '[This message is *encrypted* with OpenPGP (See :XEP:`0373`]')
