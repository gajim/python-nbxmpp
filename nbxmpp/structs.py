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

import time
from collections import namedtuple

from nbxmpp.protocol import JID
from nbxmpp.protocol import NS_STANZAS
from nbxmpp.protocol import NS_MAM_1
from nbxmpp.protocol import NS_MAM_2
from nbxmpp.const import MessageType
from nbxmpp.const import AvatarState
from nbxmpp.const import StatusCode
from nbxmpp.const import PresenceType
from nbxmpp.const import Error

StanzaHandler = namedtuple('StanzaHandler',
                           'name callback typ ns xmlns system priority')
StanzaHandler.__new__.__defaults__ = ('', '', None, False, 50)

InviteData = namedtuple('InviteData',
                        'muc from_ reason password type continued thread')

DeclineData = namedtuple('DeclineData', 'muc from_ reason')

CaptchaData = namedtuple('CaptchaData', 'form bob_data')

BobData = namedtuple('BobData', 'algo hash_ max_age data cid type')

VoiceRequest = namedtuple('VoiceRequest', 'form')

MucUserData = namedtuple('MucUserData', 'affiliation jid nick role actor reason')
MucUserData.__new__.__defaults__ = (None, None, None, None, None)

MucDestroyed = namedtuple('MucDestroyed', 'alternate reason password')
MucDestroyed.__new__.__defaults__ = (None, None, None)

EntityCapsData = namedtuple('EntityCapsData', 'hash node ver')
EntityCapsData.__new__.__defaults__ = (None, None, None)

HTTPAuthData = namedtuple('HTTPAuthData', 'id method url body')
HTTPAuthData.__new__.__defaults__ = (None, None, None, None)

StanzaIDData = namedtuple('StanzaIDData', 'id by')
StanzaIDData.__new__.__defaults__ = (None, None)

PubSubEventData = namedtuple('PubSubEventData', 'node id item data')

MoodData = namedtuple('MoodData', 'mood text')

ActivityData = namedtuple('ActivityData', 'activity subactivity text')


class MAMData(namedtuple('MAMData', 'id query_id archive namespace timestamp')):

    __slots__ = []

    @property
    def is_ver_1(self):
        return self.namespace == NS_MAM_1

    @property
    def is_ver_2(self):
        return self.namespace == NS_MAM_2


class Properties:
    pass


class MessageProperties:
    def __init__(self):
        self.carbon_type = None
        self.type = MessageType.NORMAL
        self.id = None
        self.stanza_id = None
        self.jid = None
        self.subject = None
        self.body = None
        self.thread = None
        self.user_timestamp = None
        self.timestamp = time.time()
        self.error = None
        self.eme = None
        self.http_auth = None
        self.nickname = None
        self.from_muc = False
        self.muc_nickname = None
        self.muc_status_codes = None
        self.muc_private_message = False
        self.muc_invite = None
        self.muc_decline = None
        self.muc_user = None
        self.captcha = None
        self.voice_request = None
        self.self_message = False
        self.mam = None
        self.pubsub_event = None

    @property
    def is_pubsub_event(self):
        return self.pubsub_event is not None

    @property
    def is_mam_message(self):
        return self.mam is not None

    @property
    def is_http_auth(self):
        return self.http_auth is not None

    @property
    def is_muc_subject(self):
        return (self.type == MessageType.GROUPCHAT and
                self.body is None and
                self.subject is not None)

    @property
    def is_muc_config_change(self):
        return self.body is None and self.muc_status_codes

    @property
    def is_muc_pm(self):
        return self.muc_private_message

    @property
    def is_muc_invite_or_decline(self):
        return (self.muc_invite is not None or
                self.muc_decline is not None)

    @property
    def is_captcha_challenge(self):
        return self.captcha is not None

    @property
    def is_voice_request(self):
        return self.voice_request is not None

    @property
    def is_self_message(self):
        return self.self_message


