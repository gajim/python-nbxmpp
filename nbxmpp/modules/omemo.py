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

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import NodeProcessed
from nbxmpp.protocol import Node
from nbxmpp.protocol import Message
from nbxmpp.util import b64decode
from nbxmpp.util import b64encode
from nbxmpp.util import from_xs_boolean
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import OMEMOMessage
from nbxmpp.structs import OMEMOBundle
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.util import finalize
from nbxmpp.modules.util import raise_if_error
from nbxmpp.task import iq_request_task
from nbxmpp.errors import MalformedStanzaError


class OMEMO(BaseModule):

    _depends = {
        'publish': 'PubSub',
        'request_items': 'PubSub',
    }

    def __init__(self, client):
        BaseModule.__init__(self, client)

        self._client = client
        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_omemo_devicelist,
                          ns=Namespace.PUBSUB_EVENT,
                          priority=16),
            StanzaHandler(name='message',
                          callback=self._process_omemo_message,
                          ns=Namespace.OMEMO_TEMP,
                          priority=7),
        ]

    def _process_omemo_message(self, _client, stanza, properties):
        try:
            properties.omemo = _parse_omemo_message(stanza)
            self._log.info('Received message')
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            return

    def _process_omemo_devicelist(self, _client, stanza, properties):
        if not properties.is_pubsub_event:
            return

        if properties.pubsub_event.node != Namespace.OMEMO_TEMP_DL:
            return

        item = properties.pubsub_event.item
        if item is None:
            # Retract, Deleted or Purged
            return

        try:
            devices = _parse_devicelist(item)
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            raise NodeProcessed

        if not devices:
            self._log.info('Received OMEMO devicelist: %s - no devices set',
                           properties.jid)
            return

        pubsub_event = properties.pubsub_event._replace(data=devices)
        self._log.info('Received OMEMO devicelist: %s - %s',
                       properties.jid, devices)

        properties.pubsub_event = pubsub_event

    @iq_request_task
    def set_devicelist(self, devicelist=None, public=True):
        task = yield

        self._log.info('Set devicelist: %s', devicelist)

        access_model = 'open' if public else 'presence'

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        result = yield self.publish(Namespace.OMEMO_TEMP_DL,
                                    _make_devicelist(devicelist),
                                    id_='current',
                                    options=options,
                                    force_node_options=True)

        yield finalize(task, result)

    @iq_request_task
    def request_devicelist(self, jid=None):
        task = yield

        items = yield self.request_items(Namespace.OMEMO_TEMP_DL,
                                         max_items=1,
                                         jid=jid)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        yield _parse_devicelist(items[0])

    @iq_request_task
    def set_bundle(self, bundle, device_id, public=True):
        task = yield

        self._log.info('Set bundle')

        access_model = 'open' if public else 'presence'

        options = {
            'pubsub#persist_items': 'true',
            'pubsub#access_model': access_model,
        }

        result = yield self.publish(
            f'{Namespace.OMEMO_TEMP_BUNDLE}:{device_id}',
            _make_bundle(bundle),
            id_='current',
            options=options,
            force_node_options=True)

        yield finalize(task, result)

    @iq_request_task
    def request_bundle(self, jid, device_id):
        task = yield

        self._log.info('Request bundle from: %s %s', jid, device_id)

        items = yield self.request_items(
            f'{Namespace.OMEMO_TEMP_BUNDLE}:{device_id}',
            max_items=1,
            jid=jid)

        raise_if_error(items)

        if not items:
            yield task.set_result(None)

        yield _parse_bundle(items[0])


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
    encrypted = stanza.getTag('encrypted', namespace=Namespace.OMEMO_TEMP)
    if encrypted is None:
        raise MalformedStanzaError('No encrypted node found', stanza)

    header = encrypted.getTag('header')
    if header is None:
        raise MalformedStanzaError('header node not found', stanza)

    try:
        sid = int(header.getAttr('sid'))
    except Exception as error:
        raise MalformedStanzaError('sid attr not found', stanza)

    iv_node = header.getTag('iv')
    try:
        iv = b64decode(iv_node.getData(), bytes)
    except Exception as error:
        raise MalformedStanzaError('failed to decode iv: %s' % error, stanza)

    payload = None
    payload_node = encrypted.getTag('payload')
    if payload_node is not None:
        try:
            payload = b64decode(payload_node.getData(), bytes)
        except Exception as error:
            raise MalformedStanzaError('failed to decode payload: %s' % error,
                                       stanza)

    key_nodes = header.getTags('key')
    if not key_nodes:
        raise MalformedStanzaError('no keys found', stanza)

    keys = {}
    for kn in key_nodes:
        rid = kn.getAttr('rid')
        if rid is None:
            raise MalformedStanzaError('rid not found', stanza)

        prekey = kn.getAttr('prekey')
        if prekey is None:
            prekey = False
        else:
            try:
                prekey = from_xs_boolean(prekey)
            except ValueError as error:
                raise MalformedStanzaError(error, stanza)

        try:
            keys[int(rid)] = (b64decode(kn.getData(), bytes), prekey)
        except Exception as error:
            raise MalformedStanzaError('failed to decode key: %s' % error,
                                       stanza)

    return OMEMOMessage(sid=sid, iv=iv, keys=keys, payload=payload)


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
        raise MalformedStanzaError('No item in node found', item)

    bundle = item.getTag('bundle', namespace=Namespace.OMEMO_TEMP)
    if bundle is None:
        raise MalformedStanzaError('No bundle node found', item)

    result = {}
    signed_prekey_node = bundle.getTag('signedPreKeyPublic')
    try:
        result['spk'] = {'key': b64decode(signed_prekey_node.getData(),
                                          bytes)}
    except Exception as error:
        error = 'Failed to decode signedPreKeyPublic: %s' % error
        raise MalformedStanzaError(error, item)

    signed_prekey_id = signed_prekey_node.getAttr('signedPreKeyId')
    try:
        result['spk']['id'] = int(signed_prekey_id)
    except Exception as error:
        raise MalformedStanzaError('Invalid signedPreKeyId: %s' % error, item)

    signed_signature_node = bundle.getTag('signedPreKeySignature')
    try:
        result['spk_signature'] = b64decode(signed_signature_node.getData(),
                                            bytes)
    except Exception as error:
        error = 'Failed to decode signedPreKeySignature: %s' % error
        raise MalformedStanzaError(error, item)

    identity_key_node = bundle.getTag('identityKey')
    try:
        result['ik'] = b64decode(identity_key_node.getData(), bytes)
    except Exception as error:
        error = 'Failed to decode IdentityKey: %s' % error
        raise MalformedStanzaError(error, item)

    prekeys = bundle.getTag('prekeys')
    if prekeys is None or not prekeys.getChildren():
        raise MalformedStanzaError('No prekeys node found', item)

    result['otpks'] = []
    for prekey in prekeys.getChildren():
        try:
            id_ = int(prekey.getAttr('preKeyId'))
        except Exception as error:
            raise MalformedStanzaError('Invalid prekey: %s' % error, item)

        try:
            key = b64decode(prekey.getData(), bytes)
        except Exception as error:
            raise MalformedStanzaError(
                'Failed to decode preKeyPublic: %s' % error, item)

        result['otpks'].append({'key': key, 'id': id_})

    return OMEMOBundle(**result)


