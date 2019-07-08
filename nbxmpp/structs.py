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
import random
from collections import namedtuple

from nbxmpp.protocol import JID
from nbxmpp.protocol import NS_STANZAS
from nbxmpp.protocol import NS_MAM_1
from nbxmpp.protocol import NS_MAM_2
from nbxmpp.protocol import NS_MUC
from nbxmpp.protocol import NS_MUC_INFO
from nbxmpp.const import MessageType
from nbxmpp.const import AvatarState
from nbxmpp.const import StatusCode
from nbxmpp.const import PresenceType
from nbxmpp.const import Error
from nbxmpp.const import LOCATION_DATA
from nbxmpp.const import AdHocStatus

StanzaHandler = namedtuple('StanzaHandler',
                           'name callback typ ns xmlns system priority')
StanzaHandler.__new__.__defaults__ = ('', '', None, False, 50)

CommonResult = namedtuple('CommonResult', 'jid')
CommonResult.__new__.__defaults__ = (None,)

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

MucConfigResult = namedtuple('MucConfigResult', 'jid form')
MucConfigResult.__new__.__defaults__ = (None,)

AffiliationResult = namedtuple('AffiliationResult', 'jid users')

EntityCapsData = namedtuple('EntityCapsData', 'hash node ver')
EntityCapsData.__new__.__defaults__ = (None, None, None)

HTTPAuthData = namedtuple('HTTPAuthData', 'id method url body')
HTTPAuthData.__new__.__defaults__ = (None, None, None, None)

StanzaIDData = namedtuple('StanzaIDData', 'id by')
StanzaIDData.__new__.__defaults__ = (None, None)

PubSubEventData = namedtuple('PubSubEventData', 'node id item data empty deleted retracted')
PubSubEventData.__new__.__defaults__ = (None, None, None, False, False, False)

MoodData = namedtuple('MoodData', 'mood text')

ActivityData = namedtuple('ActivityData', 'activity subactivity text')

LocationData = namedtuple('LocationData', LOCATION_DATA)
LocationData.__new__.__defaults__ = (None,) * len(LocationData._fields)

AvatarMetaData = namedtuple('AvatarMetaData', 'bytes height width id type url')
AvatarMetaData.__new__.__defaults__ = (None,) * len(AvatarMetaData._fields)

AvatarData = namedtuple('AvatarData', 'jid sha data')
AvatarData.__new__.__defaults__ = (None,) * len(AvatarData._fields)

BookmarkData = namedtuple('BookmarkData', 'jid name nick autojoin password')
BookmarkData.__new__.__defaults__ = (None, None, None, None)

BlockingListResult = namedtuple('BlockingListResult', 'blocking_list')

PGPPublicKey = namedtuple('PGPPublicKey', 'jid key date')

PGPKeyMetadata = namedtuple('PGPKeyMetadata', 'jid fingerprint date')

OMEMOMessage = namedtuple('OMEMOMessage', 'sid iv keys payload')

AnnotationNote = namedtuple('AnnotationNote', 'jid data cdate mdate')
AnnotationNote.__new__.__defaults__ = (None, None)

EMEData = namedtuple('EMEData', 'name namespace')

MuclumbusResult = namedtuple('MuclumbusResult', 'first last max end items')

MuclumbusItem = namedtuple('MuclumbusItem', 'jid name nusers description language is_open anonymity_mode')

SoftwareVersionResult = namedtuple('SoftwareVersionResult', 'name version os')

AdHocCommandNote = namedtuple('AdHocCommandNote', 'text type')

IBBData = namedtuple('IBBData', 'block_size sid seq type data')
IBBData.__new__.__defaults__ = (None, None, None, None, None)

DiscoItems = namedtuple('DiscoItems', 'jid node items')
DiscoItem = namedtuple('DiscoItem', 'jid name node')
DiscoItem.__new__.__defaults__ = (None, None)


