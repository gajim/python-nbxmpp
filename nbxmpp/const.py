# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from enum import Enum
from enum import IntEnum
from functools import total_ordering

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Soup
from packaging.version import Version

GLIB_VERSION = Version(
    f"{GLib.MAJOR_VERSION}.{GLib.MINOR_VERSION}.{GLib.MICRO_VERSION}"
)


class IqType(Enum):
    GET = "get"
    SET = "set"
    RESULT = "result"
    ERROR = "error"

    @property
    def is_get(self) -> bool:
        return self == IqType.GET

    @property
    def is_set(self) -> bool:
        return self == IqType.SET

    @property
    def is_result(self) -> bool:
        return self == IqType.RESULT

    @property
    def is_error(self) -> bool:
        return self == IqType.ERROR


class MessageType(Enum):
    NORMAL = "normal"
    CHAT = "chat"
    GROUPCHAT = "groupchat"
    HEADLINE = "headline"
    ERROR = "error"

    @property
    def is_normal(self) -> bool:
        return self == MessageType.NORMAL

    @property
    def is_chat(self) -> bool:
        return self == MessageType.CHAT

    @property
    def is_groupchat(self) -> bool:
        return self == MessageType.GROUPCHAT

    @property
    def is_headline(self) -> bool:
        return self == MessageType.HEADLINE

    @property
    def is_error(self) -> bool:
        return self == MessageType.ERROR


class PresenceType(Enum):
    PROBE = "probe"
    SUBSCRIBE = "subscribe"
    SUBSCRIBED = "subscribed"
    AVAILABLE = None
    UNAVAILABLE = "unavailable"
    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBED = "unsubscribed"
    ERROR = "error"

    @property
    def is_available(self) -> bool:
        return self == PresenceType.AVAILABLE

    @property
    def is_unavailable(self) -> bool:
        return self == PresenceType.UNAVAILABLE

    @property
    def is_error(self) -> bool:
        return self == PresenceType.ERROR

    @property
    def is_probe(self) -> bool:
        return self == PresenceType.PROBE

    @property
    def is_unsubscribe(self) -> bool:
        return self == PresenceType.UNSUBSCRIBE

    @property
    def is_unsubscribed(self) -> bool:
        return self == PresenceType.UNSUBSCRIBED

    @property
    def is_subscribe(self) -> bool:
        return self == PresenceType.SUBSCRIBE

    @property
    def is_subscribed(self) -> bool:
        return self == PresenceType.SUBSCRIBED


@total_ordering
class PresenceShow(Enum):
    ONLINE = "online"
    CHAT = "chat"
    AWAY = "away"
    XA = "xa"
    DND = "dnd"

    @property
    def is_online(self) -> bool:
        return self == PresenceShow.ONLINE

    @property
    def is_chat(self) -> bool:
        return self == PresenceShow.CHAT

    @property
    def is_away(self) -> bool:
        return self == PresenceShow.AWAY

    @property
    def is_xa(self) -> bool:
        return self == PresenceShow.XA

    @property
    def is_dnd(self) -> bool:
        return self == PresenceShow.DND

    def __lt__(self, other: PresenceShow) -> bool:
        try:
            w1 = self._WEIGHTS[self]
            w2 = self._WEIGHTS[other]
        except KeyError:
            return NotImplemented
        return w1 < w2


PresenceShow._WEIGHTS = {
    PresenceShow.DND: 2,
    PresenceShow.CHAT: 1,
    PresenceShow.ONLINE: 0,
    PresenceShow.AWAY: -1,
    PresenceShow.XA: -2,
}


@total_ordering
class Chatstate(Enum):
    COMPOSING = "composing"
    PAUSED = "paused"
    ACTIVE = "active"
    INACTIVE = "inactive"
    GONE = "gone"

    @property
    def is_composing(self) -> bool:
        return self == Chatstate.COMPOSING

    @property
    def is_paused(self) -> bool:
        return self == Chatstate.PAUSED

    @property
    def is_active(self) -> bool:
        return self == Chatstate.ACTIVE

    @property
    def is_inactive(self) -> bool:
        return self == Chatstate.INACTIVE

    @property
    def is_gone(self) -> bool:
        return self == Chatstate.GONE

    def __lt__(self, other: Chatstate) -> bool:
        try:
            w1 = self._WEIGHTS[self]
            w2 = self._WEIGHTS[other]
        except KeyError:
            return NotImplemented
        return w1 < w2


