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

import time
import random
import string

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Node
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.protocol import JID
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import PGPKeyMetadata
from nbxmpp.structs import PGPPublicKey
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import iq_request_task
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.modules.util import raise_if_error


class OpenPGP(BaseModule):

    _depends = {
        'publish': 'PubSub',
        'request_items': 'PubSub',
    }

    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_pubsub_openpgp,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_openpgp_message,
                          ns=Namespace.OPENPGP,
                          priority=7),
        ]

    def _process_openpgp_message(self, _client, stanza, properties):
        openpgp = stanza.getTag('openpgp', namespace=Namespace.OPENPGP)
        if openpgp is None:
            self._log.warning('No openpgp node found')
            self._log.warning(stanza)
            return

        data = openpgp.getData()
        if not data:
            self._log.warning('No data in openpgp node found')
            self._log.warning(stanza)
            return

        self._log.info('Encrypted message received')
        try:
            properties.openpgp = b64decode(data, return_type=bytes)
        except Exception:
            self._log.warning('b64decode failed')
            self._log.warning(stanza)
            return

    def _process_pubsub_openpgp(self, _client, stanza, properties):
        """
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
        """

        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.OPENPGP_PK:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        try:
            data = _parse_keylist(properties.jid, item)
        except ValueError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            raise NodeProcessed

        if data is None:
            self._log.info('Received PGP keylist: %s - no keys set',
                           properties.jid)
            return

        pubsub_event = properties.pubsub_event._replace(data=data)
        self._log.info('Received PGP keylist: %s - %s', properties.jid, data)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_keylist(self, keylist, public=True):
        task = yield

        access_model = 'open' if public else 'presence'

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        self._log.info('Set keylist: %s', keylist)

        result = yield self.publish(Namespace.OPENPGP_PK,
                                    _make_keylist(keylist),
                                    id_='current',
                                    options=options,
                                    force_node_options=True)

        yield finalize(task, result)

    @iq_request_task
    def set_public_key(self, key, fingerprint, date, public=True):
        task = yield

        self._log.info('Set public key')

        access_model = 'open' if public else 'presence'

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        result = yield self.publish(f'{Namespace.OPENPGP_PK}:{fingerprint}',
                                    _make_public_key(key, date),
                                    id_='current',
                                    options=options,
                                    force_node_options=True)

        yield finalize(task, result)

    @iq_request_task
    def request_public_key(self, jid, fingerprint):
        task = yield

        self._log.info('Request public key from: %s %s', jid, fingerprint)

        items = yield self.request_items(
            f'{Namespace.OPENPGP_PK}:{fingerprint}',
            max_items=1,
            jid=jid)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        try:
            key = _parse_public_key(jid, items[0])
        except ValueError as error:
            raise MalformedStanzaError(str(error), items)

        yield key

    @iq_request_task
    def request_keylist(self, jid=None):
        task = yield

        self._log.info('Request keylist from: %s', jid)

        items = yield self.request_items(
            Namespace.OPENPGP_PK,
            max_items=1,
            jid=jid)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        try:
            keylist = _parse_keylist(jid, items[0])
        except ValueError as error:
            raise MalformedStanzaError(str(error), items)

        self._log.info('Received keylist: %s', keylist)
        yield keylist

    @iq_request_task
    def request_secret_key(self):
        task = yield

        self._log.info('Request secret key')

        items = yield self.request_items(
            Namespace.OPENPGP_SK,
            max_items=1)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        try:
            secret_key = _parse_secret_key(items[0])
        except ValueError as error:
            raise MalformedStanzaError(str(error), items)

        yield secret_key

    @iq_request_task
    def set_secret_key(self, secret_key):
        task = yield

        self._log.info('Set public key')

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': 'whitelist',
        }

        self._log.info('Set secret key')

        result = yield self.publish(Namespace.OPENPGP_SK,
                                    _make_secret_key(secret_key),
                                    id_='current',
                                    options=options,
                                    force_node_options=True)

        yield finalize(task, result)


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
    if (stanza.getName() != 'signcrypt' or
            stanza.getNamespace() != Namespace.OPENPGP):
        raise StanzaMalformed('Invalid signcrypt node')

    to_nodes = stanza.getTags('to')
    if not to_nodes:
        raise StanzaMalformed('missing to nodes')

    recipients = []
    for to_node in to_nodes:
        jid = to_node.getAttr('jid')
        try:
            recipients.append(JID.from_string(jid))
        except Exception as error:
            raise StanzaMalformed('Invalid jid: %s %s' % (jid, error))

    timestamp = stanza.getTagAttr('time', 'stamp')
    if timestamp is None:
        raise StanzaMalformed('Invalid timestamp')

    payload = stanza.getTag('payload')
    if payload is None or payload.getChildren() is None:
        raise StanzaMalformed('Invalid payload node')
    return payload.getChildren(), recipients, timestamp


