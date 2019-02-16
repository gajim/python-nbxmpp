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

from nbxmpp.protocol import NS_OMEMO_TEMP
from nbxmpp.protocol import NS_OMEMO_TEMP_DL
from nbxmpp.protocol import NS_OMEMO_TEMP_BUNDLE
from nbxmpp.protocol import NS_PUBSUB_EVENT
from nbxmpp.protocol import NS_EME
from nbxmpp.protocol import NS_HINTS
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Node
from nbxmpp.protocol import isResultNode
from nbxmpp.protocol import StanzaMalformed
from nbxmpp.util import call_on_response
from nbxmpp.util import callback
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.util import raise_error
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import OMEMOMessage
from nbxmpp.structs import OMEMOBundle
from nbxmpp.modules.pubsub import get_pubsub_request

log = logging.getLogger('nbxmpp.m.omemo')


class OMEMO:
    def __init__(self, client):
        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_omemo_devicelist,
                          ns=NS_PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_omemo_message,
                          ns=NS_OMEMO_TEMP,
                          priority=7),
        ]

    def _process_omemo_message(self, _con, stanza, properties):
        try:
            properties.omemo = self._parse_omemo_message(stanza)
            log.info('Received message')
        except StanzaMalformed as error:
            log.warning(error)
            log.warning(stanza)
            return

    @staticmethod
    def _parse_omemo_message(stanza):
        '''
        <message>
          <encrypted xmlns='eu.siacs.conversations.axolotl'>
            <header sid='27183'>
              <key rid='31415'>BASE64ENCODED...</key>
              <key prekey="true" rid='12321'>BASE64ENCODED...</key>
              <!-- ... -->
              <iv>BASE64ENCODED...</iv>
            </header>
            <payload>BASE64ENCODED</payload>
          </encrypted>
          <store xmlns='urn:xmpp:hints'/>
        </message>
        '''
        encrypted = stanza.getTag('encrypted', namespace=NS_OMEMO_TEMP)
        if encrypted is None:
            raise StanzaMalformed('No encrypted node found')

        header = encrypted.getTag('header')
        if header is None:
            raise StanzaMalformed('header node not found')

        try:
            sid = int(header.getAttr('sid'))
        except Exception as error:
            raise StanzaMalformed('sid attr not found')

        iv_node = header.getTag('iv')
        try:
            iv = b64decode(iv_node.getData(), bytes)
        except Exception as error:
            raise StanzaMalformed('failed to decode iv: %s' % error)

        payload = None
        payload_node = encrypted.getTag('payload')
        if payload_node is not None:
            try:
                payload = b64decode(payload_node.getData(), bytes)
            except Exception as error:
                raise StanzaMalformed('failed to decode payload: %s' % error)

        key_nodes = header.getTags('key')
        if not key_nodes:
            raise StanzaMalformed('no keys found')

        keys = {}
        for kn in key_nodes:
            rid = kn.getAttr('rid')
            if rid is None:
                raise StanzaMalformed('rid not found')

            prekey = kn.getAttr('prekey') == 'true'

            try:
                keys[int(rid)] = (b64decode(kn.getData(), bytes), prekey)
            except Exception as error:
                raise StanzaMalformed('failed to decode key: %s' % error)

        return OMEMOMessage(sid=sid, iv=iv, keys=keys, payload=payload)

    def _process_omemo_devicelist(self, _con, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != NS_OMEMO_TEMP_DL:
            return

        if properties.pubsub_event.retracted:
            # Retracts should not happen and its unclear how we should react
            raise NodeProcessed

        if properties.pubsub_event.deleted:
            log.info('Devicelist node deleted by %s', properties.jid)
            return

        item = properties.pubsub_event.item
        try:
            devices = self._parse_devicelist(item)
        except StanzaMalformed as error:
            log.warning(error)
            log.warning(stanza)
            raise NodeProcessed

        if not devices:
            pubsub_event = properties.pubsub_event._replace(empty=True)
            log.info('Received OMEMO devicelist: %s - no devices set',
                     properties.jid)
        else:
            pubsub_event = properties.pubsub_event._replace(data=devices)
            log.info('Received OMEMO devicelist: %s - %s',
                     properties.jid, devices)

        properties.pubsub_event = pubsub_event

    @staticmethod
    def _parse_devicelist(item):
        '''
        <items node='eu.siacs.conversations.axolotl.devicelist'>
          <item id='current'>
            <list xmlns='eu.siacs.conversations.axolotl'>
              <device id='12345' />
              <device id='4223' />
            </list>
          </item>
        </items>
        '''
        if item is None:
            return []

        list_node = item.getTag('list', namespace=NS_OMEMO_TEMP)
        if list_node is None:
            raise StanzaMalformed('No list node found')

        if not list_node.getChildren():
            return []

        result = []
        devices_nodes = list_node.getChildren()
        for dn in devices_nodes:
            _id = dn.getAttr('id')
            if _id:
                result.append(int(_id))

        return result

    def set_devicelist(self, devicelist=None):
        item = Node('list', attrs={'xmlns': NS_OMEMO_TEMP})
        for device in devicelist:
            item.addChild('device').setAttr('id', device)

        log.info('Set devicelist: %s', devicelist)
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, NS_OMEMO_TEMP_DL, item, id_='current')

    @call_on_response('_devicelist_received')
    def request_devicelist(self, jid=None):
        if jid is None:
            jid = self._client.get_bound_jid().getBare()
        log.info('Request devicelist from: %s', jid)
        return get_pubsub_request(jid, NS_OMEMO_TEMP_DL, max_items=1)

    @callback
    def _devicelist_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        pubsub_node = stanza.getTag('pubsub')
        items_node = pubsub_node.getTag('items')
        item = items_node.getTag('item')

        try:
            return self._parse_devicelist(item)
        except StanzaMalformed as error:
            return raise_error(log.warning, stanza,
                               'stanza-malformed', error)

    def set_bundle(self, bundle, device_id):
        item = self._create_bundle(bundle)
        log.info('Set bundle')

        node = '%s:%s' % (NS_OMEMO_TEMP_BUNDLE, device_id)
        jid = self._client.get_bound_jid().getBare()
        self._client.get_module('PubSub').publish(
            jid, node, item, id_='current')

    @staticmethod
    def _create_bundle(bundle):
        '''
        <publish node='eu.siacs.conversations.axolotl.bundles:31415'>
          <item id='current'>
            <bundle xmlns='eu.siacs.conversations.axolotl'>
              <signedPreKeyPublic signedPreKeyId='1'>
                BASE64ENCODED...
              </signedPreKeyPublic>
              <signedPreKeySignature>
                BASE64ENCODED...
              </signedPreKeySignature>
              <identityKey>
                BASE64ENCODED...
              </identityKey>
              <prekeys>
                <preKeyPublic preKeyId='1'>
                  BASE64ENCODED...
                </preKeyPublic>
                <preKeyPublic preKeyId='2'>
                  BASE64ENCODED...
                </preKeyPublic>
                <preKeyPublic preKeyId='3'>
                  BASE64ENCODED...
                </preKeyPublic>
                <!-- ... -->
              </prekeys>
            </bundle>
          </item>
        </publish>
        '''
        bundle_node = Node('bundle', attrs={'xmlns': NS_OMEMO_TEMP})
        prekey_pub_node = bundle_node.addChild(
            'signedPreKeyPublic',
            attrs={'signedPreKeyId': bundle.spk['id']})
        prekey_pub_node.addData(b64encode(bundle.spk['key']))

        prekey_sig_node = bundle_node.addChild('signedPreKeySignature')
        prekey_sig_node.addData(b64encode(bundle.spk_signature))

        identity_key_node = bundle_node.addChild('identityKey')
        identity_key_node.addData(b64encode(bundle.ik))

        prekeys = bundle_node.addChild('prekeys')
        for key in bundle.otpks:
            pre_key_public = prekeys.addChild('preKeyPublic',
                                              attrs={'preKeyId': key['id']})
            pre_key_public.addData(b64encode(key['key']))
        return bundle_node

    @call_on_response('_bundle_received')
    def request_bundle(self, jid, device_id):
        log.info('Request bundle from: %s %s', jid, device_id)
        node = '%s:%s' % (NS_OMEMO_TEMP_BUNDLE, device_id)
        return get_pubsub_request(jid, node, max_items=1)

    @callback
    def _bundle_received(self, stanza):
        if not isResultNode(stanza):
            return raise_error(log.info, stanza)

        pubsub_node = stanza.getTag('pubsub')
        items_node = pubsub_node.getTag('items')
        item = items_node.getTag('item')

        try:
            return self._parse_bundle(item)
        except StanzaMalformed as error:
            return raise_error(log.warning, stanza,
                               'stanza-malformed', error)

    @staticmethod
    def _parse_bundle(item):
        '''
        <item id='current'>
          <bundle xmlns='eu.siacs.conversations.axolotl'>
            <signedPreKeyPublic signedPreKeyId='1'>
              BASE64ENCODED...
            </signedPreKeyPublic>
            <signedPreKeySignature>
              BASE64ENCODED...
            </signedPreKeySignature>
            <identityKey>
              BASE64ENCODED...
            </identityKey>
            <prekeys>
              <preKeyPublic preKeyId='1'>
                BASE64ENCODED...
              </preKeyPublic>
              <preKeyPublic preKeyId='2'>
               BASE64ENCODED...
              </preKeyPublic>
              <preKeyPublic preKeyId='3'>
                BASE64ENCODED...
              </preKeyPublic>
              <!-- ... -->
            </prekeys>
          </bundle>
        </item>
        '''
        if item is None:
            raise StanzaMalformed('No item in node found')

        bundle = item.getTag('bundle', namespace=NS_OMEMO_TEMP)
        if bundle is None:
            raise StanzaMalformed('No bundle node found')

        result = {}
        signed_prekey_node = bundle.getTag('signedPreKeyPublic')
        try:
            result['spk'] = {'key': b64decode(signed_prekey_node.getData(), bytes)}
        except Exception as error:
            raise StanzaMalformed('Failed to decode '
                                  'signedPreKeyPublic: %s' % error)

        signed_prekey_id = signed_prekey_node.getAttr('signedPreKeyId')
        try:
            result['spk']['id'] = int(signed_prekey_id)
        except Exception as error:
            raise StanzaMalformed('Invalid signedPreKeyId: %s' % error)

        signed_signature_node = bundle.getTag('signedPreKeySignature')
        try:
            result['spk_signature'] = b64decode(signed_signature_node.getData(), bytes)
        except Exception as error:
            raise StanzaMalformed('Failed to decode '
                                  'signedPreKeySignature: %s' % error)

        identity_key_node = bundle.getTag('identityKey')
        try:
            result['ik'] = b64decode(identity_key_node.getData(), bytes)
        except Exception as error:
            raise StanzaMalformed('Failed to decode '
                                  'signedPreKeySignature: %s' % error)

        prekeys = bundle.getTag('prekeys')
        if prekeys is None or not prekeys.getChildren():
            raise StanzaMalformed('No prekeys node found')

        result['otpks'] = []
        for prekey in prekeys.getChildren():
            try:
                id_ = int(prekey.getAttr('preKeyId'))
            except Exception as error:
                raise StanzaMalformed('Invalid prekey: %s' % error)

            try:
                key = b64decode(prekey.getData(), bytes)
            except Exception as error:
                raise StanzaMalformed('Failed to decode preKeyPublic: %s' % error)

            result['otpks'].append({'key': key, 'id': id_})

        return OMEMOBundle(**result)


