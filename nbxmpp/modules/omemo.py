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

from __future__ import annotations

from typing import Any
from typing import Optional

from nbxmpp import types
from nbxmpp.namespaces import Namespace
from nbxmpp.jid import JID
from nbxmpp.exceptions import NodeProcessed
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
from nbxmpp.builder import E
from nbxmpp.builder import Message


class OMEMO(BaseModule):

    _depends = {
        'publish': 'PubSub',
        'request_items': 'PubSub',
    }

    def __init__(self, client: types.Client):
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

    def _process_omemo_message(self,
                               _client: types.Client,
                               stanza: types.Message,
                               properties: Any):
        try:
            properties.omemo = _parse_omemo_message(stanza)
            self._log.info('Received message')
        except MalformedStanzaError as error:
            self._log.warning(error)
            self._log.warning(stanza)
            return

    def _process_omemo_devicelist(self,
                                  _client: types.Client,
                                  stanza: types.Message,
                                  properties: Any):

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
    def set_devicelist(self,
                       devicelist: Optional[list[str]] = None,
                       public: bool = True):

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

        yield finalize(result)

    @iq_request_task
    def request_devicelist(self, jid: Optional[JID] = None):

        items = yield self.request_items(Namespace.OMEMO_TEMP_DL,
                                         max_items=1,
                                         jid=jid)

        raise_if_error(items)

        if not items:
            yield None

        yield _parse_devicelist(items[0])

    @iq_request_task
    def set_bundle(self,
                   bundle,
                   device_id: str,
                   public: bool = True):


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

        yield finalize(result)

    @iq_request_task
    def request_bundle(self,
                       jid: JID,
                       device_id: str):

        items = yield self.request_items(
            f'{Namespace.OMEMO_TEMP_BUNDLE}:{device_id}',
            max_items=1,
            jid=jid)

        raise_if_error(items)

        if not items:
            yield None

        yield _parse_bundle(items[0])


def _parse_omemo_message(stanza: types.Message) -> OMEMOMessage:
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
    encrypted = stanza.find_tag('encrypted', namespace=Namespace.OMEMO_TEMP)
    if encrypted is None:
        raise MalformedStanzaError('No encrypted node found', stanza)

    header = encrypted.find_tag('header')
    if header is None:
        raise MalformedStanzaError('header node not found', stanza)

    try:
        sid = int(header.get('sid'))
    except Exception as error:
        raise MalformedStanzaError('sid attr not found', stanza)

    iv_node = header.find_tag('iv')
    try:
        iv = b64decode(iv_node.text or '')
    except Exception as error:
        raise MalformedStanzaError('failed to decode iv: %s' % error, stanza)

    payload = None
    payload_node = encrypted.find_tag('payload')
    if payload_node is not None:
        try:
            payload = b64decode(payload_node.text or '')
        except Exception as error:
            raise MalformedStanzaError('failed to decode payload: %s' % error,
                                       stanza)

    key_nodes = header.find_tags('key')
    if not key_nodes:
        raise MalformedStanzaError('no keys found', stanza)

    keys = {}
    for kn in key_nodes:
        rid = kn.get('rid')
        if rid is None:
            raise MalformedStanzaError('rid not found', stanza)

        prekey = kn.get('prekey')
        if prekey is None:
            prekey = False
        else:
            try:
                prekey = from_xs_boolean(prekey)
            except ValueError as error:
                raise MalformedStanzaError(error, stanza)

        try:
            keys[int(rid)] = (b64decode(kn.text or ''), prekey)
        except Exception as error:
            raise MalformedStanzaError('failed to decode key: %s' % error,
                                       stanza)

    return OMEMOMessage(sid=sid, iv=iv, keys=keys, payload=payload)


def _parse_bundle(item: types.Base) -> OMEMOBundle:
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

    bundle = item.find_tag('bundle', namespace=Namespace.OMEMO_TEMP)
    if bundle is None:
        raise MalformedStanzaError('No bundle node found', item)

    result = {}
    signed_prekey_node = bundle.find_tag('signedPreKeyPublic')
    try:
        result['spk'] = {'key': b64decode(signed_prekey_node.text or '')}
    except Exception as error:
        error = 'Failed to decode signedPreKeyPublic: %s' % error
        raise MalformedStanzaError(error, item)

    signed_prekey_id = signed_prekey_node.get('signedPreKeyId')
    try:
        result['spk']['id'] = int(signed_prekey_id)
    except Exception as error:
        raise MalformedStanzaError('Invalid signedPreKeyId: %s' % error, item)

    signed_signature_node = bundle.find_tag('signedPreKeySignature')
    try:
        result['spk_signature'] = b64decode(signed_signature_node.text or '')
    except Exception as error:
        error = 'Failed to decode signedPreKeySignature: %s' % error
        raise MalformedStanzaError(error, item)

    identity_key_node = bundle.find_tag('identityKey')
    try:
        result['ik'] = b64decode(identity_key_node.text or '')
    except Exception as error:
        error = 'Failed to decode IdentityKey: %s' % error
        raise MalformedStanzaError(error, item)

    prekeys = bundle.find_tag('prekeys')
    if prekeys is None or not prekeys.get_children():
        raise MalformedStanzaError('No prekeys node found', item)

    result['otpks'] = []
    for prekey in prekeys.get_children():
        try:
            id_ = int(prekey.get('preKeyId'))
        except Exception as error:
            raise MalformedStanzaError('Invalid prekey: %s' % error, item)

        try:
            key = b64decode(prekey.text or '')
        except Exception as error:
            raise MalformedStanzaError(
                'Failed to decode preKeyPublic: %s' % error, item)

        result['otpks'].append({'key': key, 'id': id_})

    return OMEMOBundle(**result)