def create_signcrypt_node(stanza, recipients, not_encrypted_nodes):
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
                node.setNamespace(Namespace.CLIENT)
            encrypted_nodes.append(node)
            stanza.delChild(node)

    signcrypt = Node('signcrypt', attrs={'xmlns': Namespace.OPENPGP})
    for recipient in recipients:
        signcrypt.addChild('to', attrs={'jid': str(recipient)})

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

    openpgp_node = Node('openpgp', attrs={'xmlns': Namespace.OPENPGP})
    openpgp_node.addData(b64encoded_payload)
    stanza.addChild(node=openpgp_node)

    eme_node = Node('encryption', attrs={'xmlns': Namespace.EME,
                                         'namespace': Namespace.OPENPGP})
    stanza.addChild(node=eme_node)

    if with_fallback_text:
        stanza.setBody(
            '[This message is *encrypted* with OpenPGP (See :XEP:`0373`]')


def _make_keylist(keylist):
    item = Node('public-keys-list', {'xmlns': Namespace.OPENPGP})
    if keylist is not None:
        for key in keylist:
            date = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                 time.gmtime(key.date))
            attrs = {'v4-fingerprint': key.fingerprint,
                     'date': date}
            item.addChild('pubkey-metadata', attrs=attrs)
    return item


def _make_public_key(key, date):
    date = time.strftime(
        '%Y-%m-%dT%H:%M:%SZ', time.gmtime(date))
    item = Node('pubkey', attrs={'xmlns': Namespace.OPENPGP,
                                 'date': date})
    data = item.addChild('data')
    data.addData(b64encode(key))
    return item


def _make_secret_key(secret_key):
    item = Node('secretkey', {'xmlns': Namespace.OPENPGP})
    if secret_key is not None:
        item.setData(b64encode(secret_key))
    return item


def _parse_public_key(jid, item):
    pub_key = item.getTag('pubkey', namespace=Namespace.OPENPGP)
    if pub_key is None:
        raise ValueError('pubkey node missing')

    date = parse_datetime(pub_key.getAttr('date'), epoch=True)

    data = pub_key.getTag('data')
    if data is None:
        raise ValueError('data node missing')

    try:
        key = b64decode(data.getData(), return_type=bytes)
    except Exception as error:
        raise ValueError(f'decoding error: {error}')

    return PGPPublicKey(jid, key, date)


def _parse_keylist(jid, item):
    keylist_node = item.getTag('public-keys-list',
                               namespace=Namespace.OPENPGP)
    if keylist_node is None:
        raise ValueError('public-keys-list node missing')

    metadata = keylist_node.getTags('pubkey-metadata')
    if not metadata:
        return None

    data = []
    for key in metadata:
        fingerprint = key.getAttr('v4-fingerprint')
        date = key.getAttr('date')
        if fingerprint is None or date is None:
            raise ValueError('Invalid metadata node')

        timestamp = parse_datetime(date, epoch=True)
        if timestamp is None:
            raise ValueError('Invalid date timestamp: %s' % date)

        data.append(PGPKeyMetadata(jid, fingerprint, timestamp))
    return data


def _parse_secret_key(item):
    sec_key = item.getTag('secretkey', namespace=Namespace.OPENPGP)
    if sec_key is None:
        raise ValueError('secretkey node missing')

    data = sec_key.getData()
    if not data:
        raise ValueError('secretkey data missing')

    try:
        key = b64decode(data, return_type=bytes)
    except Exception as error:
        raise ValueError(f'decoding error: {error}')

    return key
