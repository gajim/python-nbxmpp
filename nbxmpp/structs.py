# Copyright (C) 2018-2020 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import typing
from typing import Any
from typing import NamedTuple
from typing import Optional
from typing import TYPE_CHECKING

import logging
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from gi.repository import Gio
from gi.repository import GLib

from nbxmpp import exceptions
from nbxmpp.const import AdHocAction
from nbxmpp.const import AdHocNoteType
from nbxmpp.const import AdHocStatus
from nbxmpp.const import Affiliation
from nbxmpp.const import AnonymityMode
from nbxmpp.const import AvatarState
from nbxmpp.const import Chatstate
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.const import InviteType
from nbxmpp.const import IqType
from nbxmpp.const import MessageType
from nbxmpp.const import PresenceShow
from nbxmpp.const import PresenceType
from nbxmpp.const import Role
from nbxmpp.const import StatusCode
from nbxmpp.language import LanguageMap
from nbxmpp.language import LanguageRange
from nbxmpp.language import LanguageTag
from nbxmpp.modules.dataforms import DataForm
from nbxmpp.modules.fallback import FallbacksForT
from nbxmpp.modules.fallback import strip_fallback
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.protocol import Protocol
from nbxmpp.simplexml import Node

if TYPE_CHECKING:
    from nbxmpp.modules.security_labels import SecurityLabel

log = logging.getLogger("nbxmpp.structs")


class StanzaHandler(NamedTuple):
    name: str
    callback: Any
    typ: str = ""
    ns: str = ""
    xmlns: str | None = None
    priority: int = 50


class CommonResult(NamedTuple):
    jid: JID | None = None


class InviteData(NamedTuple):
    muc: JID
    from_: JID
    reason: str | None
    password: str | None
    type: InviteType
    continued: bool
    thread: str | None


class DeclineData(NamedTuple):
    muc: JID
    from_: JID
    reason: str | None


class CaptchaData(NamedTuple):
    form: Any
    bob_data: BobData


class BobData(NamedTuple):
    algo: str
    hash_: str
    max_age: int
    data: bytes
    cid: str
    type: str


class BookmarkData(NamedTuple):
    jid: JID
    name: str | None = None
    nick: str | None = None
    autojoin: bool = False
    password: str | None = None
    extensions: Node | None = None


class VoiceRequest(NamedTuple):
    jid: JID
    nick: str
    form: Any


class MucUserData(NamedTuple):
    jid: JID | None
    affiliation: Affiliation | None
    nick: str | None
    role: Role | None
    actor: str | None
    reason: str | None


class MucDestroyed(NamedTuple):
    alternate: JID | None
    reason: str | None
    password: str | None


class MucConfigResult(NamedTuple):
    jid: JID
    form: Optional[Any] = None


class MucSubject(NamedTuple):
    text: str
    author: str | None
    timestamp: float | None


class AffiliationResult(NamedTuple):
    jid: JID
    users: dict[JID, dict[str, str]]


class EntityCapsData(NamedTuple):
    hash: str
    node: str
    ver: str


class HTTPAuthData(NamedTuple):
    id: str | None
    method: str | None
    url: str | None
    body: str | None


class StanzaIDData(NamedTuple):
    id: str
    by: str


class PubSubEventData(NamedTuple):
    node: str
    id: str | None = None
    item: Node | None = None
    data: Optional[Any] = None
    deleted: bool = False
    retracted: bool = False
    purged: bool = False


class MoodData(NamedTuple):
    mood: str
    test: str


class BlockingPush(NamedTuple):
    block: set[JID]
    unblock: set[JID]
    unblock_all: bool


class ActivityData(NamedTuple):
    activity: str
    subactivity: str
    text: str


class LocationData(NamedTuple):
    accuracy: str | None = None
    alt: str | None = None
    altaccuracy: str | None = None
    area: str | None = None
    bearing: str | None = None
    building: str | None = None
    country: str | None = None
    countrycode: str | None = None
    datum: str | None = None
    description: str | None = None
    error: str | None = None
    floor: str | None = None
    lat: str | None = None
    locality: str | None = None
    lon: str | None = None
    postalcode: str | None = None
    region: str | None = None
    room: str | None = None
    speed: str | None = None
    street: str | None = None
    text: str | None = None
    timestamp: str | None = None
    tzo: str | None = None
    uri: str | None = None