class IqProperties:
    def __init__(self):
        self.type = None
        self.jid = None
        self.id = None
        self.error = None
        self.query = None
        self.payload = None
        self.http_auth = None

    @property
    def is_http_auth(self):
        return self.http_auth is not None


class PresenceProperties:
    def __init__(self):
        self.type = None
        self.priority = None
        self.show = None
        self.jid = None
        self.resource = None
        self.id = None
        self.payload = None
        self.query = None
        self.nickname = None
        self.self_presence = False
        self.self_bare = False
        self.from_muc = False
        self.status = ''
        self.timestamp = time.time()
        self.user_timestamp = None
        self.idle_timestamp = None
        self.signed = None
        self.error = None
        self.avatar_sha = None
        self.avatar_state = AvatarState.IGNORE
        self.muc_status_codes = None
        self.muc_user = None
        self.muc_nickname = None
        self.muc_destroyed = None
        self.entity_caps = None

    @property
    def is_self_presence(self):
        return self.self_presence

    @property
    def is_self_bare(self):
        return self.self_bare

    @property
    def is_muc_destroyed(self):
        return self.muc_destroyed is not None

    @property
    def is_muc_self_presence(self):
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.SELF in self.muc_status_codes)

    @property
    def is_nickname_changed(self):
        return (self.from_muc and
                self.muc_status_codes is not None and
                self.muc_user.nick is not None and
                StatusCode.NICKNAME_CHANGE in self.muc_status_codes and
                self.type == PresenceType.UNAVAILABLE)

    @property
    def new_jid(self):
        if not self.is_nickname_changed:
            raise ValueError('This is not a nickname change')
        jid = JID(self.jid)
        jid.setResource(self.muc_user.nick)
        return jid

    @property
    def is_kicked(self):
        status_codes = {
            StatusCode.REMOVED_BANNED,
            StatusCode.REMOVED_KICKED,
            StatusCode.REMOVED_AFFILIATION_CHANGE,
            StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY,
            StatusCode.REMOVED_ERROR
        }
        return (self.from_muc and
                self.muc_status_codes is not None and
                status_codes.intersection(self.muc_status_codes) and
                self.type == PresenceType.UNAVAILABLE)

    @property
    def is_muc_shutdown(self):
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.REMOVED_SERVICE_SHUTDOWN in self.muc_status_codes)

    @property
    def is_new_room(self):
        status_codes = {
            StatusCode.CREATED,
            StatusCode.SELF
        }
        return (self.from_muc and
                self.muc_status_codes is not None and
                status_codes.issubset(self.muc_status_codes))

    @property
    def affiliation(self):
        try:
            return self.muc_user.affiliation
        except Exception:
            return None

    @property
    def role(self):
        try:
            return self.muc_user.role
        except Exception:
            return None


class ErrorProperties:
    def __init__(self, stanza):
        for child in stanza.getTag('error').getChildren():
            if child.getNamespace() == NS_STANZAS:
                try:
                    self.type = Error(child.name)
                except ValueError:
                    self.type = Error('unknown-error')
                break
        self.legacy_code = stanza.getErrorCode()
        self.legacy_type = stanza.getErrorType()
        self.message = stanza.getErrorMsg()

    def __str__(self):
        return '%s %s' % (self.type, self.message)


class BaseResult:
    @property
    def is_error(self):
        return self.error is not None


class CommonResult(BaseResult, namedtuple('CommonResult', 'jid error')):
    pass

CommonResult.__new__.__defaults__ = (None,)


class AffiliationResult(BaseResult, namedtuple('AffiliationResult',
                                               'jid affiliation users error')):
    pass

AffiliationResult.__new__.__defaults__ = (None, None)


class MucConfigResult(BaseResult, namedtuple('MucConfigResult',
                                             'jid form error')):
    pass

MucConfigResult.__new__.__defaults__ = (None, None)


class BlockingListResult(BaseResult, namedtuple('BlockingListResult',
                                                'blocking_list error')):
    pass

BlockingListResult.__new__.__defaults__ = (None,)
