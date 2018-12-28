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

from nbxmpp.const import MessageType
from nbxmpp.const import AvatarState

StanzaHandler = namedtuple('StanzaHandler',
                           'name callback typ ns xmlns system priority')
StanzaHandler.__new__.__defaults__ = ('', '', None, False, 50)

InviteData = namedtuple('InviteData',
                        'muc from_ reason password type continued thread')

DeclineData = namedtuple('DeclineData', 'muc from_ reason')

CaptchaData = namedtuple('CaptchaData', 'form bob_data')

BobData = namedtuple('BobData', 'algo hash_ max_age data cid type')

VoiceRequest = namedtuple('VoiceRequest', 'form')


class Properties:
    pass


class MessageProperties:
    def __init__(self):
        self.carbon_type = None
        self.type = MessageType.NORMAL
        self.id = None
        self.jid = None
        self.subject = None
        self.body = None
        self.thread = None
        self.user_timestamp = None
        self.timestamp = time.time()
        self.error_code = None
        self.error_message = None
        self.eme = None
        self.http_auth = None
        self.nickname = None
        self.from_muc = False
        self.muc_nickname = None
        self.muc_status_codes = None
        self.muc_private_message = False
        self.muc_invite = None
        self.muc_decline = None
        self.captcha = None
        self.voice_request = None

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


class IqProperties:
    def __init__(self):
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
        self.nickname = None
        self.self_presence = False
        self.from_muc = False
        self.status = ''
        self.timestamp = time.time()
        self.user_timestamp = None
        self.idle_timestamp = None
        self.signed = None
        self.error_message = ''
        self.error_code = ''
        self.avatar_sha = None
        self.avatar_state = AvatarState.IGNORE


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