class DiscoInfo(namedtuple('DiscoInfo', 'jid node identities features dataforms')):

    __slots__ = []

    def __new__(cls, jid, node, identities, features, dataforms):
        return super(DiscoInfo, cls).__new__(cls, jid, node, identities,
                                             features, dataforms)

    def get_caps_hash(self):
        try:
            return self.node.split('#')[1]
        except Exception:
            return None

    def _get_form_value(self, form_type, var):
        for dataform in self.dataforms:
            try:
                is_info_form = dataform['FORM_TYPE'] != form_type
                if not is_info_form:
                    continue

                if dataform[var].type_ == 'jid-multi':
                    return dataform[var].values or None
                return dataform[var].value or None

            except Exception:
                continue

    @property
    def is_muc(self):
        for identity in self.identities:
            if identity.category == 'conference':
                if NS_MUC in self.features:
                    return True
        return False

    @property
    def muc_name(self):
        for identity in self.identities:
            if identity.category == 'conference':
                return identity.name

    @property
    def muc_description(self):
        return self._get_form_value(NS_MUC_INFO, 'muc#roominfo_description')

    @property
    def muc_log_uri(self):
        return self._get_form_value(NS_MUC_INFO, 'muc#roominfo_logs')

    @property
    def muc_users(self):
        return self._get_form_value(NS_MUC_INFO, 'muc#roominfo_occupants')

    @property
    def muc_contacts(self):
        return self._get_form_value(NS_MUC_INFO, 'muc#roominfo_contactjid')

    @property
    def muc_subject(self):
        return self._get_form_value(NS_MUC_INFO, 'muc#roominfo_subject')

    @property
    def muc_subjectmod(self):
        # muc#roominfo_changesubject stems from a wrong example in the MUC XEP
        # Ejabberd and Prosody use this value
        return (self._get_form_value(NS_MUC_INFO, 'muc#roominfo_subjectmod') or
                self._get_form_value(NS_MUC_INFO, 'muc#roominfo_changesubject'))

    @property
    def muc_lang(self):
        return self._get_form_value(NS_MUC_INFO, 'muc#roominfo_lang')

    @property
    def muc_has_mam(self):
        return NS_MAM_2 in self.features or NS_MAM_1 in self.features

    @property
    def muc_is_persistent(self):
        return 'muc_persistent' in self.features

    @property
    def muc_is_moderated(self):
        return 'muc_moderated' in self.features

    @property
    def muc_is_open(self):
        return 'muc_open' in self.features

    @property
    def muc_is_members_only(self):
        return 'muc_membersonly' in self.features

    @property
    def muc_is_hidden(self):
        return 'muc_hidden' in self.features

    @property
    def muc_is_nonanonymous(self):
        return 'muc_nonanonymous' in self.features

    @property
    def muc_is_passwordprotected(self):
        return 'muc_passwordprotected' in self.features

    @property
    def muc_is_public(self):
        return 'muc_public' in self.features

    @property
    def muc_is_semianonymous(self):
        return 'muc_semianonymous' in self.features

    @property
    def muc_is_temporary(self):
        return 'muc_temporary' in self.features

    @property
    def muc_is_unmoderated(self):
        return 'muc_unmoderated' in self.features

    @property
    def muc_is_unsecured(self):
        return 'muc_unsecured' in self.features


class DiscoIdentity(namedtuple('DiscoIdentity', 'category type name lang')):

    __slots__ = []

    def __new__(cls, category, type, name=None, lang=None):
        return super(DiscoIdentity, cls).__new__(cls, category, type, name, lang)

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return '%s/%s/%s/%s' % (self.category,
                                self.type,
                                self.lang or '',
                                self.name or '')

    def __hash__(self):
        return hash(str(self))


class AdHocCommand(namedtuple('AdHocCommand', 'jid node name sessionid status data actions notes')):

    __slots__ = []

    def __new__(cls, jid, node, name, sessionid=None, status=None,
                data=None, actions=None, notes=None):
        return super(AdHocCommand, cls).__new__(cls, jid, node, name, sessionid,
                                                status, data, actions, notes)

    @property
    def is_completed(self):
        return self.status == AdHocStatus.COMPLETED

    @property
    def is_canceled(self):
        return self.status == AdHocStatus.CANCELED


class OMEMOBundle(namedtuple('OMEMOBundle', 'spk spk_signature ik otpks')):
    def pick_prekey(self):
        return random.SystemRandom().choice(self.otpks)


class CommonError(namedtuple('CommonError', 'type message jid')):
    def __str__(self):
        if self.message is not None:
            return 'Error from %s %s: %s' % (self.jid, self.type, self.message)
        return 'Error from %s: %s' % (self.jid, self.type)


class TuneData(namedtuple('TuneData', 'artist length rating source title track uri')):

    __slots__ = []

    def __new__(cls, artist=None, length=None, rating=None, source=None,
                title=None, track=None, uri=None):
        return super(TuneData, cls).__new__(cls, artist, length, rating,
                                            source, title, track, uri)

    @property
    def was_removed(self):
        return (self.artist is None and
                self.title is None and
                self.track is None)


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
        self.has_server_delay = False
        self.error = None
        self.eme = None
        self.http_auth = None
        self.nickname = None
        self.from_muc = False
        self.muc_jid = None
        self.muc_nickname = None
        self.muc_status_codes = None
        self.muc_private_message = False
        self.muc_invite = None
        self.muc_decline = None
        self.muc_user = None
        self.muc_ofrom = None
        self.captcha = None
        self.voice_request = None
        self.self_message = False
        self.mam = None
        self.pubsub = False
        self.pubsub_event = None
        self.openpgp = None
        self.omemo = None
        self.encrypted = None
        self.pgp_legacy = None

    @property
    def has_user_delay(self):
        return self.user_timestamp is not None

    @property
    def is_encrypted(self):
        return self.encrypted is not None

    @property
    def is_omemo(self):
        return self.omemo is not None

    @property
    def is_openpgp(self):
        return self.openpgp is not None

    @property
    def is_pgp_legacy(self):
        return self.pgp_legacy is not None

    @property
    def is_pubsub(self):
        return self.pubsub

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
        self.ibb = None

    @property
    def is_http_auth(self):
        return self.http_auth is not None

    @property
    def is_ibb(self):
        return self.ibb is not None


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
        self.muc_jid = None
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
