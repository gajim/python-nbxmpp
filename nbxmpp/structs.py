# Copyright (C) 2018-2020 Philipp Hörist <philipp AT hoerist.com>
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

import typing
from typing import Any
from typing import Optional
from typing import Set
from typing import NamedTuple
from typing import Union

import time
import random
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from gi.repository import Soup
from gi.repository import Gio

from nbxmpp.simplexml import Node
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import JID
from nbxmpp.const import AdHocAction
from nbxmpp.const import IqType
from nbxmpp.const import AdHocNoteType
from nbxmpp.const import MessageType
from nbxmpp.const import AvatarState
from nbxmpp.const import StatusCode
from nbxmpp.const import PresenceType
from nbxmpp.const import AdHocStatus
from nbxmpp.const import InviteType
from nbxmpp.const import Role
from nbxmpp.const import Affiliation
from nbxmpp.const import AnonymityMode
from nbxmpp.const import PresenceShow


class StanzaHandler(NamedTuple):
    name: str
    callback: Any
    typ: str = ''
    ns: str = ''
    xmlns: Optional[str] = None
    priority: int = 50


class CommonResult(NamedTuple):
    jid: Optional[JID] = None


class InviteData(NamedTuple):
    muc: JID
    from_: JID
    reason: Optional[str]
    password: Optional[str]
    type: InviteType
    continued: bool
    thread: Optional[str]


class DeclineData(NamedTuple):
    muc: JID
    from_: JID
    reason: Optional[str]


class CaptchaData(NamedTuple):
    form: Any
    bob_data: BobData


class BobData(NamedTuple):
    algo: str
    hash_: str
    max_age: str
    data: str
    cid: str
    type: str


class BookmarkData(NamedTuple):
    jid: JID
    name: Optional[str] = None
    nick: Optional[str] = None
    autojoin: bool = False
    password: Optional[str] = None
    extensions: Optional[Node] = None


class VoiceRequest(NamedTuple):
    jid:JID
    nick: str
    form: Any


class MucUserData(NamedTuple):
    jid: Optional[JID]
    affiliation: Optional[Affiliation]
    nick: Optional[str]
    role: Optional[Role]
    actor: Optional[str]
    reason: Optional[str]


class MucDestroyed(NamedTuple):
    alternate: Optional[JID]
    reason: Optional[str]
    password: Optional[str]


class MucConfigResult(NamedTuple):
    jid: JID
    form: Optional[Any] = None


class MucSubject(NamedTuple):
    text: str
    author: Optional[str]
    timestamp: Optional[float]


class AffiliationResult(NamedTuple):
    jid: JID
    users: dict[JID, dict[str, str]]


class EntityCapsData(NamedTuple):
    hash: str
    node: str
    ver: str


class HTTPAuthData(NamedTuple):
    id: Optional[str]
    method: Optional[str]
    url: Optional[str]
    body: Optional[str]


class StanzaIDData(NamedTuple):
    id: str
    by: str


class PubSubEventData(NamedTuple):
    node: Node
    id: Optional[str] = None
    item: Optional[Node] = None
    data: Optional[Any] = None
    deleted: bool = False
    retracted: bool = False
    purged: bool = False


class MoodData(NamedTuple):
    mood: str
    test: str


class BlockingPush(NamedTuple):
    block: Set[JID]
    unblock: Set[JID]
    unblock_all: bool


class ActivityData(NamedTuple):
    activity: str
    subactivity: str
    text: str


class LocationData(NamedTuple):
    accuracy: Optional[str] = None
    alt: Optional[str] = None
    altaccuracy: Optional[str] = None
    area: Optional[str] = None
    bearing: Optional[str] = None
    building: Optional[str] = None
    country: Optional[str] = None
    countrycode: Optional[str] = None
    datum: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    floor: Optional[str] = None
    lat: Optional[str] = None
    locality: Optional[str] = None
    lon: Optional[str] = None
    postalcode: Optional[str] = None
    region: Optional[str] = None
    room: Optional[str] = None
    speed: Optional[str] = None
    street: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[str] = None
    tzo: Optional[str] = None
    uri: Optional[str] = None


class PGPPublicKey(NamedTuple):
    jid: JID
    key: str
    date: datetime