def create_omemo_message(stanza, omemo_message, store_hint=True,
                         node_whitelist=None):
    '''
    <message>
      <encrypted xmlns='eu.siacs.conversations.axolotl'>
        <header sid='27183'>
          <key rid='31415'>BASE64ENCODED...</key>
          <key prekey="true" rid='12321'>BASE64ENCODED...</key>
          <!-- ... -->
          <iv>BASE64ENCODED...</iv>
        </header>
        <payload>BASE64ENCODED</payload>
      </encrypted>
      <store xmlns='urn:xmpp:hints'/>
    </message>
    '''

    if node_whitelist is not None:
        cleanup_stanza(stanza, node_whitelist)

    encrypted = Node('encrypted', attrs={'xmlns': NS_OMEMO_TEMP})
    header = Node('header', attrs={'sid': omemo_message.sid})
    for rid, (key, prekey) in omemo_message.keys.items():
        attrs = {'rid': rid}
        if prekey:
            attrs['prekey'] = 'true'
        child = header.addChild('key', attrs=attrs)
        child.addData(b64encode(key))

    header.addChild('iv').addData(b64encode(omemo_message.iv))
    encrypted.addChild(node=header)

    payload = encrypted.addChild('payload')
    payload.addData(b64encode(omemo_message.payload))

    stanza.addChild(node=encrypted)

    stanza.addChild(node=Node('encryption', attrs={'xmlns': NS_EME,
                                                   'name': 'OMEMO',
                                                   'namespace': NS_OMEMO_TEMP}))

    stanza.setBody("You received a message encrypted with "
                   "OMEMO but your client doesn't support OMEMO.")

    if store_hint:
        stanza.addChild(node=Node('store', attrs={'xmlns': NS_HINTS}))


def cleanup_stanza(stanza, node_whitelist):
    whitelisted_nodes = []
    for tag, ns in node_whitelist:
        node = stanza.getTag(tag, namespace=ns)
        if node is not None:
            whitelisted_nodes.append(node)

    for node in list(stanza.getChildren()):
        stanza.delChild(node)

    for node in whitelisted_nodes:
        stanza.addChild(node=node)
