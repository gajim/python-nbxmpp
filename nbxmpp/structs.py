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

import time
import random
from collections import namedtuple

from gi.repository import Soup
from gi.repository import Gio

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Protocol
from nbxmpp.protocol import Node
from nbxmpp.const import MessageType
from nbxmpp.const import AvatarState
from nbxmpp.const import StatusCode
from nbxmpp.const import PresenceType
from nbxmpp.const import LOCATION_DATA
from nbxmpp.const import AdHocStatus

StanzaHandler = namedtuple('StanzaHandler',
                           'name callback typ ns xmlns priority')
StanzaHandler.__new__.__defaults__ = ('', '', None, 50)

CommonResult = namedtuple('CommonResult', 'jid')
CommonResult.__new__.__defaults__ = (None,)

InviteData = namedtuple('InviteData',
                        'muc from_ reason password type continued thread')

DeclineData = namedtuple('DeclineData', 'muc from_ reason')

CaptchaData = namedtuple('CaptchaData', 'form bob_data')

BobData = namedtuple('BobData', 'algo hash_ max_age data cid type')

VoiceRequest = namedtuple('VoiceRequest', 'form jid nick')

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

PubSubEventData = namedtuple('PubSubEventData', 'node id item data deleted retracted purged')
PubSubEventData.__new__.__defaults__ = (None, None, None, False, False, False)

MoodData = namedtuple('MoodData', 'mood text')

BlockingPush = namedtuple('BlockingPush', 'block unblock unblock_all')

ActivityData = namedtuple('ActivityData', 'activity subactivity text')

LocationData = namedtuple('LocationData', LOCATION_DATA)
LocationData.__new__.__defaults__ = (None,) * len(LocationData._fields)

BookmarkData = namedtuple('BookmarkData', 'jid name nick autojoin password')
BookmarkData.__new__.__defaults__ = (None, None, None, None)

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

OOBData = namedtuple('OOBData', 'url desc')

CorrectionData = namedtuple('CorrectionData', 'id')

RegisterData = namedtuple('RegisterData', 'instructions form fields_form oob_url bob_data')

HTTPUploadData = namedtuple('HTTPUploadData', 'put_uri get_uri headers')
HTTPUploadData.__new__.__defaults__ = (None,)

RSMData = namedtuple('RSMData', 'after before last first first_index count max index')

MAMQueryData = namedtuple('MAMQueryData', 'jid rsm complete')

MAMPreferencesData = namedtuple('MAMPreferencesData', 'default always never')


