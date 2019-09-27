# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from enum import Enum
from enum import IntEnum
from enum import unique
from functools import total_ordering


@unique
class Realm(Enum):
    CONNECTING = 'Connecting'

    def __str__(self):
        return self.value


@unique
class Event(Enum):
    AUTH_SUCCESSFUL = 'Auth successful'
    AUTH_FAILED = 'Auth failed'
    BIND_FAILED = 'Bind failed'
    SESSION_FAILED = 'Session failed'
    RESUME_SUCCESSFUL = 'Resume successful'
    RESUME_FAILED = 'Resume failed'
    CONNECTION_ACTIVE = 'Connection active'

    def __str__(self):
        return self.value


class GSSAPIState(IntEnum):
    STEP = 0
    WRAP = 1


class IqType(Enum):
    GET = 'get'
    SET = 'set'
    RESULT = 'result'
    ERROR = 'error'

    @property
    def is_get(self):
        return self == IqType.GET

    @property
    def is_set(self):
        return self == IqType.SET

    @property
    def is_result(self):
        return self == IqType.RESULT

    @property
    def is_error(self):
        return self == IqType.ERROR


class MessageType(Enum):
    NORMAL = 'normal'
    CHAT = 'chat'
    GROUPCHAT = 'groupchat'
    HEADLINE = 'headline'
    ERROR = 'error'

    @property
    def is_normal(self):
        return self == MessageType.NORMAL

    @property
    def is_chat(self):
        return self == MessageType.CHAT

    @property
    def is_groupchat(self):
        return self == MessageType.GROUPCHAT

    @property
    def is_headline(self):
        return self == MessageType.HEADLINE

    @property
    def is_error(self):
        return self == MessageType.ERROR


class PresenceType(Enum):
    PROBE = 'probe'
    SUBSCRIBE = 'subscribe'
    SUBSCRIBED = 'subscribed'
    AVAILABLE = None
    UNAVAILABLE = 'unavailable'
    UNSUBSCRIBE = 'unsubscribe'
    UNSUBSCRIBED = 'unsubscribed'
    ERROR = 'error'

    @property
    def is_available(self):
        return self == PresenceType.AVAILABLE

    @property
    def is_unavailable(self):
        return self == PresenceType.UNAVAILABLE

    @property
    def is_error(self):
        return self == PresenceType.ERROR

    @property
    def is_probe(self):
        return self == PresenceType.PROBE

    @property
    def is_unsubscribe(self):
        return self == PresenceType.UNSUBSCRIBE

    @property
    def is_unsubscribed(self):
        return self == PresenceType.UNSUBSCRIBED

    @property
    def is_subscribe(self):
        return self == PresenceType.SUBSCRIBE

    @property
    def is_subscribed(self):
        return self == PresenceType.SUBSCRIBED


@total_ordering
class PresenceShow(Enum):
    ONLINE = 'online'
    CHAT = 'chat'
    AWAY = 'away'
    XA = 'xa'
    DND = 'dnd'

    @property
    def is_online(self):
        return self == PresenceShow.ONLINE

    @property
    def is_chat(self):
        return self == PresenceShow.CHAT

    @property
    def is_away(self):
        return self == PresenceShow.AWAY

    @property
    def is_xa(self):
        return self == PresenceShow.XA

    @property
    def is_dnd(self):
        return self == PresenceShow.DND

    def __lt__(self, other):
        try:
            w1 = self._WEIGHTS[self]
            w2 = self._WEIGHTS[other]
        except KeyError:
            return NotImplemented
        return w1 < w2


PresenceShow._WEIGHTS = {
    PresenceShow.CHAT: 1,
    PresenceShow.ONLINE: 0,
    PresenceShow.AWAY: -1,
    PresenceShow.XA: -2,
    PresenceShow.DND: -3,
}


class StatusCode(Enum):
    NON_ANONYMOUS = '100'
    AFFILIATION_CHANGE = '101'
    SHOWING_UNAVAILABLE = '102'
    NOT_SHOWING_UNAVAILABLE = '103'
    CONFIG_NON_PRIVACY_RELATED = '104'
    SELF = '110'
    CONFIG_ROOM_LOGGING = '170'
    CONFIG_NO_ROOM_LOGGING = '171'
    CONFIG_NON_ANONYMOUS = '172'
    CONFIG_SEMI_ANONYMOUS = '173'
    CONFIG_FULL_ANONYMOUS = '174'
    CREATED = '201'
    NICKNAME_MODIFIED = '210'
    REMOVED_BANNED = '301'
    NICKNAME_CHANGE = '303'
    REMOVED_KICKED = '307'
    REMOVED_AFFILIATION_CHANGE = '321'
    REMOVED_NONMEMBER_IN_MEMBERS_ONLY = '322'
    REMOVED_SERVICE_SHUTDOWN = '332'
    REMOVED_ERROR = '333'


class InviteType(Enum):
    MEDIATED = 'mediated'
    DIRECT = 'direct'


class AvatarState(Enum):
    IGNORE = 'ignore'
    NOT_READY = 'not ready'
    EMPTY = 'empty'
    ADVERTISED = 'advertised'