Chatstate._WEIGHTS = {
    Chatstate.COMPOSING: 0,
    Chatstate.PAUSED: 1,
    Chatstate.ACTIVE: 2,
    Chatstate.INACTIVE: 3,
    Chatstate.GONE: 4,
}


class StatusCode(Enum):
    NON_ANONYMOUS = "100"
    AFFILIATION_CHANGE = "101"
    SHOWING_UNAVAILABLE = "102"
    NOT_SHOWING_UNAVAILABLE = "103"
    CONFIG_NON_PRIVACY_RELATED = "104"
    SELF = "110"
    CONFIG_ROOM_LOGGING = "170"
    CONFIG_NO_ROOM_LOGGING = "171"
    CONFIG_NON_ANONYMOUS = "172"
    CONFIG_SEMI_ANONYMOUS = "173"
    CONFIG_FULL_ANONYMOUS = "174"
    CREATED = "201"
    NICKNAME_MODIFIED = "210"
    REMOVED_BANNED = "301"
    NICKNAME_CHANGE = "303"
    REMOVED_KICKED = "307"
    REMOVED_AFFILIATION_CHANGE = "321"
    REMOVED_NONMEMBER_IN_MEMBERS_ONLY = "322"
    REMOVED_SERVICE_SHUTDOWN = "332"
    REMOVED_ERROR = "333"


class InviteType(Enum):
    MEDIATED = "mediated"
    DIRECT = "direct"


class AvatarState(Enum):
    IGNORE = "ignore"
    NOT_READY = "not ready"
    EMPTY = "empty"
    ADVERTISED = "advertised"