class PGPPublicKey(NamedTuple):
    jid: JID
    key: bytes
    date: float


class PGPKeyMetadata(NamedTuple):
    jid: JID
    fingerprint: str
    date: float


class OMEMOMessage(NamedTuple):
    sid: int
    iv: bytes
    keys: dict[int, tuple[bytes, bool]]
    payload: bytes


class AnnotationNote(NamedTuple):
    jid: JID
    data: str
    cdate: datetime | None = None
    mdate: datetime | None = None


class EMEData(NamedTuple):
    name: str
    namespace: str


class MuclumbusResult(NamedTuple):
    first: str | None
    last: str | None
    max: int | None
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
    os: str | None


class AdHocCommandNote(NamedTuple):
    text: str
    type: AdHocNoteType


class IBBData(NamedTuple):
    type: str
    sid: str
    block_size: int | None = None
    seq: int | None = None
    data: bytes | None = None


class OOBData(NamedTuple):
    url: str
    desc: str


class CorrectionData(NamedTuple):
    id: str


class ReplyData(NamedTuple):
    to: JID
    id: str


class ModerationData(NamedTuple):
    stanza_id: str
    by: JID | None
    reason: str | None
    stamp: datetime
    is_tombstone: bool
    occupant_id: str | None


class RetractionData(NamedTuple):
    id: str | None
    is_tombstone: bool
    timestamp: float | None


class DiscoItems(NamedTuple):
    jid: JID
    node: str
    items: list[DiscoItem]


class DiscoItem(NamedTuple):
    jid: JID
    name: str | None
    node: str | None


class RegisterData(NamedTuple):
    instructions: str | None
    form: Optional[Any]
    fields_form: Optional[Any]
    oob_url: str | None
    bob_data: BobData | None


class HTTPUploadData(NamedTuple):
    put_uri: str
    get_uri: str
    headers: dict[str, str]


class RSMData(NamedTuple):
    after: str | None
    before: str | None
    last: str | None
    first: str | None
    first_index: int | None
    count: int | None
    max: int | None
    index: int | None


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
    items: list[RosterItem] | None
    version: str | None


class RosterPush(NamedTuple):
    item: RosterItem
    version: str


class ServerAddress(NamedTuple):
    domain: str | None
    service: str | None
    host: str | None
    uri: str | None
    protocol: ConnectionProtocol
    type: ConnectionType
    proxy: ProxyData | None

    @property
    def is_service(self) -> bool:
        return self.service is not None

    @property
    def is_host(self) -> bool:
        return self.host is not None

    @property
    def is_uri(self) -> bool:
        return self.uri is not None

    def has_proxy(self) -> bool:
        return self.proxy is not None


@dataclass
class RosterItem:
    jid: JID
    name: str | None = None
    ask: str | None = None
    subscription: str | None = None
    approved: str | None = None
    groups: set[str] = field(default_factory=set)

    @classmethod
    def from_node(cls, node: Node) -> RosterItem:
        attrs = node.getAttrs(copy=True)
        jid = attrs.get("jid")
        if jid is None:
            raise Exception("jid attribute missing")

        jid = JID.from_string(jid)
        if jid.is_full:
            raise Exception("full jid in roster not allowed")

        groups = {group.getData() for group in node.getTags("group")}

        return cls(
            jid=jid,
            name=attrs.get("name"),
            ask=attrs.get("ask"),
            subscription=attrs.get("subscription") or "none",
            approved=attrs.get("approved"),
            groups=groups,
        )

    def asdict(self) -> dict[str, Any]:
        return {
            "jid": self.jid,
            "name": self.name,
            "ask": self.ask,
            "subscription": self.subscription,
            "approved": self.approved,
            "groups": self.groups,
        }