class PGPKeyMetadata(NamedTuple):
    jid: JID
    fingerprint: str
    date: datetime


class OMEMOMessage(NamedTuple):
    sid: str
    iv: bytes
    keys: dict[int, tuple[bytes, bool]]
    payload: bytes


class AnnotationNote(NamedTuple):
    jid: JID
    data: str
    cdate: Optional[datetime] = None
    mdate: Optional[datetime] = None


class EMEData(NamedTuple):
    name: str
    namespace: str


class MuclumbusResult(NamedTuple):
    first: Optional[str]
    last: Optional[str]
    max: Optional[int]
    end: bool
    items: list[MuclumbusItem]


class MuclumbusItem(NamedTuple):
    jid: str
    name: str
    nusers: str
    description: str
    language: str
    is_open: bool
    anonymity_mode: AnonymityMode


class SoftwareVersionResult(NamedTuple):
    name: str
    version: str
    os: Optional[str]


class AdHocCommandNote(NamedTuple):
    text: str
    type: AdHocNoteType


class IBBData(NamedTuple):
    type: str
    sid: str
    block_size: Optional[int]
    seq: Optional[int]
    data: Optional[str]


class OOBData(NamedTuple):
    url: str
    desc: str


class CorrectionData(NamedTuple):
    id: str


class ModerationData(NamedTuple):
    stanza_id: str
    moderator_jid: str
    reason: Optional[str] = None
    timestamp: Optional[str] = None


class DiscoItems(NamedTuple):
    jid: JID
    node: str
    items: list[DiscoItem]


class DiscoItem(NamedTuple):
    jid: JID
    name: Optional[str]
    node: Optional[str]


class RegisterData(NamedTuple):
    instructions: Optional[str]
    form: Optional[Any]
    fields_form: Optional[Any]
    oob_url: Optional[str]
    bob_data: Optional[BobData]


class HTTPUploadData(NamedTuple):
    put_uri: str
    get_uri: str
    headers: dict[str, str]


class RSMData(NamedTuple):
    after: Optional[str]
    before: Optional[str]
    last: Optional[str]
    first: Optional[str]
    first_index: Optional[int]
    count: Optional[int]
    max: Optional[int]
    index: Optional[int]


class MAMQueryData(NamedTuple):
    jid: JID
    rsm: RSMData
    complete: bool


class MAMPreferencesData(NamedTuple):
    default: str
    always: list[JID]
    never: list[JID]


class LastActivityData(NamedTuple):
    seconds: int
    status: str


class RosterData(NamedTuple):
    items: Optional[list[RosterItem]]
    version: str


class RosterPush(NamedTuple):
    item: RosterItem
    version: str


@dataclass
class RosterItem:
    jid: JID
    name: Optional[str] = None
    ask: Optional[str] = None
    subscription: Optional[str] = None
    approved: Optional[str] = None
    groups: Set[str] = field(default_factory=set)

    @classmethod
    def from_node(cls, node: Node) -> RosterItem:
        attrs = node.getAttrs(copy=True)
        jid = attrs.get('jid')
        if jid is None:
            raise Exception('jid attribute missing')

        jid = JID.from_string(jid)
        if jid.is_full:
            raise Exception('full jid in roster not allowed')

        groups = {group.getData() for group in node.getTags('group')}

        return cls(jid=jid,
                   name=attrs.get('name'),
                   ask=attrs.get('ask'),
                   subscription=attrs.get('subscription') or 'none',
                   approved=attrs.get('approved'),
                   groups=groups)

    def asdict(self) -> dict[str, Any]:
        return {'jid': self.jid,
                'name': self.name,
                'ask': self.ask,
                'subscription': self.subscription,
                'approved': self.approved,
                'groups': self.groups}