@total_ordering
class Affiliation(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    OUTCAST = "outcast"
    NONE = "none"

    @property
    def is_owner(self) -> bool:
        return self == Affiliation.OWNER

    @property
    def is_admin(self) -> bool:
        return self == Affiliation.ADMIN

    @property
    def is_member(self) -> bool:
        return self == Affiliation.MEMBER

    @property
    def is_outcast(self) -> bool:
        return self == Affiliation.OUTCAST

    @property
    def is_none(self) -> bool:
        return self == Affiliation.NONE

    def __lt__(self, other: Affiliation) -> bool:
        try:
            w1 = self._WEIGHTS[self]
            w2 = self._WEIGHTS[other]
        except KeyError:
            return NotImplemented
        return w1 < w2


Affiliation._WEIGHTS = {
    Affiliation.OWNER: 4,
    Affiliation.ADMIN: 3,
    Affiliation.MEMBER: 2,
    Affiliation.NONE: 1,
    Affiliation.OUTCAST: 0,
}


@total_ordering
class Role(Enum):
    MODERATOR = "moderator"
    PARTICIPANT = "participant"
    VISITOR = "visitor"
    NONE = "none"

    @property
    def is_moderator(self) -> bool:
        return self == Role.MODERATOR

    @property
    def is_participant(self) -> bool:
        return self == Role.PARTICIPANT

    @property
    def is_visitor(self) -> bool:
        return self == Role.VISITOR

    @property
    def is_none(self) -> bool:
        return self == Role.NONE

    def __lt__(self, other: Role) -> bool:
        try:
            w1 = self._WEIGHTS[self]
            w2 = self._WEIGHTS[other]
        except KeyError:
            return NotImplemented
        return w1 < w2


Role._WEIGHTS = {
    Role.MODERATOR: 3,
    Role.PARTICIPANT: 2,
    Role.VISITOR: 1,
    Role.NONE: 0,
}


class AnonymityMode(Enum):
    UNKNOWN = None
    SEMI = "semi"
    NONE = "none"


class AdHocStatus(Enum):
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELED = "canceled"


class AdHocAction(Enum):
    EXECUTE = "execute"
    CANCEL = "cancel"
    PREV = "prev"
    NEXT = "next"
    COMPLETE = "complete"


class AdHocNoteType(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class ConnectionType(Enum):
    DIRECT_TLS = "DIRECT TLS"
    START_TLS = "START TLS"
    PLAIN = "PLAIN"

    @property
    def is_direct_tls(self) -> bool:
        return self == ConnectionType.DIRECT_TLS

    @property
    def is_start_tls(self) -> bool:
        return self == ConnectionType.START_TLS

    @property
    def is_plain(self) -> bool:
        return self == ConnectionType.PLAIN


class ConnectionProtocol(IntEnum):
    TCP = 0
    WEBSOCKET = 1


class StreamState(Enum):
    RESOLVE = "resolve"
    RESOLVED = "resolved"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DISCONNECTING = "disconnecting"
    STREAM_START = "stream start"
    WAIT_FOR_STREAM_START = "wait for stream start"
    WAIT_FOR_FEATURES = "wait for features"
    WAIT_FOR_TLS_PROCEED = "wait for tls proceed"
    TLS_START_SUCCESSFUL = "tls start successful"
    PROCEED_WITH_AUTH = "proceed with auth"
    AUTH_SUCCESSFUL = "auth successful"
    AUTH_FAILED = "auth failed"
    WAIT_FOR_RESUMED = "wait for resumed"
    RESUME_FAILED = "resume failed"
    RESUME_SUCCESSFUL = "resume successful"
    PROCEED_WITH_BIND = "proceed with bind"
    BIND_SUCCESSFUL = "bind successful"
    WAIT_FOR_BIND = "wait for bind"
    WAIT_FOR_SESSION = "wait for session"
    ACTIVE = "active"


class StreamError(Enum):
    PARSING = 0
    CONNECTION_FAILED = 1
    SESSION = 2
    BIND = 3
    TLS = 4
    BAD_CERTIFICATE = 5
    STREAM = 6
    SASL = 7
    REGISTER = 8
    END = 9


class TCPState(Enum):
    DISCONNECTED = "disconnected"
    DISCONNECTING = "disconnecting"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class Mode(IntEnum):
    CLIENT = 0
    REGISTER = 1
    LOGIN_TEST = 2
    ANONYMOUS_TEST = 3

    @property
    def is_client(self) -> bool:
        return self == Mode.CLIENT

    @property
    def is_register(self) -> bool:
        return self == Mode.REGISTER

    @property
    def is_login_test(self) -> bool:
        return self == Mode.LOGIN_TEST

    @property
    def is_anonymous_test(self) -> bool:
        return self == Mode.ANONYMOUS_TEST


class HTTPRequestError(IntEnum):
    UNKNOWN = 0
    INCOMPLETE = 1
    STATUS_NOT_OK = 2
    CANCELLED = 3
    CONTENT_OVERFLOW = 4
    TIMEOUT = 5

    def __str__(self) -> str:
        return self.name


MOODS = [
    "afraid",
    "amazed",
    "amorous",
    "angry",
    "annoyed",
    "anxious",
    "aroused",
    "ashamed",
    "bored",
    "brave",
    "calm",
    "cautious",
    "cold",
    "confident",
    "confused",
    "contemplative",
    "contented",
    "cranky",
    "crazy",
    "creative",
    "curious",
    "dejected",
    "depressed",
    "disappointed",
    "disgusted",
    "dismayed",
    "distracted",
    "embarrassed",
    "envious",
    "excited",
    "flirtatious",
    "frustrated",
    "grateful",
    "grieving",
    "grumpy",
    "guilty",
    "happy",
    "hopeful",
    "hot",
    "humbled",
    "humiliated",
    "hungry",
    "hurt",
    "impressed",
    "in_awe",
    "in_love",
    "indignant",
    "interested",
    "intoxicated",
    "invincible",
    "jealous",
    "lonely",
    "lost",
    "lucky",
    "mean",
    "moody",
    "nervous",
    "neutral",
    "offended",
    "outraged",
    "playful",
    "proud",
    "relaxed",
    "relieved",
    "remorseful",
    "restless",
    "sad",
    "sarcastic",
    "satisfied",
    "serious",
    "shocked",
    "shy",
    "sick",
    "sleepy",
    "spontaneous",
    "stressed",
    "strong",
    "surprised",
    "thankful",
    "thirsty",
    "tired",
    "undefined",
    "weak",
    "worried",
]


ACTIVITIES = {
    "doing_chores": [
        "buying_groceries",
        "cleaning",
        "cooking",
        "doing_maintenance",
        "doing_the_dishes",
        "doing_the_laundry",
        "gardening",
        "running_an_errand",
        "walking_the_dog",
    ],
    "drinking": ["having_a_beer", "having_coffee", "having_tea"],
    "eating": ["having_a_snack", "having_breakfast", "having_dinner", "having_lunch"],
    "exercising": [
        "cycling",
        "dancing",
        "hiking",
        "jogging",
        "playing_sports",
        "running",
        "skiing",
        "swimming",
        "working_out",
    ],
    "grooming": [
        "at_the_spa",
        "brushing_teeth",
        "getting_a_haircut",
        "shaving",
        "taking_a_bath",
        "taking_a_shower",
    ],
    "having_appointment": [],
    "inactive": [
        "day_off",
        "hanging_out",
        "hiding",
        "on_vacation",
        "praying",
        "scheduled_holiday",
        "sleeping",
        "thinking",
    ],
    "relaxing": [
        "fishing",
        "gaming",
        "going_out",
        "partying",
        "reading",
        "rehearsing",
        "shopping",
        "smoking",
        "socializing",
        "sunbathing",
        "watching_tv",
        "watching_a_movie",
    ],
    "talking": ["in_real_life", "on_the_phone", "on_video_phone"],
    "traveling": [
        "commuting",
        "cycling",
        "driving",
        "in_a_car",
        "on_a_bus",
        "on_a_plane",
        "on_a_train",
        "on_a_trip",
        "walking",
    ],
    "working": ["coding", "in_a_meeting", "studying", "writing"],
}


LOCATION_DATA = [
    "accuracy",
    "alt",
    "altaccuracy",
    "area",
    "bearing",
    "building",
    "country",
    "countrycode",
    "datum",
    "description",
    "error",
    "floor",
    "lat",
    "locality",
    "lon",
    "postalcode",
    "region",
    "room",
    "speed",
    "street",
    "text",
    "timestamp",
    "tzo",
    "uri",
]


TUNE_DATA = ["artist", "length", "rating", "source", "title", "track", "uri"]


REGISTER_FIELDS = [
    "username",
    "nick",
    "password",
    "name",
    "first",
    "last",
    "email",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "url",
    "date",
]

GIO_TLS_ERRORS = {
    Gio.TlsCertificateFlags.UNKNOWN_CA: "The signing certificate authority is not known",
    Gio.TlsCertificateFlags.REVOKED: "The certificate has been revoked",
    Gio.TlsCertificateFlags.BAD_IDENTITY: "The certificate does not match the expected identity of the site",
    Gio.TlsCertificateFlags.INSECURE: "The certificate’s algorithm is insecure",
    Gio.TlsCertificateFlags.NOT_ACTIVATED: "The certificate’s activation time is in the future",
    Gio.TlsCertificateFlags.GENERIC_ERROR: "Unknown validation error",
    Gio.TlsCertificateFlags.EXPIRED: "The certificate has expired",
}

NOT_ALLOWED_XML_CHARS = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "\x0C": "",
    "\x1B": "",
}


SOUP_ENCODING: set[Soup.Encoding] = {
    Soup.Encoding.UNRECOGNIZED,
    Soup.Encoding.NONE,
    Soup.Encoding.CONTENT_LENGTH,
    Soup.Encoding.EOF,
    Soup.Encoding.CHUNKED,
    Soup.Encoding.BYTERANGES,
}