@total_ordering
class Affiliation(Enum):
    OWNER = 'owner'
    ADMIN = 'admin'
    MEMBER = 'member'
    OUTCAST = 'outcast'
    NONE = 'none'

    @property
    def is_owner(self):
        return self == Affiliation.OWNER

    @property
    def is_admin(self):
        return self == Affiliation.ADMIN

    @property
    def is_member(self):
        return self == Affiliation.MEMBER

    @property
    def is_outcast(self):
        return self == Affiliation.OUTCAST

    @property
    def is_none(self):
        return self == Affiliation.NONE

    def __lt__(self, other):
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
    MODERATOR = 'moderator'
    PARTICIPANT = 'participant'
    VISITOR = 'visitor'
    NONE = 'none'

    @property
    def is_moderator(self):
        return self == Role.MODERATOR

    @property
    def is_participant(self):
        return self == Role.PARTICIPANT

    @property
    def is_visitor(self):
        return self == Role.VISITOR

    @property
    def is_none(self):
        return self == Role.NONE

    def __lt__(self, other):
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


class BookmarkStoreType(Enum):
    PUBSUB_BOOKMARK_2 = 'pubsub bookmark 2'
    PUBSUB_BOOKMARK_1 = 'pubsub bookmark 1'
    PRIVATE = 'private'


class AnonymityMode(Enum):
    UNKNOWN = None
    SEMI = 'semi'
    NONE = 'none'


class AdHocStatus(Enum):
    EXECUTING = 'executing'
    COMPLETED = 'completed'
    CANCELED = 'canceled'


class AdHocAction(Enum):
    EXECUTE = 'execute'
    CANCEL = 'cancel'
    PREV = 'prev'
    NEXT = 'next'
    COMPLETE = 'complete'


class AdHocNoteType(Enum):
    INFO = 'info'
    WARN = 'warn'
    ERROR = 'error'


MOODS = [
    'afraid',
    'amazed',
    'amorous',
    'angry',
    'annoyed',
    'anxious',
    'aroused',
    'ashamed',
    'bored',
    'brave',
    'calm',
    'cautious',
    'cold',
    'confident',
    'confused',
    'contemplative',
    'contented',
    'cranky',
    'crazy',
    'creative',
    'curious',
    'dejected',
    'depressed',
    'disappointed',
    'disgusted',
    'dismayed',
    'distracted',
    'embarrassed',
    'envious',
    'excited',
    'flirtatious',
    'frustrated',
    'grateful',
    'grieving',
    'grumpy',
    'guilty',
    'happy',
    'hopeful',
    'hot',
    'humbled',
    'humiliated',
    'hungry',
    'hurt',
    'impressed',
    'in_awe',
    'in_love',
    'indignant',
    'interested',
    'intoxicated',
    'invincible',
    'jealous',
    'lonely',
    'lost',
    'lucky',
    'mean',
    'moody',
    'nervous',
    'neutral',
    'offended',
    'outraged',
    'playful',
    'proud',
    'relaxed',
    'relieved',
    'remorseful',
    'restless',
    'sad',
    'sarcastic',
    'satisfied',
    'serious',
    'shocked',
    'shy',
    'sick',
    'sleepy',
    'spontaneous',
    'stressed',
    'strong',
    'surprised',
    'thankful',
    'thirsty',
    'tired',
    'undefined',
    'weak',
    'worried']


ACTIVITIES = {
    'doing_chores': [
        'buying_groceries',
        'cleaning',
        'cooking',
        'doing_maintenance',
        'doing_the_dishes',
        'doing_the_laundry',
        'gardening',
        'running_an_errand',
        'walking_the_dog'],
    'drinking': [
        'having_a_beer',
        'having_coffee',
        'having_tea'],
    'eating': [
        'having_a_snack',
        'having_breakfast',
        'having_dinner',
        'having_lunch'],
    'exercising': [
        'cycling',
        'dancing',
        'hiking',
        'jogging',
        'playing_sports',
        'running',
        'skiing',
        'swimming',
        'working_out'],
    'grooming': [
        'at_the_spa',
        'brushing_teeth',
        'getting_a_haircut',
        'shaving',
        'taking_a_bath',
        'taking_a_shower'],
    'having_appointment': [],
    'inactive': [
        'day_off',
        'hanging_out',
        'hiding',
        'on_vacation',
        'praying',
        'scheduled_holiday',
        'sleeping',
        'thinking'],
    'relaxing': [
        'fishing',
        'gaming',
        'going_out',
        'partying',
        'reading',
        'rehearsing',
        'shopping',
        'smoking',
        'socializing',
        'sunbathing',
        'watching_tv',
        'watching_a_movie'],
    'talking': [
        'in_real_life',
        'on_the_phone',
        'on_video_phone'],
    'traveling': [
        'commuting',
        'cycling',
        'driving',
        'in_a_car',
        'on_a_bus',
        'on_a_plane',
        'on_a_train',
        'on_a_trip',
        'walking'],
    'working': [
        'coding',
        'in_a_meeting',
        'studying',
        'writing']
}


LOCATION_DATA = [
    'accuracy',
    'alt',
    'altaccuracy',
    'area',
    'bearing',
    'building',
    'country',
    'countrycode',
    'datum',
    'description',
    'error',
    'floor',
    'lat',
    'locality',
    'lon',
    'postalcode',
    'region',
    'room',
    'speed',
    'street',
    'text',
    'timestamp',
    'tzo',
    'uri']


TUNE_DATA = [
    'artist',
    'length',
    'rating',
    'source',
    'title',
    'track',
    'uri']
