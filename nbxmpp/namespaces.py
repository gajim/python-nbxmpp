# Copyright (C) 2020 Philipp Hörist <philipp AT hoerist.com>
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

from dataclasses import dataclass

# pylint: disable=invalid-name
# pylint: disable=line-too-long

@dataclass(frozen=True)
class _Namespaces:

    ACTIVITY: str = 'http://jabber.org/protocol/activity'
    ADDRESS: str = 'http://jabber.org/protocol/address'
    AGENTS: str = 'jabber:iq:agents'
    ATTENTION: str = 'urn:xmpp:attention:0'
    AUTH: str = 'jabber:iq:auth'
    AVATAR_METADATA: str = 'urn:xmpp:avatar:metadata'
    AVATAR_DATA: str = 'urn:xmpp:avatar:data'
    BIND: str = 'urn:ietf:params:xml:ns:xmpp-bind'
    BLOCKING: str = 'urn:xmpp:blocking'
    BOB: str = 'urn:xmpp:bob'
    BOOKMARKS: str = 'storage:bookmarks'
    BOOKMARKS_1: str = 'urn:xmpp:bookmarks:1'
    BOOKMARKS_COMPAT: str = 'urn:xmpp:bookmarks:1#compat'
    BOOKMARKS_COMPAT_PEP: str = 'urn:xmpp:bookmarks:1#compat-pep'
    BOOKMARK_CONVERSION: str = 'urn:xmpp:bookmarks-conversion:0'
    BROWSE: str = 'jabber:iq:browse'
    BYTESTREAM: str = 'http://jabber.org/protocol/bytestreams'
    CAPS: str = 'http://jabber.org/protocol/caps'
    CAPTCHA: str = 'urn:xmpp:captcha'
    CARBONS: str = 'urn:xmpp:carbons:2'
    CHANNEL_BINDING: str = 'urn:xmpp:sasl-cb:0'
    CHATMARKERS: str = 'urn:xmpp:chat-markers:0'
    CHATSTATES: str = 'http://jabber.org/protocol/chatstates'
    CLIENT: str = 'jabber:client'
    COMMANDS: str = 'http://jabber.org/protocol/commands'
    CONFERENCE: str = 'jabber:x:conference'
    CORRECT: str = 'urn:xmpp:message-correct:0'
    DATA: str = 'jabber:x:data'
    DATA_LAYOUT: str = 'http://jabber.org/protocol/xdata-layout'
    DATA_MEDIA: str = 'urn:xmpp:media-element'
    DATA_VALIDATE: str = 'http://jabber.org/protocol/xdata-validate'
    DELAY: str = 'jabber:x:delay'
    DELAY2: str = 'urn:xmpp:delay'
    DELIMITER: str = 'roster:delimiter'
    DISCO: str = 'http://jabber.org/protocol/disco'
    DISCO_INFO: str = 'http://jabber.org/protocol/disco#info'
    DISCO_ITEMS: str = 'http://jabber.org/protocol/disco#items'
    DOMAIN_BASED_NAME: str = 'urn:xmpp:domain-based-name:1'
    EME: str = 'urn:xmpp:eme:0'
    ENCRYPTED: str = 'jabber:x:encrypted'
    FALLBACK: str = 'urn:xmpp:fallback:0'
    FASTEN: str = 'urn:xmpp:fasten:0'
    FILE_METADATA: str = 'urn:xmpp:file:metadata:0'
    FORWARD: str = 'urn:xmpp:forward:0'
    FRAMING: str = 'urn:ietf:params:xml:ns:xmpp-framing'
    GATEWAY: str = 'jabber:iq:gateway'
    GEOLOC: str = 'http://jabber.org/protocol/geoloc'
    HASHES: str = 'urn:xmpp:hashes:1'
    HASHES_2: str = 'urn:xmpp:hashes:2'
    HASHES_BLAKE2B_256: str = 'urn:xmpp:hash-function-text-names:id-blake2b256'
    HASHES_BLAKE2B_512: str = 'urn:xmpp:hash-function-text-names:id-blake2b512'
    HASHES_MD5: str = 'urn:xmpp:hash-function-text-names:md5'
    HASHES_SHA1: str = 'urn:xmpp:hash-function-text-names:sha-1'
    HASHES_SHA256: str = 'urn:xmpp:hash-function-text-names:sha-256'
    HASHES_SHA512: str = 'urn:xmpp:hash-function-text-names:sha-512'
    HASHES_SHA3_256: str = 'urn:xmpp:hash-function-text-names:sha3-256'
    HASHES_SHA3_512: str = 'urn:xmpp:hash-function-text-names:sha3-512'
    HINTS: str = 'urn:xmpp:hints'
    HTTPUPLOAD_0: str = 'urn:xmpp:http:upload:0'
    HTTP_AUTH: str = 'http://jabber.org/protocol/http-auth'
    IBB: str = 'http://jabber.org/protocol/ibb'
    IDLE: str = 'urn:xmpp:idle:1'
    JINGLE: str = 'urn:xmpp:jingle:1'
    JINGLE_BYTESTREAM: str = 'urn:xmpp:jingle:transports:s5b:1'
    JINGLE_DTLS: str = 'urn:xmpp:jingle:apps:dtls:0'
    JINGLE_ERRORS: str = 'urn:xmpp:jingle:errors:1'
    JINGLE_FILE_TRANSFER: str = 'urn:xmpp:jingle:apps:file-transfer:3'
    JINGLE_FILE_TRANSFER_5: str = 'urn:xmpp:jingle:apps:file-transfer:5'
    JINGLE_IBB: str = 'urn:xmpp:jingle:transports:ibb:1'
    JINGLE_ICE_UDP: str = 'urn:xmpp:jingle:transports:ice-udp:1'
    JINGLE_RAW_UDP: str = 'urn:xmpp:jingle:transports:raw-udp:1'
    JINGLE_RTP: str = 'urn:xmpp:jingle:apps:rtp:1'
    JINGLE_RTP_AUDIO: str = 'urn:xmpp:jingle:apps:rtp:audio'
    JINGLE_RTP_VIDEO: str = 'urn:xmpp:jingle:apps:rtp:video'
    JINGLE_XTLS: str = 'urn:xmpp:jingle:security:xtls:0'
    JINGLE_MESSAGE: str = 'urn:xmpp:jingle-message:0'
    LAST: str = 'jabber:iq:last'
    LOCATION: str = 'http://jabber.org/protocol/geoloc'
    MAM_1: str = 'urn:xmpp:mam:1'
    MAM_2: str = 'urn:xmpp:mam:2'
    MESSAGE_MODERATE: str = 'urn:xmpp:message-moderate:0'
    MESSAGE_RETRACT: str = 'urn:xmpp:message-retract:0'
    MOOD: str = 'http://jabber.org/protocol/mood'
    MSG_HINTS: str = 'urn:xmpp:hints'
    MUCLUMBUS: str = 'https://xmlns.zombofant.net/muclumbus/search/1.0'
    MUC: str = 'http://jabber.org/protocol/muc'
    MUC_USER: str = 'http://jabber.org/protocol/muc#user'
    MUC_ADMIN: str = 'http://jabber.org/protocol/muc#admin'
    MUC_OWNER: str = 'http://jabber.org/protocol/muc#owner'
    MUC_UNIQUE: str = 'http://jabber.org/protocol/muc#unique'
    MUC_CONFIG: str = 'http://jabber.org/protocol/muc#roomconfig'
    MUC_REQUEST: str = 'http://jabber.org/protocol/muc#request'
    MUC_INFO: str = 'http://jabber.org/protocol/muc#roominfo'
    NICK: str = 'http://jabber.org/protocol/nick'
    OCCUPANT_ID: str = 'urn:xmpp:occupant-id:0'
    OMEMO_TEMP: str = 'eu.siacs.conversations.axolotl'
    OMEMO_TEMP_BUNDLE: str = 'eu.siacs.conversations.axolotl.bundles'
    OMEMO_TEMP_DL: str = 'eu.siacs.conversations.axolotl.devicelist'
    OPENPGP: str = 'urn:xmpp:openpgp:0'
    OPENPGP_PK: str = 'urn:xmpp:openpgp:0:public-keys'
    OPENPGP_SK: str = 'urn:xmpp:openpgp:0:secret-key'
    PING: str = 'urn:xmpp:ping'
    PRIVACY: str = 'jabber:iq:privacy'
    PRIVATE: str = 'jabber:iq:private'
    PUBKEY_ATTEST: str = 'urn:xmpp:attest:2'
    PUBKEY_PUBKEY: str = 'urn:xmpp:pubkey:2'
    PUBKEY_REVOKE: str = 'urn:xmpp:revoke:2'
    PUBSUB: str = 'http://jabber.org/protocol/pubsub'
    PUBSUB_ERROR: str = 'http://jabber.org/protocol/pubsub#errors'
    PUBSUB_CONFIG: str = 'http://jabber.org/protocol/pubsub#node_config'
    PUBSUB_EVENT: str = 'http://jabber.org/protocol/pubsub#event'
    PUBSUB_OWNER: str = 'http://jabber.org/protocol/pubsub#owner'
    PUBSUB_PUBLISH_OPTIONS: str = 'http://jabber.org/protocol/pubsub#publish-options'
    PUBSUB_NODE_MAX: str = 'http://jabber.org/protocol/pubsub#config-node-max'
    REACTIONS: str = 'urn:xmpp:reactions:0'
    RECEIPTS: str = 'urn:xmpp:receipts'
    REGISTER: str = 'jabber:iq:register'
    REGISTER_FEATURE: str = 'http://jabber.org/features/iq-register'
    REPLY: str = 'urn:xmpp:reply:0'
    REPORTING: str = 'urn:xmpp:reporting:0'
    ROSTER: str = 'jabber:iq:roster'
    ROSTERNOTES: str = 'storage:rosternotes'
    ROSTERX: str = 'http://jabber.org/protocol/rosterx'
    ROSTER_VER: str = 'urn:xmpp:features:rosterver'
    RSM: str = 'http://jabber.org/protocol/rsm'
    SASL: str = 'urn:ietf:params:xml:ns:xmpp-sasl'
    SASL2: str = 'urn:xmpp:sasl:2'
    SEARCH: str = 'jabber:iq:search'
    SECLABEL: str = 'urn:xmpp:sec-label:0'
    SECLABEL_CATALOG: str = 'urn:xmpp:sec-label:catalog:2'
    SESSION: str = 'urn:ietf:params:xml:ns:xmpp-session'
    SFS: str = 'urn:xmpp:sfs:0'
    SID: str = 'urn:xmpp:sid:0'
    SIGNED: str = 'jabber:x:signed'
    SIMS: str = 'urn:xmpp:sims:1'
    STANZAS: str = 'urn:ietf:params:xml:ns:xmpp-stanzas'
    STICKERS: str = 'urn:xmpp:stickers:0'
    STREAM: str = 'http://affinix.com/jabber/stream'
    STREAMS: str = 'http://etherx.jabber.org/streams'
    STREAM_MGMT: str = 'urn:xmpp:sm:3'
    STYLING: str = 'urn:xmpp:styling:0'
    TIME_REVISED: str = 'urn:xmpp:time'
    TIME: str = 'urn:xmpp:time'
    TLS: str = 'urn:ietf:params:xml:ns:xmpp-tls'
    TUNE: str = 'http://jabber.org/protocol/tune'
    URL_DATA: str = 'http://jabber.org/protocol/url-data'
    VCARD: str = 'vcard-temp'
    VCARD_UPDATE: str = 'vcard-temp:x:update'
    VCARD_CONVERSION: str = 'urn:xmpp:pep-vcard-conversion:0'
    VCARD4: str = 'urn:ietf:params:xml:ns:vcard-4.0'
    VCARD4_PUBSUB: str = 'urn:xmpp:vcard4'
    VERSION: str = 'jabber:iq:version'
    XHTML_IM: str = 'http://jabber.org/protocol/xhtml-im'
    XHTML: str = 'http://www.w3.org/1999/xhtml'
    XMPP_STREAMS: str = 'urn:ietf:params:xml:ns:xmpp-streams'
    X_OOB: str = 'jabber:x:oob'
    XRD: str = 'http://docs.oasis-open.org/ns/xri/xrd-1.0'


Namespace: _Namespaces = _Namespaces()