class DiscoInfo(NamedTuple):
    stanza: Optional[Node]
    identities: list[DiscoIdentity]
    features: list[str]
    dataforms: list[Any]
    timestamp: Optional[float] = None

    def get_caps_hash(self) -> Optional[str]:
        try:
            return self.node.split('#')[1]
        except Exception:
            return None

    def has_field(self, form_type: str, var: str) -> bool:
        for dataform in self.dataforms:
            try:
                if dataform['FORM_TYPE'].value != form_type:
                    continue
                if var in dataform.vars:
                    return True

            except Exception:
                continue
        return False

    def get_field_value(self, form_type: str, var: str) -> Optional[Any]:
        for dataform in self.dataforms:
            try:
                if dataform['FORM_TYPE'].value != form_type:
                    continue

                if dataform[var].type_ == 'jid-multi':
                    return dataform[var].values or None
                return dataform[var].value or None

            except Exception:
                continue

        return None

    def supports(self, feature: str) -> bool:
        return feature in self.features

    def serialize(self) -> str:
        if self.stanza is None:
            raise ValueError('Unable to serialize DiscoInfo, no stanza found')
        return str(self.stanza)

    @property
    def node(self) -> Optional[str]:
        try:
            query = self.stanza.getQuery()
        except Exception:
            return None

        if query is not None:
            return query.getAttr('node')
        return None

    @property
    def jid(self) -> Optional[JID]:
        try:
            return self.stanza.getFrom()
        except Exception:
            return None

    @property
    def mam_namespace(self) -> Optional[str]:
        if Namespace.MAM_2 in self.features:
            return Namespace.MAM_2
        if Namespace.MAM_1 in self.features:
            return Namespace.MAM_1
        return None

    @property
    def has_mam_2(self) -> bool:
        return Namespace.MAM_2 in self.features

    @property
    def has_mam_1(self) -> bool:
        return Namespace.MAM_1 in self.features

    @property
    def has_mam(self) -> bool:
        return self.has_mam_1 or self.has_mam_2

    @property
    def has_httpupload(self) -> bool:
        return Namespace.HTTPUPLOAD_0 in self.features

    @property
    def has_message_moderation(self) -> bool:
        return Namespace.MESSAGE_MODERATE in self.features

    @property
    def is_muc(self) -> bool:
        for identity in self.identities:
            if identity.category == 'conference':
                if Namespace.MUC in self.features:
                    return True
        return False

    @property
    def is_irc(self) -> bool:
        for identity in self.identities:
            if identity.category == 'conference' and identity.type == 'irc':
                return True
        return False

    @property
    def muc_name(self) -> Optional[str]:
        if self.muc_room_name:
            return self.muc_room_name

        if self.muc_identity_name:
            return self.muc_identity_name

        if self.jid is not None:
            return self.jid.localpart
        return None

    @property
    def muc_identity_name(self) -> Optional[str]:
        for identity in self.identities:
            if identity.category == 'conference':
                return identity.name
        return None

    @property
    def muc_room_name(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roomconfig_roomname')

    @property
    def muc_description(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_description')

    @property
    def muc_log_uri(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_logs')

    @property
    def muc_users(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_occupants')

    @property
    def muc_contacts(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_contactjid')

    @property
    def muc_subject(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_subject')

    @property
    def muc_subjectmod(self) -> Optional[Any]:
        # muc#roominfo_changesubject stems from a wrong example in the MUC XEP
        # Ejabberd and Prosody use this value
        return (self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_subjectmod') or
                self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_changesubject'))

    @property
    def muc_lang(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_lang')

    @property
    def muc_is_persistent(self) -> bool:
        return 'muc_persistent' in self.features

    @property
    def muc_is_moderated(self) -> bool:
        return 'muc_moderated' in self.features

    @property
    def muc_is_open(self) -> bool:
        return 'muc_open' in self.features

    @property
    def muc_is_members_only(self) -> bool:
        return 'muc_membersonly' in self.features

    @property
    def muc_is_hidden(self) -> bool:
        return 'muc_hidden' in self.features

    @property
    def muc_is_nonanonymous(self) -> bool:
        return 'muc_nonanonymous' in self.features

    @property
    def muc_is_passwordprotected(self) -> bool:
        return 'muc_passwordprotected' in self.features

    @property
    def muc_is_public(self) -> bool:
        return 'muc_public' in self.features

    @property
    def muc_is_semianonymous(self) -> bool:
        return 'muc_semianonymous' in self.features

    @property
    def muc_is_temporary(self) -> bool:
        return 'muc_temporary' in self.features

    @property
    def muc_is_unmoderated(self) -> bool:
        return 'muc_unmoderated' in self.features

    @property
    def muc_is_unsecured(self) -> bool:
        return 'muc_unsecured' in self.features

    @property
    def is_gateway(self) -> bool:
        for identity in self.identities:
            if identity.category == 'gateway':
                return True
        return False

    @property
    def gateway_name(self) -> Optional[str]:
        for identity in self.identities:
            if identity.category == 'gateway':
                return identity.name
        return None

    @property
    def gateway_type(self) -> Optional[str]:
        for identity in self.identities:
            if identity.category == 'gateway':
                return identity.type
        return None

    def has_category(self, category: str) -> bool:
        for identity in self.identities:
            if identity.category == category:
                return True
        return False

    @property
    def httpupload_max_file_size(self) -> Optional[float]:
        size = self.get_field_value(Namespace.HTTPUPLOAD_0, 'max-file-size')
        try:
            return float(size)
        except Exception:
            return None


class DiscoIdentity(NamedTuple):

    category: str
    type: str
    name: Optional[str] = None
    lang: Optional[str] = None

    def get_node(self) -> Node:
        identity = Node('identity',
                        attrs={'category': self.category,
                               'type': self.type})
        if self.name is not None:
            identity.setAttr('name', self.name)

        if self.lang is not None:
            identity.setAttr('xml:lang', self.lang)
        return identity

    def __eq__(self, other: DiscoIdentity):
        return str(self) == str(other)

    def __ne__(self, other: DiscoIdentity):
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '%s/%s/%s/%s' % (self.category,
                                self.type,
                                self.lang or '',
                                self.name or '')

    def __hash__(self) -> int:
        return hash(str(self))


class AdHocCommand(NamedTuple):
    jid: JID
    node: Node
    name: Optional[str]
    sessionid: Optional[str] = None
    status: Optional[AdHocStatus] = None
    data: Optional[Node] = None
    actions: Optional[Set[AdHocAction]] = None
    default: Optional[AdHocAction] = None
    notes: Optional[list[AdHocCommandNote]] = None

    @property
    def is_completed(self) -> bool:
        return self.status == AdHocStatus.COMPLETED

    @property
    def is_canceled(self) -> bool:
        return self.status == AdHocStatus.CANCELED


class ProxyData(NamedTuple):
    type: str
    host: str
    username: Optional[str]
    password: Optional[str]

    def get_uri(self) -> str:
        if self.username is not None:
            user_pass = Soup.uri_encode('%s:%s' % (self.username,
                                                   self.password))
            return '%s://%s@%s' % (self.type,
                                   user_pass,
                                   self.host)
        return '%s://%s' % (self.type, self.host)

    def get_resolver(self) -> Gio.SimpleProxyResolver:
        return Gio.SimpleProxyResolver.new(self.get_uri(), None)


class OMEMOBundle(NamedTuple):
    spk: dict[str, Union[int, bytes]]
    spk_signature: bytes
    ik: bytes
    otpks: list[dict[str, str]]

    def pick_prekey(self) -> dict[str, str]:
        return random.SystemRandom().choice(self.otpks)


class ChatMarker(NamedTuple):
    type: str
    id: str

    @property
    def is_received(self) -> bool:
        return self.type == 'received'

    @property
    def is_displayed(self) -> bool:
        return self.type == 'displayed'

    @property
    def is_acknowledged(self) -> bool:
        return self.type == 'acknowledged'


class CommonError:
    def __init__(self, stanza):
        self._stanza_name = stanza.getName()
        self._error_node = stanza.getTag('error')
        self.condition = stanza.getError()
        self.condition_data = self._error_node.getTagData(self.condition)
        self.app_condition = stanza.getAppError()
        self.type = stanza.getErrorType()
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text = {}

        text_elements = self._error_node.getTags('text', namespace=Namespace.STANZAS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.getData()
            self._text[lang] = text

    @classmethod
    def from_string(cls, node_string: Union[bytes, str]) -> CommonError:
        return cls(Protocol(node=node_string))

    def get_text(self, pref_lang=None):
        if pref_lang is not None:
            text = self._text.get(pref_lang)
            if text is not None:
                return text

        if self._text:
            text = self._text.get('en')
            if text is not None:
                return text

            text = self._text.get(None)
            if text is not None:
                return text
            return self._text.popitem()[1]
        return ''

    def set_text(self, lang, text):
        self._text[lang] = text

    def __str__(self):
        condition = self.condition
        if self.app_condition is not None:
            condition = '%s (%s)' % (self.condition, self.app_condition)
        text = self.get_text('en') or ''
        if text:
            text = ' - %s' % text
        return 'Error from %s: %s%s' % (self.jid, condition, text)

    def serialize(self) -> str:
        return str(Protocol(name=self._stanza_name,
                            frm=self.jid,
                            xmlns=Namespace.CLIENT,
                            attrs={'id': self.id},
                            payload=self._error_node))


class HTTPUploadError(CommonError):
    def __init__(self, stanza):
        CommonError.__init__(self, stanza)

    def get_max_file_size(self):
        if not self.app_condition == 'file-too-large':
            return None
        node = self._error_node.getTag(self.app_condition)
        try:
            return float(node.getTagData('max-file-size'))
        except Exception:
            return None

    def get_retry_date(self):
        if not self.app_condition == 'retry':
            return None
        return self._error_node.getTagAttr('stamp')


class StanzaMalformedError(CommonError):
    def __init__(self, stanza, text):
        self._error_node = None
        self.condition = 'stanza-malformed'
        self.condition_data = None
        self.app_condition = None
        self.type = None
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text = {}
        if text:
            self._text['en'] = text

    @classmethod
    def from_string(cls, node_string):
        raise NotImplementedError

    def __str__(self):
        text = self.get_text('en')
        if text:
            text = ': %s' % text
        return 'Received malformed stanza from %s%s' % (self.jid, text)

    def serialize(self):
        raise NotImplementedError


class StreamError(CommonError):
    def __init__(self, stanza):
        self.condition = stanza.getError()
        self.condition_data = self._error_node.getTagData(self.condition)
        self.app_condition = stanza.getAppError()
        self.type = stanza.getErrorType()
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text = {}

        text_elements = self._error_node.getTags('text', namespace=Namespace.STREAMS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.getData()
            self._text[lang] = text

    @classmethod
    def from_string(cls, node_string):
        raise NotImplementedError

    def __str__(self):
        text = self.get_text('en') or ''
        if text:
            text = ' - %s' % text
        return 'Error from %s: %s%s' % (self.jid, self.condition, text)

    def serialize(self):
        raise NotImplementedError


class TuneData(NamedTuple):
    artist: Optional[str] = None
    length: Optional[str] = None
    rating: Optional[str] = None
    source: Optional[str] = None
    title: Optional[str] = None
    track: Optional[str] = None
    uri: Optional[str] = None

    @property
    def was_removed(self) -> bool:
        return (self.artist is None and
                self.title is None and
                self.track is None)


class MAMData(NamedTuple):
    id: str
    query_id: str
    archive: JID
    namespace: str
    timestamp: datetime

    @property
    def is_ver_1(self) -> bool:
        return self.namespace == Namespace.MAM_1

    @property
    def is_ver_2(self) -> bool:
        return self.namespace == Namespace.MAM_2


class CarbonData(NamedTuple):
    type: str

    @property
    def is_sent(self) -> bool:
        return self.type == 'sent'

    @property
    def is_received(self) -> bool:
        return self.type == 'received'


class ReceiptData(NamedTuple):
    type: str
    id: Optional[str] = None

    @property
    def is_request(self) -> bool:
        return self.type == 'request'

    @property
    def is_received(self) -> bool:
        return self.type == 'received'


class Properties:
    pass


@dataclass
class MessageProperties:
    own_jid: JID
    carbon: Optional[CarbonData] = None
    type: MessageType = MessageType.NORMAL
    id: Optional[str] = None
    stanza_ids: list[StanzaIDData] = field(default_factory=list)
    from_: Optional[JID] = None
    to: Optional[JID] = None
    jid: Optional[JID] = None
    subject = None
    body: Optional[str] = None
    thread: Optional[str] = None
    user_timestamp = None
    timestamp: float = field(default_factory=time.time)
    has_server_delay: bool = False
    error = None
    eme: Optional[EMEData] = None
    http_auth: Optional[HTTPAuthData] = None
    nickname: Optional[str] = None
    from_muc: bool = False
    muc_jid: Optional[JID] = None
    muc_nickname: Optional[str] = None
    muc_status_codes: Optional[Set[StatusCode]] = None
    muc_private_message: bool = False
    muc_invite = None
    muc_decline = None
    muc_user = None
    muc_ofrom = None
    muc_subject: Optional[MucSubject] = None
    captcha: Optional[CaptchaData] = None
    voice_request: Optional[VoiceRequest] = None
    self_message: bool = False
    mam: Optional[MAMData] = None
    pubsub: bool = False
    pubsub_event: Optional[PubSubEventData] = None
    openpgp = None
    omemo = None
    encrypted = None
    pgp_legacy = None
    marker: Optional[ChatMarker] = None
    receipt: Optional[ReceiptData] = None
    oob: Optional[OOBData] = None
    correction: Optional[CorrectionData] = None
    moderation: Optional[ModerationData] = None
    attention: bool = False
    forms = None
    xhtml: Optional[str] = None
    security_label = None
    chatstate = None

    def is_from_us(self, bare_match: bool = True):
        if self.from_ is None:
            raise ValueError('from attribute missing')

        if bare_match:
            return self.own_jid.bare_match(self.from_)
        return self.own_jid == self.from_

    @property
    def has_user_delay(self) -> bool:
        return self.user_timestamp is not None

    @property
    def is_encrypted(self) -> bool:
        return self.encrypted is not None

    @property
    def is_omemo(self) -> bool:
        return self.omemo is not None

    @property
    def is_openpgp(self) -> bool:
        return self.openpgp is not None

    @property
    def is_pgp_legacy(self) -> bool:
        return self.pgp_legacy is not None

    @property
    def is_pubsub(self) -> bool:
        return self.pubsub

    @property
    def is_pubsub_event(self) -> bool:
        return self.pubsub_event is not None

    @property
    def is_carbon_message(self) -> bool:
        return self.carbon is not None

    @property
    def is_sent_carbon(self) -> bool:
        return self.carbon is not None and self.carbon.is_sent

    @property
    def is_received_carbon(self) -> bool:
        return self.carbon is not None and self.carbon.is_received

    @property
    def is_mam_message(self) -> bool:
        return self.mam is not None

    @property
    def is_http_auth(self) -> bool:
        return self.http_auth is not None

    @property
    def is_muc_subject(self) -> bool:
        return (self.type == MessageType.GROUPCHAT and
                self.body is None and
                self.subject is not None)

    @property
    def is_muc_config_change(self) -> bool:
        return bool(self.muc_status_codes)

    @property
    def is_muc_pm(self) -> bool:
        return self.muc_private_message

    @property
    def is_muc_invite_or_decline(self) -> bool:
        return (self.muc_invite is not None or
                self.muc_decline is not None)

    @property
    def is_captcha_challenge(self) -> bool:
        return self.captcha is not None

    @property
    def is_voice_request(self) -> bool:
        return self.voice_request is not None

    @property
    def is_self_message(self) -> bool:
        return self.self_message

    @property
    def is_marker(self) -> bool:
        return self.marker is not None

    @property
    def is_receipt(self) -> bool:
        return self.receipt is not None

    @property
    def is_oob(self) -> bool:
        return self.oob is not None

    @property
    def is_correction(self) -> bool:
        return self.correction is not None

    @property
    def is_moderation(self) -> bool:
        return self.moderation is not None

    @property
    def has_attention(self) -> bool:
        return self.attention

    @property
    def has_forms(self) -> bool:
        return self.forms is not None

    @property
    def has_xhtml(self) -> bool:
        return self.xhtml is not None

    @property
    def has_security_label(self) -> bool:
        return self.security_label is not None

    @property
    def has_chatstate(self) -> bool:
        return self.chatstate is not None


@dataclass
class IqProperties:
    own_jid: JID
    type: Optional[IqType] = None
    jid: Optional[JID] = None
    id: Optional[str] = None
    error: Optional[Any] = None
    query: Optional[Node] = None
    payload: Optional[Node] = None
    http_auth: Optional[HTTPAuthData] = None
    ibb: Optional[IBBData] = None
    blocking: Optional[BlockingPush] = None
    roster: Optional[RosterPush] = None

    @property
    def is_http_auth(self) -> bool:
        return self.http_auth is not None

    @property
    def is_ibb(self) -> bool:
        return self.ibb is not None

    @property
    def is_blocking(self) -> bool:
        return self.blocking is not None

    @property
    def is_roster(self) -> bool:
        return self.roster is not None


class IqPropertiesBase(typing.Protocol):
    own_jid: JID
    type: IqType
    jid: JID
    id: str
    error: Optional[Any]
    query: Optional[Node]
    payload: Optional[Node]


class BlockingProperties(IqPropertiesBase):

    blocking: BlockingPush

    @property
    def is_blocking(self) -> bool: ...


@dataclass
class PresenceProperties:
    own_jid: JID
    type: Optional[PresenceType] = None
    priority: Optional[int] = None
    show: Optional[PresenceShow] = None
    jid: Optional[JID] = None
    resource: Optional[str] = None
    id: Optional[str] = None
    nickname: Optional[str] = None
    self_presence: bool = False
    self_bare: bool = False
    from_muc: bool = False
    status: str = ''
    timestamp: float = field(default_factory=time.time)
    user_timestamp: Optional[float] = None
    idle_timestamp: Optional[float] = None
    signed: Optional[Any] = None
    error: Optional[Any] = None
    avatar_sha: Optional[str] = None
    avatar_state: AvatarState = AvatarState.IGNORE
    muc_jid: Optional[JID] = None
    muc_status_codes: Optional[Set[StatusCode]] = None
    muc_user: Optional[MucUserData] = None
    muc_nickname: Optional[str] = None
    muc_destroyed: Optional[MucDestroyed] = None
    entity_caps: Optional[EntityCapsData] = None

    @property
    def is_self_presence(self) -> bool:
        return self.self_presence

    @property
    def is_self_bare(self) -> bool:
        return self.self_bare

    @property
    def is_muc_destroyed(self) -> bool:
        return self.muc_destroyed is not None

    @property
    def is_muc_self_presence(self) -> bool:
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.SELF in self.muc_status_codes)

    @property
    def is_nickname_modified(self) -> bool:
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.NICKNAME_MODIFIED in self.muc_status_codes and
                self.type == PresenceType.AVAILABLE)

    @property
    def is_nickname_changed(self) -> bool:
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.NICKNAME_CHANGE in self.muc_status_codes and
                self.muc_user.nick is not None and
                self.type == PresenceType.UNAVAILABLE)

    @property
    def new_jid(self) -> JID:
        if not self.is_nickname_changed:
            raise ValueError('This is not a nickname change')
        return self.jid.new_with(resource=self.muc_user.nick)

    @property
    def is_kicked(self) -> bool:
        status_codes = {
            StatusCode.REMOVED_BANNED,
            StatusCode.REMOVED_KICKED,
            StatusCode.REMOVED_AFFILIATION_CHANGE,
            StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY,
            StatusCode.REMOVED_SERVICE_SHUTDOWN,
            StatusCode.REMOVED_ERROR
        }
        return (self.from_muc and
                self.muc_status_codes is not None and
                bool(status_codes.intersection(self.muc_status_codes)) and
                self.type == PresenceType.UNAVAILABLE)

    @property
    def is_muc_shutdown(self) -> bool:
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.REMOVED_SERVICE_SHUTDOWN in self.muc_status_codes)

    @property
    def is_new_room(self) -> bool:
        status_codes = {
            StatusCode.CREATED,
            StatusCode.SELF
        }
        return (self.from_muc and
                self.muc_status_codes is not None and
                status_codes.issubset(self.muc_status_codes))

    @property
    def affiliation(self) -> Optional[Affiliation]:
        try:
            return self.muc_user.affiliation
        except Exception:
            return None

    @property
    def role(self) -> Optional[Role]:
        try:
            return self.muc_user.role
        except Exception:
            return None


class XHTMLData:
    def __init__(self, xhtml: Node):
        self._bodys: dict[Optional[str], Node] = {}
        for body in xhtml.getTags('body', namespace=Namespace.XHTML):
            lang = body.getXmlLang()
            self._bodys[lang] = body

    def get_body(self, pref_lang: Optional[str] = None) -> str:
        if pref_lang is not None:
            body = self._bodys.get(pref_lang)
            if body is not None:
                return str(body)

        body = self._bodys.get('en')
        if body is not None:
            return str(body)

        body = self._bodys.get(None)
        if body is not None:
            return str(body)
        return str(self._bodys.popitem()[1])