def _make_bundle(bundle):
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
    bundle_node = Node('bundle', attrs={'xmlns': Namespace.OMEMO_TEMP})
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


def _make_devicelist(devicelist):
    if devicelist is None:
        devicelist = []

    devicelist_node = Node('list', attrs={'xmlns': Namespace.OMEMO_TEMP})
    for device in devicelist:
        devicelist_node.addChild('device').setAttr('id', device)

    return devicelist_node


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
    list_node = item.getTag('list', namespace=Namespace.OMEMO_TEMP)
    if list_node is None:
        raise MalformedStanzaError('No list node found', item)

    if not list_node.getChildren():
        return []

    result = []
    devices_nodes = list_node.getChildren()
    for dn in devices_nodes:
        _id = dn.getAttr('id')
        if _id:
            result.append(int(_id))

    return result


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

    encrypted = Node('encrypted', attrs={'xmlns': Namespace.OMEMO_TEMP})
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

    stanza.addChild(node=Node('encryption',
                              attrs={'xmlns': Namespace.EME,
                                     'name': 'OMEMO',
                                     'namespace': Namespace.OMEMO_TEMP}))

    stanza.setBody("You received a message encrypted with "
                   "OMEMO but your client doesn't support OMEMO.")

    if store_hint:
        stanza.addChild(node=Node('store', attrs={'xmlns': Namespace.HINTS}))


def get_key_transport_message(typ, jid, omemo_message):
    message = Message(typ=typ, to=jid)

    encrypted = Node('encrypted', attrs={'xmlns': Namespace.OMEMO_TEMP})
    header = Node('header', attrs={'sid': omemo_message.sid})
    for rid, (key, prekey) in omemo_message.keys.items():
        attrs = {'rid': rid}
        if prekey:
            attrs['prekey'] = 'true'
        child = header.addChild('key', attrs=attrs)
        child.addData(b64encode(key))

    header.addChild('iv').addData(b64encode(omemo_message.iv))
    encrypted.addChild(node=header)

    message.addChild(node=encrypted)
    return message


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