class DiscoInfo(NamedTuple):
    stanza: Iq | None
    identities: list[DiscoIdentity]
    features: list[str]
    dataforms: list[DataForm]
    timestamp: float | None = None

    def get_caps_hash(self) -> str | None:
        try:
            return self.node.split("#")[1]
        except Exception:
            return None

    def has_field(self, form_type: str, var: str) -> bool:
        for dataform in self.dataforms:
            try:
                if dataform["FORM_TYPE"].value != form_type:
                    continue
                if var in dataform.vars:
                    return True

            except Exception:
                continue
        return False

    def get_field_value(self, form_type: str, var: str) -> Optional[Any]:
        for dataform in self.dataforms:
            try:
                if dataform["FORM_TYPE"].value != form_type:
                    continue

                if dataform[var].type_ == "jid-multi":
                    return dataform[var].values or None
                return dataform[var].value

            except Exception:
                continue

        return None

    def supports(self, feature: str) -> bool:
        return feature in self.features

    def serialize(self) -> str:
        if self.stanza is None:
            raise ValueError("Unable to serialize DiscoInfo, no stanza found")
        return str(self.stanza)

    @property
    def node(self) -> str | None:
        try:
            query = self.stanza.getQuery()
        except Exception:
            return None

        if query is not None:
            return query.getAttr("node")
        return None

    @property
    def jid(self) -> JID | None:
        try:
            return self.stanza.getFrom()
        except Exception:
            return None

    @property
    def mam_namespace(self) -> str | None:
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
        return (
            Namespace.MESSAGE_MODERATE in self.features
            or Namespace.MESSAGE_MODERATE_1 in self.features
        )

    @property
    def moderation_namespace(self) -> str | None:
        if Namespace.MESSAGE_MODERATE_1 in self.features:
            return Namespace.MESSAGE_MODERATE_1
        if Namespace.MESSAGE_MODERATE in self.features:
            return Namespace.MESSAGE_MODERATE
        return None

    @property
    def is_muc(self) -> bool:
        for identity in self.identities:
            if identity.category == "conference":
                if Namespace.MUC in self.features:
                    return True
        return False

    @property
    def is_irc(self) -> bool:
        for identity in self.identities:
            if identity.category == "conference" and identity.type == "irc":
                return True
        return False

    @property
    def muc_name(self) -> str | None:
        if self.muc_room_name:
            return self.muc_room_name

        if self.muc_identity_name:
            return self.muc_identity_name

        if self.jid is not None:
            return self.jid.localpart
        return None

    @property
    def muc_identity_name(self) -> str | None:
        for identity in self.identities:
            if identity.category == "conference":
                return identity.name
        return None

    @property
    def muc_room_name(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roomconfig_roomname")

    @property
    def muc_description(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_description")

    @property
    def muc_log_uri(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_logs")

    @property
    def muc_users(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_occupants")

    @property
    def muc_contacts(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_contactjid")

    @property
    def muc_subject(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_subject")

    @property
    def muc_subjectmod(self) -> Optional[Any]:
        # muc#roominfo_changesubject stems from a wrong example in the MUC XEP
        # Ejabberd and Prosody use this value
        # muc#roomconfig_changesubject is also used by Prosody
        return (
            self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_subjectmod")
            or self.get_field_value(Namespace.MUC_INFO, "muc#roomconfig_changesubject")
            or self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_changesubject")
        )

    @property
    def muc_lang(self) -> Optional[Any]:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roominfo_lang")

    @property
    def muc_allows_invites(self) -> bool | None:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roomconfig_allowinvites")

    @property
    def prosody_allow_member_invites(self) -> bool | None:
        return self.get_field_value(
            Namespace.MUC_INFO,
            r"{http://prosody.im/protocol/muc}roomconfig_allowmemberinvites",
        )

    @property
    def roomconfig_allowpm(self) -> str | None:
        return self.get_field_value(Namespace.MUC_INFO, "muc#roomconfig_allowpm")

    @property
    def muc_is_persistent(self) -> bool:
        return "muc_persistent" in self.features

    @property
    def muc_is_moderated(self) -> bool:
        return "muc_moderated" in self.features

    @property
    def muc_is_open(self) -> bool:
        return "muc_open" in self.features

    @property
    def muc_is_members_only(self) -> bool:
        return "muc_membersonly" in self.features

    @property
    def muc_is_hidden(self) -> bool:
        return "muc_hidden" in self.features

    @property
    def muc_is_nonanonymous(self) -> bool:
        return "muc_nonanonymous" in self.features

    @property
    def muc_is_passwordprotected(self) -> bool:
        return "muc_passwordprotected" in self.features

    @property
    def muc_is_public(self) -> bool:
        return "muc_public" in self.features

    @property
    def muc_is_semianonymous(self) -> bool:
        return "muc_semianonymous" in self.features

    @property
    def muc_is_temporary(self) -> bool:
        return "muc_temporary" in self.features

    @property
    def muc_is_unmoderated(self) -> bool:
        return "muc_unmoderated" in self.features

    @property
    def muc_is_unsecured(self) -> bool:
        return "muc_unsecured" in self.features

    @property
    def is_gateway(self) -> bool:
        return any(identity.category == "gateway" for identity in self.identities)

    @property
    def gateway_name(self) -> str | None:
        for identity in self.identities:
            if identity.category == "gateway":
                return identity.name
        return None

    @property
    def gateway_type(self) -> str | None:
        for identity in self.identities:
            if identity.category == "gateway":
                return identity.type
        return None

    def has_category(self, category: str) -> bool:
        return any(identity.category == category for identity in self.identities)

    def has_identity(self, category: str, type_: str) -> bool:
        for identity in self.identities:
            if identity.category == category and identity.type == type_:
                return True
        return False

    @property
    def httpupload_max_file_size(self) -> float | None:
        size = self.get_field_value(Namespace.HTTPUPLOAD_0, "max-file-size")
        try:
            return float(size)
        except Exception:
            return None


class DiscoIdentity(NamedTuple):

    category: str
    type: str
    name: str | None = None
    lang: str | None = None

    def get_node(self) -> Node:
        identity = Node(
            "identity", attrs={"category": self.category, "type": self.type}
        )
        if self.name is not None:
            identity.setAttr("name", self.name)

        if self.lang is not None:
            identity.setAttr("xml:lang", self.lang)
        return identity

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return "%s/%s/%s/%s" % (
            self.category,
            self.type,
            self.lang or "",
            self.name or "",
        )

    def __hash__(self) -> int:
        return hash(str(self))


class AdHocCommand(NamedTuple):
    jid: JID
    node: Node
    name: str | None
    sessionid: str | None = None
    status: AdHocStatus | None = None
    data: Node | None = None
    actions: set[AdHocAction] | None = None
    default: AdHocAction | None = None
    notes: list[AdHocCommandNote] | None = None

    @property
    def is_completed(self) -> bool:
        return self.status == AdHocStatus.COMPLETED

    @property
    def is_canceled(self) -> bool:
        return self.status == AdHocStatus.CANCELED


class ProxyData(NamedTuple):
    type: str
    host: str
    username: str | None
    password: str | None

    def get_uri(self) -> str:
        if self.username is not None:
            username = GLib.uri_escape_string(self.username, None, False)
            password = GLib.uri_escape_string(self.password, None, False)
            user_pass = f"{username}:{password}"
            return "%s://%s@%s" % (self.type, user_pass, self.host)
        return "%s://%s" % (self.type, self.host)

    def get_resolver(self) -> Gio.SimpleProxyResolver:
        return Gio.SimpleProxyResolver.new(self.get_uri(), None)


class OMEMOBundle(NamedTuple):
    spk: dict[str, int | bytes]
    spk_signature: bytes
    ik: bytes
    otpks: list[dict[str, str]]
    device_id: int = -1
    namespace: str = Namespace.OMEMO_TEMP

    def pick_prekey(self) -> dict[str, str]:
        return random.SystemRandom().choice(self.otpks)


class ChatMarker(NamedTuple):
    type: str
    id: str

    @property
    def is_received(self) -> bool:
        return self.type == "received"

    @property
    def is_displayed(self) -> bool:
        return self.type == "displayed"

    @property
    def is_acknowledged(self) -> bool:
        return self.type == "acknowledged"


class Reactions(NamedTuple):
    id: str
    emojis: set[str]


class CommonError:
    def __init__(self, stanza: Protocol) -> None:
        self._stanza_name = stanza.getName()
        self._error_node = stanza.getTag("error")
        self.condition = stanza.getError()
        self.condition_data = self._error_node.getTagData(self.condition)
        self.app_condition = stanza.getAppError()
        self.type = stanza.getErrorType()
        self.by = None
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text: dict[str, str] = {}

        by = self._error_node.getAttr("by")
        if by is not None:
            try:
                self.by = JID.from_string(by)
            except Exception:
                pass

        text_elements = self._error_node.getTags("text", namespace=Namespace.STANZAS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.getData()
            self._text[lang] = text

    @classmethod
    def from_string(cls, node_string: bytes | str) -> CommonError:
        return cls(Protocol(node=node_string))

    def get_text(self, pref_lang: str | None = None) -> str:
        if pref_lang is not None:
            text = self._text.get(pref_lang)
            if text is not None:
                return text

        if self._text:
            text = self._text.get("en")
            if text is not None:
                return text

            text = self._text.get(None)
            if text is not None:
                return text
            return self._text.popitem()[1]
        return ""

    def set_text(self, lang: str, text: str) -> None:
        self._text[lang] = text

    def __str__(self) -> str:
        condition = self.condition
        if self.app_condition is not None:
            condition = "%s (%s)" % (self.condition, self.app_condition)
        text = self.get_text("en") or ""
        if text:
            text = " - %s" % text
        return "Error from %s: %s%s" % (self.jid, condition, text)

    def serialize(self) -> str:
        return str(
            Protocol(
                name=self._stanza_name,
                frm=self.jid,
                xmlns=Namespace.CLIENT,
                attrs={"id": self.id},
                payload=self._error_node,
            )
        )


class HTTPUploadError(CommonError):
    def __init__(self, stanza: Protocol) -> None:
        CommonError.__init__(self, stanza)

    def get_max_file_size(self) -> float | None:
        if not self.app_condition == "file-too-large":
            return None
        node = self._error_node.getTag(self.app_condition)
        try:
            return float(node.getTagData("max-file-size"))
        except Exception:
            return None

    def get_retry_date(self):
        if not self.app_condition == "retry":
            return None
        return self._error_node.getTagAttr("stamp")


class StanzaMalformedError(CommonError):
    def __init__(self, stanza: Protocol, text: str | None) -> None:
        self._error_node = None
        self.condition = "stanza-malformed"
        self.condition_data = None
        self.app_condition = None
        self.type = None
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text: dict[str, str] = {}
        if text:
            self._text["en"] = text

    @classmethod
    def from_string(cls, node_string: str) -> Any:
        raise NotImplementedError

    def __str__(self) -> str:
        text = self.get_text("en")
        if text:
            text = ": %s" % text
        return "Received malformed stanza from %s%s" % (self.jid, text)

    def serialize(self) -> str:
        raise NotImplementedError


class StreamError(CommonError):
    def __init__(self, stanza: Protocol) -> None:
        self.condition = stanza.getError()
        self.condition_data = self._error_node.getTagData(self.condition)
        self.app_condition = stanza.getAppError()
        self.type = stanza.getErrorType()
        self.jid = stanza.getFrom()
        self.id = stanza.getID()
        self._text: dict[str, str] = {}

        text_elements = self._error_node.getTags("text", namespace=Namespace.STREAMS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.getData()
            self._text[lang] = text

    @classmethod
    def from_string(cls, node_string: str) -> Any:
        raise NotImplementedError

    def __str__(self) -> str:
        text = self.get_text("en") or ""
        if text:
            text = " - %s" % text
        return "Error from %s: %s%s" % (self.jid, self.condition, text)

    def serialize(self) -> str:
        raise NotImplementedError


class TuneData(NamedTuple):
    artist: str | None = None
    length: str | None = None
    rating: str | None = None
    source: str | None = None
    title: str | None = None
    track: str | None = None
    uri: str | None = None

    @property
    def was_removed(self) -> bool:
        return self.artist is None and self.title is None and self.track is None


class MAMData(NamedTuple):
    id: str
    query_id: str
    archive: JID
    namespace: str
    timestamp: float

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
        return self.type == "sent"

    @property
    def is_received(self) -> bool:
        return self.type == "received"


class ReceiptData(NamedTuple):
    type: str
    id: str | None = None

    @property
    def is_request(self) -> bool:
        return self.type == "request"

    @property
    def is_received(self) -> bool:
        return self.type == "received"


@dataclass
class Hat:
    uri: str
    title: str


class HatData:
    def __init__(self) -> None:
        self._hat_map = LanguageMap()

    def add_hat(self, hat: Hat, lang: str | None) -> None:
        language_tag = LanguageTag(tag=lang) if lang else None
        if language_tag not in self._hat_map:
            self._hat_map[language_tag] = []
        self._hat_map[language_tag].append(hat)

    def get_hats(
        self, language_range: Sequence[LanguageRange] | None = None
    ) -> list[Hat]:

        if language_range is None:
            return self._hat_map.any()

        try:
            return self._hat_map.lookup(language_range)
        except KeyError:
            return self._hat_map.any()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HatData):
            return False
        return self._hat_map == other._hat_map

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


@dataclass
class EncryptionData:
    protocol: str
    key: str | None
    trust: int


class Properties:
    pass


@dataclass
class MessageProperties:
    own_jid: JID
    carbon: CarbonData | None = None
    type: MessageType = MessageType.NORMAL
    id: str | None = None
    stanza_ids: list[StanzaIDData] = field(default_factory=list)
    origin_id: str | None = None
    from_: JID | None = None
    to: JID | None = None
    jid: JID | None = None
    remote_jid: JID | None = None
    subject: str | None = None
    body: str | None = None
    bodies: BodyData | None = None
    thread: str | None = None
    user_timestamp: float | None = None
    timestamp: float = field(default_factory=time.time)
    has_server_delay: bool = False
    error = None
    eme: EMEData | None = None
    http_auth: HTTPAuthData | None = None
    nickname: str | None = None
    from_muc: bool = False
    occupant_id: str | None = None
    muc_jid: JID | None = None
    muc_nickname: str | None = None
    muc_status_codes: set[StatusCode] | None = None
    muc_private_message: bool = False
    muc_invite: InviteData | None = None
    muc_decline: DeclineData | None = None
    muc_user: MucUserData | None = None
    muc_ofrom: JID | None = None
    muc_subject: MucSubject | None = None
    captcha: CaptchaData | None = None
    voice_request: VoiceRequest | None = None
    self_message: bool = False
    mam: MAMData | None = None
    pubsub: bool = False
    pubsub_event: PubSubEventData | None = None
    openpgp: bytes | None = None
    omemo: OMEMOMessage | None = None
    encrypted: EncryptionData | None = None
    pgp_legacy: str | None = None
    marker: ChatMarker | None = None
    receipt: ReceiptData | None = None
    oob: OOBData | None = None
    correction: CorrectionData | None = None
    reply_data: ReplyData | None = None
    moderation: ModerationData | None = None
    retraction: RetractionData | None = None
    attention: bool = False
    forms = None
    xhtml: XHTMLData | None = None
    security_label: SecurityLabel | None = None
    chatstate: Chatstate | None = None
    reactions: Reactions | None = None

    def is_from_us(self, bare_match: bool = True) -> bool:
        if self.from_ is None:
            raise ValueError("from attribute missing")

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
        return (
            self.type == MessageType.GROUPCHAT
            and self.body is None
            and self.subject is not None
        )

    @property
    def is_muc_config_change(self) -> bool:
        return bool(self.muc_status_codes)

    @property
    def is_muc_pm(self) -> bool:
        return self.muc_private_message

    @property
    def is_muc_invite_or_decline(self) -> bool:
        return self.muc_invite is not None or self.muc_decline is not None

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
    def is_retraction(self) -> bool:
        return self.retraction is not None

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
    type: IqType | None = None
    jid: JID | None = None
    id: str | None = None
    error: Optional[Any] = None
    query: Node | None = None
    payload: Node | None = None
    http_auth: HTTPAuthData | None = None
    ibb: IBBData | None = None
    blocking: BlockingPush | None = None
    roster: RosterPush | None = None

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
    query: Node | None
    payload: Node | None


class BlockingProperties(IqPropertiesBase):

    blocking: BlockingPush

    @property
    def is_blocking(self) -> bool: ...


@dataclass
class PresenceProperties:
    own_jid: JID
    type: PresenceType | None = None
    priority: int | None = None
    show: PresenceShow | None = None
    jid: JID | None = None
    resource: str | None = None
    id: str | None = None
    nickname: str | None = None
    self_presence: bool = False
    self_bare: bool = False
    from_muc: bool = False
    occupant_id: str | None = None
    status: str = ""
    timestamp: float = field(default_factory=time.time)
    user_timestamp: float | None = None
    idle_timestamp: float | None = None
    signed: Optional[Any] = None
    error: Optional[Any] = None
    avatar_sha: str | None = None
    avatar_state: AvatarState = AvatarState.IGNORE
    muc_jid: JID | None = None
    muc_status_codes: set[StatusCode] | None = None
    muc_user: MucUserData | None = None
    muc_nickname: str | None = None
    muc_destroyed: MucDestroyed | None = None
    entity_caps: EntityCapsData | None = None
    hats: HatData | None = None

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
        return (
            self.from_muc
            and self.muc_status_codes is not None
            and StatusCode.SELF in self.muc_status_codes
        )

    @property
    def is_nickname_modified(self) -> bool:
        return (
            self.from_muc
            and self.muc_status_codes is not None
            and StatusCode.NICKNAME_MODIFIED in self.muc_status_codes
            and self.type == PresenceType.AVAILABLE
        )

    @property
    def is_nickname_changed(self) -> bool:
        return (
            self.from_muc
            and self.muc_status_codes is not None
            and StatusCode.NICKNAME_CHANGE in self.muc_status_codes
            and self.muc_user.nick is not None
            and self.type == PresenceType.UNAVAILABLE
        )

    @property
    def new_jid(self) -> JID:
        if not self.is_nickname_changed:
            raise ValueError("This is not a nickname change")
        return self.jid.new_with(resource=self.muc_user.nick)

    @property
    def is_kicked(self) -> bool:
        status_codes = {
            StatusCode.REMOVED_BANNED,
            StatusCode.REMOVED_KICKED,
            StatusCode.REMOVED_AFFILIATION_CHANGE,
            StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY,
            StatusCode.REMOVED_SERVICE_SHUTDOWN,
            StatusCode.REMOVED_ERROR,
        }
        return (
            self.from_muc
            and self.muc_status_codes is not None
            and bool(status_codes.intersection(self.muc_status_codes))
            and self.type == PresenceType.UNAVAILABLE
        )

    @property
    def is_muc_shutdown(self) -> bool:
        return (
            self.from_muc
            and self.muc_status_codes is not None
            and StatusCode.REMOVED_SERVICE_SHUTDOWN in self.muc_status_codes
        )

    @property
    def is_new_room(self) -> bool:
        status_codes = {StatusCode.CREATED, StatusCode.SELF}
        return (
            self.from_muc
            and self.muc_status_codes is not None
            and status_codes.issubset(self.muc_status_codes)
        )

    @property
    def affiliation(self) -> Affiliation | None:
        try:
            return self.muc_user.affiliation
        except Exception:
            return None

    @property
    def role(self) -> Role | None:
        try:
            return self.muc_user.role
        except Exception:
            return None


class XHTMLData:
    def __init__(self, xhtml: Node) -> None:
        self._bodys: dict[str | None, Node] = {}
        for body in xhtml.getTags("body", namespace=Namespace.XHTML):
            lang = body.getXmlLang()
            self._bodys[lang] = body

    def get_body(self, pref_lang: str | None = None) -> str:
        if pref_lang is not None:
            body = self._bodys.get(pref_lang)
            if body is not None:
                return str(body)

        body = self._bodys.get("en")
        if body is not None:
            return str(body)

        body = self._bodys.get(None)
        if body is not None:
            return str(body)
        return str(self._bodys.popitem()[1])


@dataclass
class ChannelBindingData:
    type: Gio.TlsChannelBindingType
    data: bytes


@dataclass
class MDSData:
    jid: JID
    stanza_id: str
    stanza_id_by: JID


@dataclass
class BodyData:
    def __init__(
        self,
        stanza: Node,
        fallbacks_for: FallbacksForT | None = None,
        fallback_ns: set[str] | None = None,
    ) -> None:

        self._body_map = LanguageMap()
        self._fallbacks_for = fallbacks_for
        self._fallback_ns = fallback_ns

        for body in stanza.getTags("body"):
            lang = body.getAttr("xml:lang")
            lang_tag = LanguageTag(tag=lang) if lang else None
            self._body_map[lang_tag] = (lang, body.getData())

    def get(
        self,
        language_range: Sequence[LanguageRange] | None,
    ) -> str:

        if not self._body_map:
            return ""

        if language_range is None:
            lang, text = self._body_map.any()

        else:
            try:
                lang, text = self._body_map.lookup(language_range)
            except KeyError:
                lang, text = self._body_map.any()

        if not self._fallbacks_for or not self._fallback_ns:
            return text

        try:
            return strip_fallback(self._fallbacks_for, self._fallback_ns, lang, text)
        except exceptions.FallbackLanguageError:
            log.warning("Missing fallback for language: %s", lang)
            return text