def _make_bundle(bundle: OMEMOBundle) -> types.Base:
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
    bundle_node = E('bundle', namespace=Namespace.OMEMO_TEMP)
    prekey_pub_node = bundle_node.add_tag(
        'signedPreKeyPublic',
        signedPreKeyId=str(bundle.spk['id']))
    prekey_pub_node.text = b64encode(bundle.spk['key'])

    prekey_sig_node = bundle_node.add_tag('signedPreKeySignature')
    prekey_sig_node.text = b64encode(bundle.spk_signature)

    identity_key_node = bundle_node.add_tag('identityKey')
    identity_key_node.text = b64encode(bundle.ik)

    prekeys = bundle_node.add_tag('prekeys')
    for key in bundle.otpks:
        pre_key_public = prekeys.add_tag('preKeyPublic',
                                         preKeyId=key['id'])
        pre_key_public.text = b64encode(key['key'])
    return bundle_node


def _make_devicelist(devicelist: Optional[list[str]]) -> types.Base:
    if devicelist is None:
        devicelist = []

    devicelist_node = E('list', namespace=Namespace.OMEMO_TEMP)
    for device in devicelist:
        devicelist_node.add_tag('device', id=device)

    return devicelist_node


def _parse_devicelist(item: types.Base) -> list[int]:
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
    list_node = item.find_tag('list', namespace=Namespace.OMEMO_TEMP)
    if list_node is None:
        raise MalformedStanzaError('No list node found', item)

    if not list_node.get_children():
        return []

    result: list[int] = []
    devices_nodes = list_node.get_children()
    for dn in devices_nodes:
        _id = dn.get('id')
        if _id:
            result.append(int(_id))

    return result


def create_omemo_message(stanza: types.Message,
                         omemo_message: OMEMOMessage,
                         store_hint: bool = True,
                         node_whitelist: Optional[tuple[str, str]] = None):
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

    encrypted = E('encrypted', namespace=Namespace.OMEMO_TEMP)
    header = encrypted.add_tag('header', sid=omemo_message.sid)
    header.add_tag_text('iv', b64encode(omemo_message.iv))

    for rid, (key, prekey) in omemo_message.keys.items():
        attrs = {'rid': rid}
        if prekey:
            attrs['prekey'] = 'true'
        child = header.add_tag('key', **attrs)
        child.text = b64encode(key)

    encrypted.add_tag_text('payload', b64encode(omemo_message.payload))


    enc = stanza.add_tag('encryption', namespace=Namespace.EME, name='OMEMO')
    enc.set('namespace', Namespace.OMEMO_TEMP)

    stanza.append(encrypted)
    stanza.add_tag_text('body',
                        ("You received a message encrypted with "
                         "OMEMO but your client doesn't support OMEMO."))

    if store_hint:
        stanza.add_tag('store', namespace=Namespace.HINTS)


def get_key_transport_message(type: str,
                              jid: JID,
                              omemo_message: OMEMOMessage) -> types.Message:

    message = Message(to=jid, type=type)
    encrypted = message.add_tag('encrypted', namespace=Namespace.OMEMO_TEMP)
    header = encrypted.add_tag('header', sid=omemo_message.sid)

    for rid, (key, prekey) in omemo_message.keys.items():
        attrs = {'rid': rid}
        if prekey:
            attrs['prekey'] = 'true'
        child = header.add_tag('key', **attrs)
        child.text = b64encode(key)

    header.add_tag_text('iv', b64encode(omemo_message.iv))

    return message


def cleanup_stanza(stanza: types.Message,
                   node_whitelist: tuple[str, str]):

    whitelisted_nodes: list[types.Base] = []
    for tag, ns in node_whitelist:
        element = stanza.find_tag(tag, namespace=ns)
        if element is not None:
            whitelisted_nodes.append(element)

    for element in list(stanza):
        if element in whitelisted_nodes:
            continue
        stanza.remove(element)