class DiscoInfo(namedtuple('DiscoInfo', 'stanza identities features dataforms timestamp')):

    __slots__ = []

    def __new__(cls, stanza, identities, features, dataforms, timestamp=None):
        return super(DiscoInfo, cls).__new__(cls, stanza, identities,
                                             features, dataforms, timestamp)

    def get_caps_hash(self):
        try:
            return self.node.split('#')[1]
        except Exception:
            return None

    def has_field(self, form_type, var):
        for dataform in self.dataforms:
            try:
                if dataform['FORM_TYPE'].value != form_type:
                    continue
                if var in dataform.vars:
                    return True

            except Exception:
                continue
        return False

    def get_field_value(self, form_type, var):
        for dataform in self.dataforms:
            try:
                if dataform['FORM_TYPE'].value != form_type:
                    continue

                if dataform[var].type_ == 'jid-multi':
                    return dataform[var].values or None
                return dataform[var].value or None

            except Exception:
                continue

    def supports(self, feature):
        return feature in self.features

    def serialize(self):
        if self.stanza is None:
            raise ValueError('Unable to serialize DiscoInfo, no stanza found')
        return str(self.stanza)

    @property
    def node(self):
        try:
            query = self.stanza.getQuery()
        except Exception:
            return None

        if query is not None:
            return query.getAttr('node')
        return None

    @property
    def jid(self):
        try:
            return self.stanza.getFrom()
        except Exception:
            return None

    @property
    def mam_namespace(self):
        if Namespace.MAM_2 in self.features:
            return Namespace.MAM_2
        if Namespace.MAM_1 in self.features:
            return Namespace.MAM_1
        return None

    @property
    def has_mam_2(self):
        return Namespace.MAM_2 in self.features

    @property
    def has_mam_1(self):
        return Namespace.MAM_1 in self.features

    @property
    def has_mam(self):
        return self.has_mam_1 or self.has_mam_2

    @property
    def has_httpupload(self):
        return Namespace.HTTPUPLOAD_0 in self.features

    @property
    def is_muc(self):
        for identity in self.identities:
            if identity.category == 'conference':
                if Namespace.MUC in self.features:
                    return True
        return False

    @property
    def muc_name(self):
        if self.muc_room_name:
            return self.muc_room_name

        if self.muc_identity_name:
            return self.muc_identity_name

        if self.jid is not None:
            return self.jid.localpart
        return None

    @property
    def muc_identity_name(self):
        for identity in self.identities:
            if identity.category == 'conference':
                return identity.name
        return None

    @property
    def muc_room_name(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roomconfig_roomname')

    @property
    def muc_description(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_description')

    @property
    def muc_log_uri(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_logs')

    @property
    def muc_users(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_occupants')

    @property
    def muc_contacts(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_contactjid')

    @property
    def muc_subject(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_subject')

    @property
    def muc_subjectmod(self):
        # muc#roominfo_changesubject stems from a wrong example in the MUC XEP
        # Ejabberd and Prosody use this value
        return (self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_subjectmod') or
                self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_changesubject'))

    @property
    def muc_lang(self):
        return self.get_field_value(Namespace.MUC_INFO, 'muc#roominfo_lang')

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

    @property
    def is_gateway(self):
        for identity in self.identities:
            if identity.category == 'gateway':
                return True
        return False

    @property
    def gateway_name(self):
        for identity in self.identities:
            if identity.category == 'gateway':
                return identity.name
        return None

    @property
    def gateway_type(self):
        for identity in self.identities:
            if identity.category == 'gateway':
                return identity.type
        return None

    def has_category(self, category):
        for identity in self.identities:
            if identity.category == category:
                return True
        return False

    @property
    def httpupload_max_file_size(self):
        size = self.get_field_value(Namespace.HTTPUPLOAD_0, 'max-file-size')
        try:
            return float(size)
        except Exception:
            return None


class DiscoIdentity(namedtuple('DiscoIdentity', 'category type name lang')):

    __slots__ = []

    def __new__(cls, category, type, name=None, lang=None):
        return super(DiscoIdentity, cls).__new__(cls, category, type, name, lang)

    def get_node(self):
        identity = Node('identity',
                        attrs={'category': self.category,
                               'type': self.type})
        if self.name is not None:
            identity.setAttr('name', self.name)

        if self.lang is not None:
            identity.setAttr('xml:lang', self.lang)
        return identity

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


class AdHocCommand(namedtuple('AdHocCommand', 'jid node name sessionid status data actions default notes')):

    __slots__ = []

    def __new__(cls, jid, node, name, sessionid=None, status=None,
                data=None, actions=None, default=None, notes=None):
        return super(AdHocCommand, cls).__new__(cls, jid, node, name, sessionid,
                                                status, data, actions, default, notes)

    @property
    def is_completed(self):
        return self.status == AdHocStatus.COMPLETED

    @property
    def is_canceled(self):
        return self.status == AdHocStatus.CANCELED


class ProxyData(namedtuple('ProxyData', 'type host username password')):

    __slots__ = []

    def get_uri(self):
        if self.username is not None:
            user_pass = Soup.uri_encode('%s:%s' % (self.username,
                                                   self.password))
            return '%s://%s@%s' % (self.type,
                                   user_pass,
                                   self.host)
        return '%s://%s' % (self.type, self.host)

    def get_resolver(self):
        return Gio.SimpleProxyResolver.new(self.get_uri(), None)


class OMEMOBundle(namedtuple('OMEMOBundle', 'spk spk_signature ik otpks')):
    def pick_prekey(self):
        return random.SystemRandom().choice(self.otpks)


class ChatMarker(namedtuple('ChatMarker', 'type id')):

    @property
    def is_received(self):
        return self.type == 'received'

    @property
    def is_displayed(self):
        return self.type == 'displayed'

    @property
    def is_acknowledged(self):
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
    def from_string(cls, node_string):
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

    def serialize(self):
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
        return self.namespace == Namespace.MAM_1

    @property
    def is_ver_2(self):
        return self.namespace == Namespace.MAM_2


class CarbonData(namedtuple('MAMData', 'type')):

    __slots__ = []

    @property
    def is_sent(self):
        return self.type == 'sent'

    @property
    def is_received(self):
        return self.type == 'received'


class ReceiptData(namedtuple('ReceiptData', 'type id')):

    __slots__ = []

    def __new__(cls, type, id=None):
        return super(ReceiptData, cls).__new__(cls, type, id)

    @property
    def is_request(self):
        return self.type == 'request'

    @property
    def is_received(self):
        return self.type == 'received'


class Properties:
    pass


class MessageProperties:
    def __init__(self, own_jid):
        self._own_jid = own_jid
        self.carbon = None
        self.type = MessageType.NORMAL
        self.id = None
        self.stanza_id = None
        self.from_ = None
        self.to = None
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
        self.marker = None
        self.receipt = None
        self.oob = None
        self.correction = None
        self.attention = False
        self.forms = None
        self.xhtml = None
        self.security_label = None
        self.chatstate = None

    def is_from_us(self, bare_match=True):
        if self.from_ is None:
            raise ValueError('from attribute missing')

        if bare_match:
            return self._own_jid.bare_match(self.from_)
        return self._own_jid == self.from_

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
    def is_carbon_message(self):
        return self.carbon is not None

    @property
    def is_sent_carbon(self):
        return self.carbon is not None and self.carbon.is_sent

    @property
    def is_received_carbon(self):
        return self.carbon is not None and self.carbon.is_received

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

    @property
    def is_marker(self):
        return self.marker is not None

    @property
    def is_receipt(self):
        return self.receipt is not None

    @property
    def is_oob(self):
        return self.oob is not None

    @property
    def is_correction(self):
        return self.correction is not None

    @property
    def has_attention(self):
        return self.attention

    @property
    def has_forms(self):
        return self.forms is not None

    @property
    def has_xhtml(self):
        return self.xhtml is not None

    @property
    def has_security_label(self):
        return self.security_label is not None

    @property
    def has_chatstate(self):
        return self.chatstate is not None


class IqProperties:
    def __init__(self, own_jid):
        self._own_jid = own_jid
        self.type = None
        self.jid = None
        self.id = None
        self.error = None
        self.query = None
        self.payload = None
        self.http_auth = None
        self.ibb = None
        self.blocking = None

    @property
    def is_http_auth(self):
        return self.http_auth is not None

    @property
    def is_ibb(self):
        return self.ibb is not None

    @property
    def is_blocking(self):
        return self.blocking is not None


class PresenceProperties:
    def __init__(self, own_jid):
        self._own_jid = own_jid
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
    def is_nickname_modified(self):
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.NICKNAME_MODIFIED in self.muc_status_codes and
                self.type == PresenceType.AVAILABLE)

    @property
    def is_nickname_changed(self):
        return (self.from_muc and
                self.muc_status_codes is not None and
                StatusCode.NICKNAME_CHANGE in self.muc_status_codes and
                self.muc_user.nick is not None and
                self.type == PresenceType.UNAVAILABLE)

    @property
    def new_jid(self):
        if not self.is_nickname_changed:
            raise ValueError('This is not a nickname change')
        return self.jid.new_with(resource=self.muc_user.nick)

    @property
    def is_kicked(self):
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


class XHTMLData:
    def __init__(self, xhtml):
        self._bodys = {}
        for body in xhtml.getTags('body', namespace=Namespace.XHTML):
            lang = body.getXmlLang()
            self._bodys[lang] = body

    def get_body(self, pref_lang=None):
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
