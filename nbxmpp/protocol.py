##   protocol.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

"""
Protocol module contains tools that are needed for processing of xmpp-related
data structures, including jabber-objects like JID or different stanzas and
sub- stanzas) handling routines
"""

import time
import hashlib
import functools
import warnings
from base64 import b64encode
from collections import namedtuple

from gi.repository import GLib

import idna
from precis_i18n import get_profile
from nbxmpp.simplexml import Node
from nbxmpp.namespaces import Namespace

def ascii_upper(s):
    return s.upper()

SASL_AUTH_MECHS = [
    'SCRAM-SHA-256-PLUS',
    'SCRAM-SHA-256',
    'SCRAM-SHA-1-PLUS',
    'SCRAM-SHA-1',
    'GSSAPI',
    'PLAIN',
    'EXTERNAL',
    'ANONYMOUS',
]

SASL_ERROR_CONDITIONS = [
    'aborted',
    'account-disabled',
    'credentials-expired',
    'encryption-required',
    'incorrect-encoding',
    'invalid-authzid',
    'invalid-mechanism',
    'mechanism-too-weak',
    'malformed-request',
    'not-authorized',
    'temporary-auth-failure',
]

ERRORS = {
    'urn:ietf:params:xml:ns:xmpp-sasl aborted': ['',
        '',
        'The receiving entity acknowledges an <abort/> element sent by the initiating entity; sent in reply to the <abort/> element.'],
    'urn:ietf:params:xml:ns:xmpp-sasl incorrect-encoding': ['',
        '',
        'The data provided by the initiating entity could not be processed because the [BASE64]Josefsson, S., The Base16, Base32, and Base64 Data Encodings, July 2003. encoding is incorrect (e.g., because the encoding does not adhere to the definition in Section 3 of [BASE64]Josefsson, S., The Base16, Base32, and Base64 Data Encodings, July 2003.); sent in reply to a <response/> element or an <auth/> element with initial response data.'],
    'urn:ietf:params:xml:ns:xmpp-sasl invalid-authzid': ['',
        '',
        'The authzid provided by the initiating entity is invalid, either because it is incorrectly formatted or because the initiating entity does not have permissions to authorize that ID; sent in reply to a <response/> element or an <auth/> element with initial response data.'],
    'urn:ietf:params:xml:ns:xmpp-sasl invalid-mechanism': ['',
        '',
        'The initiating entity did not provide a mechanism or requested a mechanism that is not supported by the receiving entity; sent in reply to an <auth/> element.'],
    'urn:ietf:params:xml:ns:xmpp-sasl mechanism-too-weak': ['',
        '',
        'The mechanism requested by the initiating entity is weaker than server policy permits for that initiating entity; sent in reply to a <response/> element or an <auth/> element with initial response data.'],
    'urn:ietf:params:xml:ns:xmpp-sasl not-authorized': ['',
        '',
        'The authentication failed because the initiating entity did not provide valid credentials (this includes but is not limited to the case of an unknown username); sent in reply to a <response/> element or an <auth/> element with initial response data.'],
    'urn:ietf:params:xml:ns:xmpp-sasl temporary-auth-failure': ['',
        '',
        'The authentication failed because of a temporary error condition within the receiving entity; sent in reply to an <auth/> element or <response/> element.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas bad-request': ['400',
        'modify',
        'The sender has sent XML that is malformed or that cannot be processed.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas conflict': ['409',
        'cancel',
        'Access cannot be granted because an existing resource or session exists with the same name or address.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas feature-not-implemented': ['501',
        'cancel',
        'The feature requested is not implemented by the recipient or server and therefore cannot be processed.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas forbidden': ['403',
        'auth',
        'The requesting entity does not possess the required permissions to perform the action.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas gone': ['302',
        'modify',
        'The recipient or server can no longer be contacted at this address.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas internal-server-error': ['500',
        'wait',
        'The server could not process the stanza because of a misconfiguration or an otherwise-undefined internal server error.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas item-not-found': ['404',
        'cancel',
        'The addressed JID or item requested cannot be found.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas jid-malformed': ['400',
        'modify',
        "The value of the        'to' attribute in the sender's stanza does not adhere to the syntax defined in Addressing Scheme."],
    'urn:ietf:params:xml:ns:xmpp-stanzas not-acceptable': ['406',
        'cancel',
        'The recipient or server understands the request but is refusing to process it because it does not meet criteria defined by the recipient or server.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas not-allowed': ['405',
        'cancel',
        'The recipient or server does not allow any entity to perform the action.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas not-authorized': ['401',
        'auth',
        'The sender must provide proper credentials before being allowed to perform the action, or has provided improper credentials.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas payment-required': ['402',
        'auth',
        'The requesting entity is not authorized to access the requested service because payment is required.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas recipient-unavailable': ['404',
        'wait',
        'The intended recipient is temporarily unavailable.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas redirect': ['302',
        'modify',
        'The recipient or server is redirecting requests for this information to another entity.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas registration-required': ['407',
        'auth',
        'The requesting entity is not authorized to access the requested service because registration is required.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas remote-server-not-found': ['404',
        'cancel',
        'A remote server or service specified as part or all of the JID of the intended recipient does not exist.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas remote-server-timeout': ['504',
        'wait',
        'A remote server or service specified as part or all of the JID of the intended recipient could not be contacted within a reasonable amount of time.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas resource-constraint': ['500',
        'wait',
        'The server or recipient lacks the system resources necessary to service the request.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas service-unavailable': ['503',
        'cancel',
        'The server or recipient does not currently provide the requested service.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas subscription-required': ['407',
        'auth',
        'The requesting entity is not authorized to access the requested service because a subscription is required.'],
    'urn:ietf:params:xml:ns:xmpp-stanzas undefined-condition': ['500',
        '',
        'Undefined Condition'],
    'urn:ietf:params:xml:ns:xmpp-stanzas unexpected-request': ['400',
        'wait',
        'The recipient or server understood the request but was not expecting it at this time (e.g., the request was out of order).'],
    'urn:ietf:params:xml:ns:xmpp-streams bad-format': ['',
        '',
        'The entity has sent XML that cannot be processed.'],
    'urn:ietf:params:xml:ns:xmpp-streams bad-namespace-prefix': ['',
        '',
        'The entity has sent a namespace prefix that is unsupported, or has sent no namespace prefix on an element that requires such a prefix.'],
    'urn:ietf:params:xml:ns:xmpp-streams conflict': ['',
        '',
        'The server is closing the active stream for this entity because a new stream has been initiated that conflicts with the existing stream.'],
    'urn:ietf:params:xml:ns:xmpp-streams connection-timeout': ['',
        '',
        'The entity has not generated any traffic over the stream for some period of time.'],
    'urn:ietf:params:xml:ns:xmpp-streams host-gone': ['',
        '',
        "The value of the        'to' attribute provided by the initiating entity in the stream header corresponds to a hostname that is no longer hosted by the server."],
    'urn:ietf:params:xml:ns:xmpp-streams host-unknown': ['',
        '',
        "The value of the        'to' attribute provided by the initiating entity in the stream header does not correspond to a hostname that is hosted by the server."],
    'urn:ietf:params:xml:ns:xmpp-streams improper-addressing': ['',
        '',
        "A stanza sent between two servers lacks a        'to' or 'from' attribute (or the attribute has no value)."],
    'urn:ietf:params:xml:ns:xmpp-streams internal-server-error': ['',
        '',
        'The server has experienced a misconfiguration or an otherwise-undefined internal error that prevents it from servicing the stream.'],
    'urn:ietf:params:xml:ns:xmpp-streams invalid-from': ['cancel',
        '',
        "The JID or hostname provided in a        'from' address does not match an authorized JID or validated domain negotiated between servers via SASL or dialback, or between a client and a server via authentication and resource authorization."],
    'urn:ietf:params:xml:ns:xmpp-streams invalid-id': ['',
        '',
        'The stream ID or dialback ID is invalid or does not match an ID previously provided.'],
    'urn:ietf:params:xml:ns:xmpp-streams invalid-namespace': ['',
        '',
        'The streams namespace name is something other than        "http://etherx.jabber.org/streams" or the dialback namespace name is something other than "jabber:server:dialback".'],
    'urn:ietf:params:xml:ns:xmpp-streams invalid-xml': ['',
        '',
        'The entity has sent invalid XML over the stream to a server that performs validation.'],
    'urn:ietf:params:xml:ns:xmpp-streams not-authorized': ['',
        '',
        'The entity has attempted to send data before the stream has been authenticated, or otherwise is not authorized to perform an action related to stream negotiation.'],
    'urn:ietf:params:xml:ns:xmpp-streams policy-violation': ['',
        '',
        'The entity has violated some local service policy.'],
    'urn:ietf:params:xml:ns:xmpp-streams remote-connection-failed': ['',
        '',
        'The server is unable to properly connect to a remote resource that is required for authentication or authorization.'],
    'urn:ietf:params:xml:ns:xmpp-streams resource-constraint': ['',
        '',
        'The server lacks the system resources necessary to service the stream.'],
    'urn:ietf:params:xml:ns:xmpp-streams restricted-xml': ['',
        '',
        'The entity has attempted to send restricted XML features such as a comment, processing instruction, DTD, entity reference, or unescaped character.'],
    'urn:ietf:params:xml:ns:xmpp-streams see-other-host': ['',
        '',
        'The server will not provide service to the initiating entity but is redirecting traffic to another host.'],
    'urn:ietf:params:xml:ns:xmpp-streams system-shutdown': ['',
        '',
        'The server is being shut down and all active streams are being closed.'],
    'urn:ietf:params:xml:ns:xmpp-streams undefined-condition': ['',
        '',
        'The error condition is not one of those defined by the other conditions in this list.'],
    'urn:ietf:params:xml:ns:xmpp-streams unsupported-encoding': ['',
        '',
        'The initiating entity has encoded the stream in an encoding that is not supported by the server.'],
    'urn:ietf:params:xml:ns:xmpp-streams unsupported-stanza-type': ['',
        '',
        'The initiating entity has sent a first-level child of the stream that is not supported by the server.'],
    'urn:ietf:params:xml:ns:xmpp-streams unsupported-version': ['',
        '',
        "The value of the        'version' attribute provided by the initiating entity in the stream header specifies a version of XMPP that is not supported by the server."],
    'urn:ietf:params:xml:ns:xmpp-streams xml-not-well-formed': ['',
        '',
        'The initiating entity has sent XML that is not well-formed.']
}

_errorcodes = {
    '302': 'redirect',
    '400': 'unexpected-request',
    '401': 'not-authorized',
    '402': 'payment-required',
    '403': 'forbidden',
    '404': 'remote-server-not-found',
    '405': 'not-allowed',
    '406': 'not-acceptable',
    '407': 'subscription-required',
    '409': 'conflict',
    '500': 'undefined-condition',
    '501': 'feature-not-implemented',
    '503': 'service-unavailable',
    '504': 'remote-server-timeout',
    'cancel': 'invalid-from'
}

_status_conditions = {
    'realjid-public': 100,
    'affiliation-changed': 101,
    'unavailable-shown': 102,
    'unavailable-not-shown': 103,
    'configuration-changed': 104,
    'self-presence': 110,
    'logging-enabled': 170,
    'logging-disabled': 171,
    'non-anonymous': 172,
    'semi-anonymous': 173,
    'fully-anonymous': 174,
    'room-created': 201,
    'nick-assigned': 210,
    'banned': 301,
    'new-nick': 303,
    'kicked': 307,
    'removed-affiliation': 321,
    'removed-membership': 322,
    'removed-shutdown': 332,
}

_localpart_disallowed_chars = set('"&\'/:<>@')
_localpart_escape_chars = ' "&\'/:<>@'


STREAM_NOT_AUTHORIZED = 'urn:ietf:params:xml:ns:xmpp-streams not-authorized'
STREAM_REMOTE_CONNECTION_FAILED = 'urn:ietf:params:xml:ns:xmpp-streams remote-connection-failed'
SASL_MECHANISM_TOO_WEAK = 'urn:ietf:params:xml:ns:xmpp-sasl mechanism-too-weak'
STREAM_XML_NOT_WELL_FORMED = 'urn:ietf:params:xml:ns:xmpp-streams xml-not-well-formed'
ERR_JID_MALFORMED = 'urn:ietf:params:xml:ns:xmpp-stanzas jid-malformed'
STREAM_SEE_OTHER_HOST = 'urn:ietf:params:xml:ns:xmpp-streams see-other-host'
STREAM_BAD_NAMESPACE_PREFIX = 'urn:ietf:params:xml:ns:xmpp-streams bad-namespace-prefix'
ERR_SERVICE_UNAVAILABLE = 'urn:ietf:params:xml:ns:xmpp-stanzas service-unavailable'
STREAM_CONNECTION_TIMEOUT = 'urn:ietf:params:xml:ns:xmpp-streams connection-timeout'
STREAM_UNSUPPORTED_VERSION = 'urn:ietf:params:xml:ns:xmpp-streams unsupported-version'
STREAM_IMPROPER_ADDRESSING = 'urn:ietf:params:xml:ns:xmpp-streams improper-addressing'
STREAM_UNDEFINED_CONDITION = 'urn:ietf:params:xml:ns:xmpp-streams undefined-condition'
SASL_NOT_AUTHORIZED = 'urn:ietf:params:xml:ns:xmpp-sasl not-authorized'
ERR_GONE = 'urn:ietf:params:xml:ns:xmpp-stanzas gone'
SASL_TEMPORARY_AUTH_FAILURE = 'urn:ietf:params:xml:ns:xmpp-sasl temporary-auth-failure'
ERR_REMOTE_SERVER_NOT_FOUND = 'urn:ietf:params:xml:ns:xmpp-stanzas remote-server-not-found'
ERR_UNEXPECTED_REQUEST = 'urn:ietf:params:xml:ns:xmpp-stanzas unexpected-request'
ERR_RECIPIENT_UNAVAILABLE = 'urn:ietf:params:xml:ns:xmpp-stanzas recipient-unavailable'
ERR_CONFLICT = 'urn:ietf:params:xml:ns:xmpp-stanzas conflict'
STREAM_SYSTEM_SHUTDOWN = 'urn:ietf:params:xml:ns:xmpp-streams system-shutdown'
STREAM_BAD_FORMAT = 'urn:ietf:params:xml:ns:xmpp-streams bad-format'
ERR_SUBSCRIPTION_REQUIRED = 'urn:ietf:params:xml:ns:xmpp-stanzas subscription-required'
STREAM_INTERNAL_SERVER_ERROR = 'urn:ietf:params:xml:ns:xmpp-streams internal-server-error'
ERR_NOT_AUTHORIZED = 'urn:ietf:params:xml:ns:xmpp-stanzas not-authorized'
SASL_ABORTED = 'urn:ietf:params:xml:ns:xmpp-sasl aborted'
ERR_REGISTRATION_REQUIRED = 'urn:ietf:params:xml:ns:xmpp-stanzas registration-required'
ERR_INTERNAL_SERVER_ERROR = 'urn:ietf:params:xml:ns:xmpp-stanzas internal-server-error'
SASL_INCORRECT_ENCODING = 'urn:ietf:params:xml:ns:xmpp-sasl incorrect-encoding'
STREAM_HOST_GONE = 'urn:ietf:params:xml:ns:xmpp-streams host-gone'
STREAM_POLICY_VIOLATION = 'urn:ietf:params:xml:ns:xmpp-streams policy-violation'
STREAM_INVALID_XML = 'urn:ietf:params:xml:ns:xmpp-streams invalid-xml'
STREAM_CONFLICT = 'urn:ietf:params:xml:ns:xmpp-streams conflict'
STREAM_RESOURCE_CONSTRAINT = 'urn:ietf:params:xml:ns:xmpp-streams resource-constraint'
STREAM_UNSUPPORTED_ENCODING = 'urn:ietf:params:xml:ns:xmpp-streams unsupported-encoding'
ERR_NOT_ALLOWED = 'urn:ietf:params:xml:ns:xmpp-stanzas not-allowed'
ERR_ITEM_NOT_FOUND = 'urn:ietf:params:xml:ns:xmpp-stanzas item-not-found'
ERR_NOT_ACCEPTABLE = 'urn:ietf:params:xml:ns:xmpp-stanzas not-acceptable'
STREAM_INVALID_FROM = 'urn:ietf:params:xml:ns:xmpp-streams invalid-from'
ERR_FEATURE_NOT_IMPLEMENTED = 'urn:ietf:params:xml:ns:xmpp-stanzas feature-not-implemented'
ERR_BAD_REQUEST = 'urn:ietf:params:xml:ns:xmpp-stanzas bad-request'
STREAM_INVALID_ID = 'urn:ietf:params:xml:ns:xmpp-streams invalid-id'
STREAM_HOST_UNKNOWN = 'urn:ietf:params:xml:ns:xmpp-streams host-unknown'
ERR_UNDEFINED_CONDITION = 'urn:ietf:params:xml:ns:xmpp-stanzas undefined-condition'
SASL_INVALID_MECHANISM = 'urn:ietf:params:xml:ns:xmpp-sasl invalid-mechanism'
STREAM_RESTRICTED_XML = 'urn:ietf:params:xml:ns:xmpp-streams restricted-xml'
ERR_RESOURCE_CONSTRAINT = 'urn:ietf:params:xml:ns:xmpp-stanzas resource-constraint'
ERR_REMOTE_SERVER_TIMEOUT = 'urn:ietf:params:xml:ns:xmpp-stanzas remote-server-timeout'
SASL_INVALID_AUTHZID = 'urn:ietf:params:xml:ns:xmpp-sasl invalid-authzid'
ERR_PAYMENT_REQUIRED = 'urn:ietf:params:xml:ns:xmpp-stanzas payment-required'
STREAM_INVALID_NAMESPACE = 'urn:ietf:params:xml:ns:xmpp-streams invalid-namespace'
ERR_REDIRECT = 'urn:ietf:params:xml:ns:xmpp-stanzas redirect'
STREAM_UNSUPPORTED_STANZA_TYPE = 'urn:ietf:params:xml:ns:xmpp-streams unsupported-stanza-type'
ERR_FORBIDDEN = 'urn:ietf:params:xml:ns:xmpp-stanzas forbidden'

def isResultNode(node):
    """
    Return true if the node is a positive reply
    """
    return node and node.getType() == 'result'

def isErrorNode(node):
    """
    Return true if the node is a negative reply
    """
    return node and node.getType() == 'error'

def isMucPM(message):
    muc_user = message.getTag('x', namespace=Namespace.MUC_USER)
    return (message.getType() in ('chat', 'error') and
            muc_user is not None and
            not muc_user.getChildren())

class NodeProcessed(Exception):
    """
    Exception that should be raised by handler when the handling should be
    stopped
    """

class StreamError(Exception):
    """
    Base exception class for stream errors
    """

class BadFormat(StreamError):
    pass

class BadNamespacePrefix(StreamError):
    pass

class Conflict(StreamError):
    pass

class ConnectionTimeout(StreamError):
    pass

class HostGone(StreamError):
    pass

class HostUnknown(StreamError):
    pass

class ImproperAddressing(StreamError):
    pass

class InternalServerError(StreamError):
    pass

class InvalidFrom(StreamError):
    pass

class InvalidID(StreamError):
    pass

class InvalidNamespace(StreamError):
    pass

class InvalidXML(StreamError):
    pass

class NotAuthorized(StreamError):
    pass

class PolicyViolation(StreamError):
    pass

class RemoteConnectionFailed(StreamError):
    pass

class ResourceConstraint(StreamError):
    pass

class RestrictedXML(StreamError):
    pass

class SeeOtherHost(StreamError):
    pass

class SystemShutdown(StreamError):
    pass

class UndefinedCondition(StreamError):
    pass

class UnsupportedEncoding(StreamError):
    pass

class UnsupportedStanzaType(StreamError):
    pass

class UnsupportedVersion(StreamError):
    pass

class XMLNotWellFormed(StreamError):
    pass

class InvalidStanza(Exception):
    pass

class InvalidJid(Exception):
    pass

class LocalpartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Localpart must be between 1 and 1023 bytes')

class LocalpartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Not allowed character in localpart')

class ResourcepartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self,
                            'Resourcepart must be between 1 and 1023 bytes')

class ResourcepartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Not allowed character in resourcepart')

class DomainpartByteLimit(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Domainpart must be between 1 and 1023 bytes')

class DomainpartNotAllowedChar(InvalidJid):
    def __init__(self):
        InvalidJid.__init__(self, 'Not allowed character in domainpart')

class StanzaMalformed(Exception):
    pass

class DiscoInfoMalformed(Exception):
    pass

stream_exceptions = {'bad-format': BadFormat,
                     'bad-namespace-prefix': BadNamespacePrefix,
                     'conflict': Conflict,
                     'connection-timeout': ConnectionTimeout,
                     'host-gone': HostGone,
                     'host-unknown': HostUnknown,
                     'improper-addressing': ImproperAddressing,
                     'internal-server-error': InternalServerError,
                     'invalid-from': InvalidFrom,
                     'invalid-id': InvalidID,
                     'invalid-namespace': InvalidNamespace,
                     'invalid-xml': InvalidXML,
                     'not-authorized': NotAuthorized,
                     'policy-violation': PolicyViolation,
                     'remote-connection-failed': RemoteConnectionFailed,
                     'resource-constraint': ResourceConstraint,
                     'restricted-xml': RestrictedXML,
                     'see-other-host': SeeOtherHost,
                     'system-shutdown': SystemShutdown,
                     'undefined-condition': UndefinedCondition,
                     'unsupported-encoding': UnsupportedEncoding,
                     'unsupported-stanza-type': UnsupportedStanzaType,
                     'unsupported-version': UnsupportedVersion,
                     'xml-not-well-formed': XMLNotWellFormed}


def deprecation_warning(message):
    warnings.warn(message, DeprecationWarning)


@functools.lru_cache(maxsize=None)
def validate_localpart(localpart):
    if not localpart or len(localpart.encode()) > 1023:
        raise LocalpartByteLimit

    if _localpart_disallowed_chars & set(localpart):
        raise LocalpartNotAllowedChar

    try:
        username = get_profile('UsernameCaseMapped')
        return username.enforce(localpart)
    except Exception:
        raise LocalpartNotAllowedChar


@functools.lru_cache(maxsize=None)
def validate_resourcepart(resourcepart):
    if not resourcepart or len(resourcepart.encode()) > 1023:
        raise ResourcepartByteLimit

    try:
        opaque = get_profile('OpaqueString')
        return opaque.enforce(resourcepart)
    except Exception:
        raise ResourcepartNotAllowedChar


@functools.lru_cache(maxsize=None)
def validate_domainpart(domainpart):
    if not domainpart:
        raise DomainpartByteLimit

    ip_address = domainpart.strip('[]')
    if GLib.hostname_is_ip_address(ip_address):
        return ip_address

    length = len(domainpart.encode())
    if length == 0 or length > 1023:
        raise DomainpartByteLimit

    if domainpart.endswith('.'):  # RFC7622, 3.2
        domainpart = domainpart[:-1]

    try:
        idna_encode(domainpart)
    except Exception:
        raise DomainpartNotAllowedChar

    return domainpart


@functools.lru_cache(maxsize=None)
def idna_encode(domain):
    return idna.encode(domain, uts46=True).decode()


@functools.lru_cache(maxsize=None)
def escape_localpart(localpart):
    # https://xmpp.org/extensions/xep-0106.html#bizrules-algorithm
    #
    # If there are any instances of character sequences that correspond
    # to escapings of the disallowed characters
    # (e.g., the character sequence "\27") or the escaping character
    # (i.e., the character sequence "\5c") in the source address,
    # the leading backslash character MUST be escaped to the character
    # sequence "\5c"

    for char in '\\' + _localpart_escape_chars:
        seq = "\\{:02x}".format(ord(char))
        localpart = localpart.replace(seq, "\\5c{:02x}".format(ord(char)))

    # Escape all other chars
    for char in _localpart_escape_chars:
        localpart = localpart.replace(char, "\\{:02x}".format(ord(char)))

    return localpart


@functools.lru_cache(maxsize=None)
def unescape_localpart(localpart):
    if localpart.startswith('\\20') or localpart.endswith('\\20'):
        # Escaped JIDs are not allowed to start or end with \20
        # so this localpart must be already unescaped
        return localpart

    for char in _localpart_escape_chars:
        seq = "\\{:02x}".format(ord(char))
        localpart = localpart.replace(seq, char)

    for char in _localpart_escape_chars + "\\":
        seq = "\\5c{:02x}".format(ord(char))
        localpart = localpart.replace(seq, "\\{:02x}".format(ord(char)))

    return localpart


class JID(namedtuple('JID',
                     ['jid', 'localpart', 'domain', 'resource'])):

    __slots__ = []

    def __new__(cls, jid=None, localpart=None, domain=None, resource=None):
        if jid is not None:
            deprecation_warning('JID(jid) is deprecated, use from_string()')
            return JID.from_string(str(jid))

        if localpart is not None:
            localpart = validate_localpart(localpart)

        domain = validate_domainpart(domain)

        if resource is not None:
            resource = validate_resourcepart(resource)

        return super().__new__(cls, None, localpart, domain, resource)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def from_string(cls, jid_string):
        # https://tools.ietf.org/html/rfc7622#section-3.2

        # Remove any portion from the first '/' character to the end of the
        # string (if there is a '/' character present).

        # Remove any portion from the beginning of the string to the first
        # '@' character (if there is an '@' character present).

        if jid_string.find('/') != -1:
            rest, resourcepart = jid_string.split('/', 1)
        else:
            rest, resourcepart = jid_string, None

        if rest.find('@') != -1:
            localpart, domainpart = rest.split('@', 1)
        else:
            localpart, domainpart = None, rest

        return cls(jid=None,
                   localpart=localpart,
                   domain=domainpart,
                   resource=resourcepart)

    @classmethod
    @functools.lru_cache(maxsize=None)
    def from_user_input(cls, user_input, escaped=False):
        # Use this if we want JIDs to be escaped according to XEP-0106
        # The standard JID parsing cannot be applied because user_input is
        # not a valid JID.

        # Only user_input which after escaping result in a bare JID can be
        # successfully parsed.

        # The assumpution is user_input is a bare JID so we start with an
        # rsplit on @ because we assume there is no resource, so the char @
        # in the localpart can later be escaped.

        if escaped:
            # for convenience
            return cls.from_string(user_input)

        if '@' in user_input:
            localpart, domainpart = user_input.rsplit('@', 1)
            if localpart.startswith(' ') or localpart.endswith(' '):
                raise LocalpartNotAllowedChar

            localpart = escape_localpart(localpart)

        else:
            localpart = None
            domainpart = user_input

        return cls(jid=None,
                   localpart=localpart,
                   domain=domainpart,
                   resource=None)

    def __str__(self):
        if self.localpart:
            jid = f'{self.localpart}@{self.domain}'
        else:
            jid = self.domain

        if self.resource is not None:
            return f'{jid}/{self.resource}'
        return jid

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if isinstance(other, str):
            deprecation_warning('comparing string with JID is deprected')
            try:
                return JID.from_string(other) == self
            except Exception:
                return False
        return super().__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def domain_to_ascii(self):
        return idna_encode(self.domain)

    @property
    def bare(self):
        if self.localpart is not None:
            return f'{self.localpart}@{self.domain}'
        return self.domain

    @property
    def is_bare(self):
        return self.resource is None

    def new_as_bare(self):
        if self.resource is None:
            return self
        return self._replace(resource=None)

    def bare_match(self, other):
        if isinstance(other, str):
            other = JID.from_string(other)
        return self.bare == other.bare

    @property
    def is_domain(self):
        return self.localpart is None and self.resource is None

    @property
    def is_full(self):
        return (self.localpart is not None and
                self.domain is not None and
                self.resource is not None)

    def new_with(self, **kwargs):
        return self._replace(**kwargs)

    def to_user_string(self, show_punycode=True):
        domain = self.domain_to_ascii()
        if domain.startswith('xn--') and show_punycode:
            domain_encoded = f' ({domain})'
        else:
            domain_encoded = ''

        if self.localpart is None:
            return f'{self}{domain_encoded}'

        localpart = unescape_localpart(self.localpart)

        if self.resource is None:
            return f'{localpart}@{self.domain}{domain_encoded}'
        return f'{localpart}@{self.domain}/{self.resource}{domain_encoded}'

    def bareMatch(self, other):
        deprecation_warning('bareMatch() is deprected use bare_match()')
        return self.bare_match(other)

    @property
    def isBare(self):
        deprecation_warning('isBare() is deprected use '
                            'the attribute is_bare')
        return self.is_bare

    @property
    def isDomain(self):
        deprecation_warning('isDomain() is deprected use '
                            'the attribute is_domain')
        return self.is_domain

    @property
    def isFull(self):
        deprecation_warning('isFull() is deprected use '
                            'the attribute is_full')
        return self.is_full

    def copy(self):
        deprecation_warning('copy() is not needed, JID is immutable')
        return self

    def getNode(self):
        deprecation_warning('getNode() is deprected use '
                            'the attribute localpart')
        return self.localpart

    def getDomain(self):
        deprecation_warning('getDomain() is deprected use '
                            'the attribute domain')
        return self.domain

    def getResource(self):
        deprecation_warning('getResource() is deprected use '
                            'the attribute resource')
        return self.resource

    def getStripped(self):
        deprecation_warning('getStripped() is deprected use '
                            'the attribute bare')
        return self.bare

    def getBare(self):
        deprecation_warning('getBare() is deprected use '
                            'the attribute bare')
        return self.bare


class StreamErrorNode(Node):
    def __init__(self, node):
        Node.__init__(self, node=node)

        self._text = {}

        text_elements = self.getTags('text', namespace=Namespace.XMPP_STREAMS)
        for element in text_elements:
            lang = element.getXmlLang()
            text = element.getData()
            self._text[lang] = text

    def get_condition(self):
        for tag in self.getChildren():
            if (tag.getName() != 'text' and
                    tag.getNamespace() == Namespace.XMPP_STREAMS):
                return tag.getName()
        return None

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


class Protocol(Node):
    """
    A "stanza" object class. Contains methods that are common for presences, iqs
    and messages
    """

    def __init__(self,
                 name=None,
                 to=None,
                 typ=None,
                 frm=None,
                 attrs=None,
                 payload=None,
                 timestamp=None,
                 xmlns=None,
                 node=None):
        """
        Constructor, name is the name of the stanza
        i.e. 'message' or 'presence'or 'iq'

        to is the value of 'to' attribure, 'typ' - 'type' attribute
        frn - from attribure, attrs - other attributes mapping,
        payload - same meaning as for simplexml payload definition
        timestamp - the time value that needs to be stamped over stanza
        xmlns - namespace of top stanza node
        node - parsed or unparsed stana to be taken as prototype.
        """
        if not attrs:
            attrs = {}
        if to:
            attrs['to'] = to
        if frm:
            attrs['from'] = frm
        if typ:
            attrs['type'] = typ
        Node.__init__(self, tag=name, attrs=attrs, payload=payload, node=node)
        if not node and xmlns:
            self.setNamespace(xmlns)
        if self['to']:
            self.setTo(self['to'])
        if self['from']:
            self.setFrom(self['from'])
        if (node and
                isinstance(node, Protocol) and
                self.__class__ == node.__class__
                and 'id' in self.attrs):
            del self.attrs['id']
        self.timestamp = None
        for d in self.getTags('delay', namespace=Namespace.DELAY2):
            try:
                if d.getAttr('stamp') < self.getTimestamp2():
                    self.setTimestamp(d.getAttr('stamp'))
            except Exception:
                pass
        if not self.timestamp:
            for x in self.getTags('x', namespace=Namespace.DELAY):
                try:
                    if x.getAttr('stamp') < self.getTimestamp():
                        self.setTimestamp(x.getAttr('stamp'))
                except Exception:
                    pass
        if timestamp is not None:
            self.setTimestamp(timestamp)

    def isError(self):
        return self.getAttr('type') == 'error'

    def isResult(self):
        return self.getAttr('type') == 'result'

    def getTo(self):
        """
        Return value of the 'to' attribute
        """
        try:
            return self['to']
        except Exception:
            pass
        return None

    def getFrom(self):
        """
        Return value of the 'from' attribute
        """
        try:
            return self['from']
        except Exception:
            pass
        return None

    def getTimestamp(self):
        """
        Return the timestamp in the 'yyyymmddThhmmss' format
        """
        if self.timestamp:
            return self.timestamp
        return time.strftime('%Y%m%dT%H:%M:%S', time.gmtime())

    def getTimestamp2(self):
        """
        Return the timestamp in the 'yyyymmddThhmmss' format
        """
        if self.timestamp:
            return self.timestamp
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    def getJid(self):
        """
        Return the value of the 'jid' attribute
        """
        attr = self.getAttr('jid')
        if attr:
            return JID.from_string(attr)
        return attr

    def getID(self):
        """
        Return the value of the 'id' attribute
        """
        return self.getAttr('id')

    def setTo(self, val):
        """
        Set the value of the 'to' attribute
        """
        if not isinstance(val, JID):
            val = JID.from_string(val)
        self.setAttr('to', val)

    def getType(self):
        """
        Return the value of the 'type' attribute
        """
        return self.getAttr('type')

    def setFrom(self, val):
        """
        Set the value of the 'from' attribute
        """
        if not isinstance(val, JID):
            val = JID.from_string(val)
        self.setAttr('from', val)

    def setType(self, val):
        """
        Set the value of the 'type' attribute
        """
        self.setAttr('type', val)

    def setID(self, val):
        """
        Set the value of the 'id' attribute
        """
        self.setAttr('id', val)

    def getError(self):
        """
        Return the error-condition (if present) or the textual description
        of the error (otherwise)
        """
        errtag = self.getTag('error')
        if errtag is None:
            return None
        for tag in errtag.getChildren():
            if (tag.getName() != 'text' and
                    tag.getNamespace() == Namespace.STANZAS):
                return tag.getName()
        return None

    def getAppError(self):
        errtag = self.getTag('error')
        if errtag is None:
            return None
        for tag in errtag.getChildren():
            if (tag.getName() != 'text' and
                    tag.getNamespace() != Namespace.STANZAS):
                return tag.getName()
        return None

    def getAppErrorNamespace(self):
        errtag = self.getTag('error')
        if errtag is None:
            return None
        for tag in errtag.getChildren():
            if (tag.getName() != 'text' and
                    tag.getNamespace() != Namespace.STANZAS):
                return tag.getNamespace()
        return None

    def getErrorMsg(self):
        """
        Return the textual description of the error (if present)
        or the error condition
        """
        errtag = self.getTag('error')
        if errtag:
            for tag in errtag.getChildren():
                if tag.getName() == 'text':
                    return tag.getData()
            return self.getError()
        return None

    def getErrorCode(self):
        """
        Return the error code. Obsolete.
        """
        return self.getTagAttr('error', 'code')

    def getErrorType(self):
        """
        Return the error code. Obsolete.
        """
        return self.getTagAttr('error', 'type')

    def getStatusConditions(self, as_code=False):
        """
        Return the status conditions list as defined in XEP-0306.
        """
        result = set()
        status_tags = self.getTags('status')
        for status in status_tags:
            if as_code:
                code = status.getAttr('code')
                if code is not None:
                    result.add(code)
            else:
                for condition in status.getChildren():
                    result.add(condition.getName())
        return list(result)

    def setError(self, error, code=None):
        """
        Set the error code. Obsolete. Use error-conditions instead
        """
        if code:
            if str(code) in _errorcodes.keys():
                error = ErrorNode(_errorcodes[str(code)], text=error)
            else:
                error = ErrorNode(ERR_UNDEFINED_CONDITION, code=code,
                                  typ='cancel', text=error)
        elif isinstance(error, str):
            error = ErrorNode(error)
        self.setType('error')
        self.addChild(node=error)

    def setTimestamp(self, val=None):
        """
        Set the timestamp. timestamp should be the yyyymmddThhmmss string
        """
        if not val:
            val = time.strftime('%Y%m%dT%H:%M:%S', time.gmtime())
        self.timestamp=val
        self.setTag('x', {'stamp': self.timestamp}, namespace=Namespace.DELAY)

    def getProperties(self):
        """
        Return the list of namespaces to which belongs the
        direct childs of element
        """
        props = []
        for child in self.getChildren():
            prop = child.getNamespace()
            if prop not in props:
                props.append(prop)
        return props

    def getTag(self, name, attrs=None, namespace=None, protocol=False):
        """
        Return the Node instance for the tag.
        If protocol is True convert to a new Protocol/Message instance.
        """
        tag = Node.getTag(self, name, attrs, namespace)
        if protocol and tag:
            if name == 'message':
                return Message(node=tag)
            return Protocol(node=tag)
        return tag

    def __setitem__(self, item, val):
        """
        Set the item 'item' to the value 'val'
        """
        if item in ['to', 'from']:
            if not isinstance(val, JID):
                val = JID.from_string(val)
        return self.setAttr(item, val)


class Message(Protocol):
    """
    XMPP Message stanza - "push" mechanism
    """

    def __init__(self,
                 to=None,
                 body=None,
                 xhtml=None,
                 typ=None,
                 subject=None,
                 attrs=None,
                 frm=None,
                 payload=None,
                 timestamp=None,
                 xmlns=Namespace.CLIENT,
                 node=None):
        """
        You can specify recipient, text of message, type of message any
        additional attributes, sender of the message, any additional payload
        (f.e. jabber:x:delay element) and namespace in one go.

        Alternatively you can pass in the other XML object as the 'node'
        parameted to replicate it as message
        """
        Protocol.__init__(self,
                          'message',
                          to=to,
                          typ=typ,
                          attrs=attrs,
                          frm=frm,
                          payload=payload,
                          timestamp=timestamp,
                          xmlns=xmlns,
                          node=node)
        if body:
            self.setBody(body)
        if xhtml is not None:
            self.setXHTML(xhtml)
        if subject is not None:
            self.setSubject(subject)

    def getBody(self):
        """
        Return text of the message
        """
        return self.getTagData('body')

    def getXHTML(self):
        return self.getTag('html', namespace=Namespace.XHTML_IM)

    def getSubject(self):
        """
        Return subject of the message
        """
        return self.getTagData('subject')

    def getThread(self):
        """
        Return thread of the message
        """
        return self.getTagData('thread')

    def getOriginID(self):
        """
        Return origin-id of the message
        """
        return self.getTagAttr('origin-id', namespace=Namespace.SID, attr='id')

    def getStanzaIDAttrs(self):
        """
        Return the stanza-id attributes of the message
        """
        try:
            attrs = self.getTag('stanza-id', namespace=Namespace.SID).getAttrs()
        except Exception:
            return None, None
        return attrs['id'], attrs['by']

    def setBody(self, val):
        """
        Set the text of the message"""
        self.setTagData('body', val)

    def setXHTML(self, body, add=False):
        if isinstance(body, str):
            body = Node(node=body)
        if add:
            xhtml = self.getTag('html', namespace=Namespace.XHTML_IM)
            if xhtml is not None:
                xhtml.addChild(node=body)
            else:
                self.addChild('html',
                              namespace=Namespace.XHTML_IM,
                              payload=body)
        else:
            xhtml_nodes = self.getTags('html', namespace=Namespace.XHTML_IM)
            for xhtml in xhtml_nodes:
                self.delChild(xhtml)
            self.addChild('html', namespace=Namespace.XHTML_IM, payload=body)

    def setSubject(self, val):
        """
        Set the subject of the message
        """
        self.setTagData('subject', val)

    def setThread(self, val):
        """
        Set the thread of the message
        """
        self.setTagData('thread', val)

    def setOriginID(self, val):
        """
        Sets the origin-id of the message
        """
        self.setTag('origin-id', namespace=Namespace.SID, attrs={'id': val})

    def buildReply(self, text=None):
        """
        Builds and returns another message object with specified text. The to,
        from, thread and type properties of new message are pre-set as reply to
        this message
        """
        m = Message(to=self.getFrom(),
                    frm=self.getTo(),
                    body=text,
                    typ=self.getType())
        th = self.getThread()
        if th:
            m.setThread(th)
        return m

    def getStatusCode(self):
        """
        Return the status code of the message (for groupchat config change)
        """
        attrs = []
        for xtag in self.getTags('x'):
            for child in xtag.getTags('status'):
                attrs.append(child.getAttr('code'))
        return attrs

    def setMarker(self, type_, id_):
        self.setTag(type_, namespace=Namespace.CHATMARKERS, attrs={'id': id_})

    def setMarkable(self):
        self.setTag('markable', namespace=Namespace.CHATMARKERS)

    def setReceiptRequest(self):
        self.setTag('request', namespace=Namespace.RECEIPTS)

    def setReceiptReceived(self, id_):
        self.setTag('received', namespace=Namespace.RECEIPTS, attrs={'id': id_})

    def setOOB(self, url, desc=None):
        oob = self.setTag('x', namespace=Namespace.X_OOB)
        oob.setTagData('url', url)
        if desc is not None:
            oob.setTagData('desc', desc)

    def setCorrection(self, id_):
        self.setTag('replace', namespace=Namespace.CORRECT, attrs={'id': id_})

    def setAttention(self):
        self.setTag('attention', namespace=Namespace.ATTENTION)

    def setHint(self, hint):
        self.setTag(hint, namespace=Namespace.HINTS)


class Presence(Protocol):

    def __init__(self,
                 to=None,
                 typ=None,
                 priority=None,
                 show=None,
                 status=None,
                 attrs=None,
                 frm=None,
                 timestamp=None,
                 payload=None,
                 xmlns=Namespace.CLIENT,
                 node=None):
        """
        You can specify recipient, type of message, priority, show and status
        values any additional attributes, sender of the presence, timestamp, any
        additional payload (f.e. jabber:x:delay element) and namespace in one
        go. Alternatively you can pass in the other XML object as the 'node'
        parameted to replicate it as presence
        """
        Protocol.__init__(self,
                          'presence',
                          to=to,
                          typ=typ,
                          attrs=attrs,
                          frm=frm,
                          payload=payload,
                          timestamp=timestamp,
                          xmlns=xmlns,
                          node=node)
        if priority:
            self.setPriority(priority)
        if show:
            self.setShow(show)
        if status:
            self.setStatus(status)

    def getPriority(self):
        """
        Return the priority of the message
        """
        return self.getTagData('priority')

    def getShow(self):
        """
        Return the show value of the message
        """
        return self.getTagData('show')

    def getStatus(self):
        """
        Return the status string of the message
        """
        return self.getTagData('status') or ''

    def setPriority(self, val):
        """
        Set the priority of the message
        """
        self.setTagData('priority', val)

    def setShow(self, val):
        """
        Set the show value of the message
        """
        if val not in ['away', 'chat', 'dnd', 'xa']:
            raise ValueError('Invalid show value: %s' % val)
        self.setTagData('show', val)

    def setStatus(self, val):
        """
        Set the status string of the message
        """
        self.setTagData('status', val)

    def _muc_getItemAttr(self, tag, attr):
        for xtag in self.getTags('x'):
            if xtag.getNamespace() not in (Namespace.MUC_USER,
                                           Namespace.MUC_ADMIN):
                continue
            for child in xtag.getTags(tag):
                return child.getAttr(attr)

    def _muc_getSubTagDataAttr(self, tag, attr):
        for xtag in self.getTags('x'):
            if xtag.getNamespace() not in (Namespace.MUC_USER,
                                           Namespace.MUC_ADMIN):
                continue
            for child in xtag.getTags('item'):
                for cchild in child.getTags(tag):
                    return cchild.getData(), cchild.getAttr(attr)
        return None, None

    def getRole(self):
        """
        Return the presence role (for groupchat)
        """
        return self._muc_getItemAttr('item', 'role')

    def getAffiliation(self):
        """
        Return the presence affiliation (for groupchat)
        """
        return self._muc_getItemAttr('item', 'affiliation')

    def getNewNick(self):
        """
        Return the status code of the presence (for groupchat)
        """
        return self._muc_getItemAttr('item', 'nick')

    def getJid(self):
        """
        Return the presence jid (for groupchat)
        """
        return self._muc_getItemAttr('item', 'jid')

    def getReason(self):
        """
        Returns the reason of the presence (for groupchat)
        """
        return self._muc_getSubTagDataAttr('reason', '')[0]

    def getActor(self):
        """
        Return the reason of the presence (for groupchat)
        """
        return self._muc_getSubTagDataAttr('actor', 'jid')[1]

    def getStatusCode(self):
        """
        Return the status code of the presence (for groupchat)
        """
        attrs = []
        for xtag in self.getTags('x'):
            for child in xtag.getTags('status'):
                attrs.append(child.getAttr('code'))
        return attrs

class Iq(Protocol):
    """
    XMPP Iq object - get/set dialog mechanism
    """

    def __init__(self,
                 typ=None,
                 queryNS=None,
                 attrs=None,
                 to=None,
                 frm=None,
                 payload=None,
                 xmlns=Namespace.CLIENT,
                 node=None):
        """
        You can specify type, query namespace any additional attributes,
        recipient of the iq, sender of the iq, any additional payload (f.e.
        jabber:x:data node) and namespace in one go.

        Alternatively you can pass in the other XML object as the 'node'
        parameted to replicate it as an iq
        """
        Protocol.__init__(self,
                          'iq',
                          to=to,
                          typ=typ,
                          attrs=attrs,
                          frm=frm,
                          xmlns=xmlns,
                          node=node)
        if payload:
            self.setQueryPayload(payload)
        if queryNS:
            self.setQueryNS(queryNS)

    def getQuery(self):
        """
        Return the IQ's child element if it exists, None otherwise.
        """
        children = self.getChildren()
        if children and self.getType() != 'error' and \
        children[0].getName() != 'error':
            return children[0]
        return None

    def getQueryNS(self):
        """
        Return the namespace of the 'query' child element
        """
        tag = self.getQuery()
        if tag:
            return tag.getNamespace()
        return None

    def getQuerynode(self):
        """
        Return the 'node' attribute value of the 'query' child element
        """
        tag = self.getQuery()
        if tag:
            return tag.getAttr('node')
        return None

    def getQueryPayload(self):
        """
        Return the 'query' child element payload
        """
        tag = self.getQuery()
        if tag:
            return tag.getPayload()
        return None

    def getQueryChildren(self):
        """
        Return the 'query' child element child nodes
        """
        tag = self.getQuery()
        if tag:
            return tag.getChildren()
        return None

    def getQueryChild(self, name=None):
        """
        Return the 'query' child element with name, or the first element
        which is not an error element
        """
        query = self.getQuery()
        if not query:
            return None
        for node in query.getChildren():
            if name is not None:
                if node.getName() == name:
                    return node
            else:
                if node.getName() != 'error':
                    return node
        return None

    def setQuery(self, name=None):
        """
        Change the name of the query node, creating it if needed. Keep the
        existing name if none is given (use 'query' if it's a creation).
        Return the query node.
        """
        query = self.getQuery()
        if query is None:
            query = self.addChild('query')
        if name is not None:
            query.setName(name)
        return query

    def setQueryNS(self, namespace):
        """
        Set the namespace of the 'query' child element
        """
        self.setQuery().setNamespace(namespace)

    def setQueryPayload(self, payload):
        """
        Set the 'query' child element payload
        """
        self.setQuery().setPayload(payload)

    def setQuerynode(self, node):
        """
        Set the 'node' attribute value of the 'query' child element
        """
        self.setQuery().setAttr('node', node)

    def buildReply(self, typ):
        """
        Build and return another Iq object of specified type. The to, from and
        query child node of new Iq are pre-set as reply to this Iq.
        """
        iq = Iq(typ,
                to=self.getFrom(),
                frm=self.getTo(),
                attrs={'id': self.getID()})
        iq.setQuery(self.getQuery().getName()).setNamespace(self.getQueryNS())
        return iq

    def buildSimpleReply(self, typ):
        return Iq(typ,
                  to=self.getFrom(),
                  attrs={'id': self.getID()})


class Hashes(Node):
    """
    Hash elements for various XEPs as defined in XEP-300

    RECOMENDED HASH USE:
    Algorithm     Support
    MD2           MUST NOT
    MD4           MUST NOT
    MD5           MAY
    SHA-1         MUST
    SHA-256       MUST
    SHA-512       SHOULD
    """

    supported = ('md5', 'sha-1', 'sha-256', 'sha-512')

    def __init__(self, nsp=Namespace.HASHES):
        Node.__init__(self, None, {}, [], None, None, False, None)
        self.setNamespace(nsp)
        self.setName('hash')

    def calculateHash(self, algo, file_string):
        """
        Calculate the hash and add it. It is preferable doing it here
        instead of doing it all over the place in Gajim.
        """
        hl = None
        hash_ = None
        # file_string can be a string or a file
        if isinstance(file_string, str):
            if algo == 'sha-1':
                hl = hashlib.sha1()
            elif algo == 'md5':
                hl = hashlib.md5()
            elif algo == 'sha-256':
                hl = hashlib.sha256()
            elif algo == 'sha-512':
                hl = hashlib.sha512()
            if hl:
                hl.update(file_string)
                hash_ = hl.hexdigest()
        else: # if it is a file
            if algo == 'sha-1':
                hl = hashlib.sha1()
            elif algo == 'md5':
                hl = hashlib.md5()
            elif algo == 'sha-256':
                hl = hashlib.sha256()
            elif algo == 'sha-512':
                hl = hashlib.sha512()
            if hl:
                for line in file_string:
                    hl.update(line)
                hash_ = hl.hexdigest()
        return hash_

    def addHash(self, hash_, algo):
        self.setAttr('algo', algo)
        self.setData(hash_)

class Hashes2(Node):
    """
    Hash elements for various XEPs as defined in XEP-300

    RECOMENDED HASH USE:
    Algorithm     Support
    MD2           MUST NOT
    MD4           MUST NOT
    MD5           MUST NOT
    SHA-1         SHOULD NOT
    SHA-256       MUST
    SHA-512       SHOULD
    SHA3-256      MUST
    SHA3-512      SHOULD
    BLAKE2b256    MUST
    BLAKE2b512    SHOULD
    """

    supported = ('sha-256', 'sha-512', 'sha3-256',
                 'sha3-512', 'blake2b-256', 'blake2b-512')

    def __init__(self, nsp=Namespace.HASHES_2):
        Node.__init__(self, None, {}, [], None, None, False, None)
        self.setNamespace(nsp)
        self.setName('hash')

    def calculateHash(self, algo, file_string):
        """
        Calculate the hash and add it. It is preferable doing it here
        instead of doing it all over the place in Gajim.
        """
        hl = None
        hash_ = None
        if algo == 'sha-256':
            hl = hashlib.sha256()
        elif algo == 'sha-512':
            hl = hashlib.sha512()
        elif algo == 'sha3-256':
            hl = hashlib.sha3_256()
        elif algo == 'sha3-512':
            hl = hashlib.sha3_512()
        elif algo == 'blake2b-256':
            hl = hashlib.blake2b(digest_size=32)
        elif algo == 'blake2b-512':
            hl = hashlib.blake2b(digest_size=64)
        # file_string can be a string or a file
        if hl is not None:
            if isinstance(file_string, bytes):
                hl.update(file_string)
            else: # if it is a file
                for line in file_string:
                    hl.update(line)
            hash_ = b64encode(hl.digest()).decode('ascii')
        return hash_

    def addHash(self, hash_, algo):
        self.setAttr('algo', algo)
        self.setData(hash_)


class BindRequest(Iq):
    def __init__(self, resource):
        if resource is not None:
            resource = Node('resource', payload=resource)
        Iq.__init__(self, typ='set')
        self.addChild(node=Node('bind',
                                {'xmlns': Namespace.BIND},
                                payload=resource))


class TLSRequest(Node):
    def __init__(self):
        Node.__init__(self, tag='starttls', attrs={'xmlns': Namespace.TLS})


class SessionRequest(Iq):
    def __init__(self):
        Iq.__init__(self, typ='set')
        self.addChild(node=Node('session', attrs={'xmlns': Namespace.SESSION}))


class StreamHeader(Node):
    def __init__(self, domain, lang=None):
        if lang is None:
            lang = 'en'
        Node.__init__(self,
                      tag='stream:stream',
                      attrs={'xmlns': Namespace.CLIENT,
                             'version': '1.0',
                             'xmlns:stream': Namespace.STREAMS,
                             'to': domain,
                             'xml:lang': lang})


class WebsocketOpenHeader(Node):
    def __init__(self, domain, lang=None):
        if lang is None:
            lang = 'en'
        Node.__init__(self,
                      tag='open',
                      attrs={'xmlns': Namespace.FRAMING,
                             'version': '1.0',
                             'to': domain,
                             'xml:lang': lang})

class WebsocketCloseHeader(Node):
    def __init__(self):
        Node.__init__(self, tag='close', attrs={'xmlns': Namespace.FRAMING})


class Features(Node):
    def __init__(self, node):
        Node.__init__(self, node=node)

    def has_starttls(self):
        tls = self.getTag('starttls', namespace=Namespace.TLS)
        if tls is not None:
            required = tls.getTag('required') is not None
            return True, required
        return False, False

    def has_sasl(self):
        return self.getTag('mechanisms', namespace=Namespace.SASL) is not None

    def get_mechs(self):
        mechanisms = self.getTag('mechanisms', namespace=Namespace.SASL)
        if mechanisms is None:
            return set()
        mechanisms = mechanisms.getTags('mechanism')
        return set(mech.getData() for mech in mechanisms)

    def get_domain_based_name(self):
        hostname = self.getTag('hostname',
                               namespace=Namespace.DOMAIN_BASED_NAME)
        if hostname is not None:
            return hostname.getData()
        return None

    def has_bind(self):
        return self.getTag('bind', namespace=Namespace.BIND) is not None

    def session_required(self):
        session = self.getTag('session', namespace=Namespace.SESSION)
        if session is not None:
            optional = session.getTag('optional') is not None
            return not optional
        return False

    def has_sm(self):
        return self.getTag('sm', namespace=Namespace.STREAM_MGMT) is not None

    def has_roster_version(self):
        return self.getTag('ver', namespace=Namespace.ROSTER_VER) is not None

    def has_register(self):
        return self.getTag(
            'register', namespace=Namespace.REGISTER_FEATURE) is not None

    def has_anonymous(self):
        return 'ANONYMOUS' in self.get_mechs()


class ErrorNode(Node):
    """
    XMPP-style error element

    In the case of stanza error should be attached to XMPP stanza.
    In the case of stream-level errors should be used separately.
    """

    def __init__(self, name, code=None, typ=None, text=None):
        """
        Mandatory parameter: name - name of error condition.
        Optional parameters: code, typ, text.
        Used for backwards compartibility with older jabber protocol.
        """
        if name in ERRORS:
            cod, type_, txt = ERRORS[name]
            ns = name.split()[0]
        else:
            cod, ns, type_, txt = '500', Namespace.STANZAS, 'cancel', ''
        if typ:
            type_ = typ
        if code:
            cod = code
        if text:
            txt = text
        Node.__init__(self, 'error', {}, [Node(name)])
        if type_:
            self.setAttr('type', type_)
        if not cod:
            self.setName('stream:error')
        if txt:
            self.addChild(node=Node(ns + ' text', {}, [txt]))
        if cod:
            self.setAttr('code', cod)

class Error(Protocol):
    """
    Used to quickly transform received stanza into error reply
    """

    def __init__(self, node, error, reply=1):
        """
        Create error reply basing on the received 'node' stanza and the 'error'
        error condition

        If the 'node' is not the received stanza but locally created ('to' and
        'from' fields needs not swapping) specify the 'reply' argument as false.
        """
        if reply:
            Protocol.__init__(self,
                              to=node.getFrom(),
                              frm=node.getTo(),
                              node=node)
        else:
            Protocol.__init__(self, node=node)
        self.setError(error)
        if node.getType() == 'error':
            self.__str__ = self.__dupstr__

    def __dupstr__(self, _dup1=None, _dup2=None):
        """
        Dummy function used as preventor of creating error node in reply to
        error node. I.e. you will not be able to serialise "double" error
        into string.
        """
        return ''

class DataField(Node):
    """
    This class is used in the DataForm class to describe the single data item

    If you are working with jabber:x:data (XEP-0004, XEP-0068, XEP-0122) then
    you will need to work with instances of this class.
    """

    def __init__(self,
                 name=None,
                 value=None,
                 typ=None,
                 required=0,
                 desc=None,
                 options=None,
                 node=None):
        """
        Create new data field of specified name,value and type

        Also 'required','desc' and 'options' fields can be set. Alternatively
        other XML object can be passed in as the 'node' parameted
        to replicate it as a new datafiled.
        """
        Node.__init__(self, 'field', node=node)
        if name:
            self.setVar(name)
        if isinstance(value, (list, tuple)):
            self.setValues(value)
        elif value:
            self.setValue(value)
        if typ:
            self.setType(typ)
        elif not typ and not node:
            self.setType('text-single')
        if required:
            self.setRequired(required)
        if desc:
            self.setDesc(desc)
        if options:
            self.setOptions(options)

    def setRequired(self, req=1):
        """
        Change the state of the 'required' flag
        """
        if req:
            self.setTag('required')
        else:
            try:
                self.delChild('required')
            except ValueError:
                return

    def isRequired(self):
        """
        Return in this field a required one
        """
        return self.getTag('required')

    def setDesc(self, desc):
        """
        Set the description of this field
        """
        self.setTagData('desc', desc)

    def getDesc(self):
        """
        Return the description of this field
        """
        return self.getTagData('desc')

    def setValue(self, val):
        """
        Set the value of this field
        """
        self.setTagData('value', val)

    def getValue(self):
        return self.getTagData('value')

    def setValues(self, lst):
        """
        Set the values of this field as values-list. Replaces all previous filed
        values! If you need to just add a value - use addValue method
        """
        while self.getTag('value'):
            self.delChild('value')
        for val in lst:
            self.addValue(val)

    def addValue(self, val):
        """
        Add one more value to this field. Used in 'get' iq's or such
        """
        self.addChild('value', {}, [val])

    def getValues(self):
        """
        Return the list of values associated with this field
        """
        ret = []
        for tag in self.getTags('value'):
            ret.append(tag.getData())
        return ret

    def getOptions(self):
        """
        Return label-option pairs list associated with this field
        """
        ret = []
        for tag in self.getTags('option'):
            ret.append([tag.getAttr('label'), tag.getTagData('value')])
        return ret

    def setOptions(self, lst):
        """
        Set label-option pairs list associated with this field
        """
        while self.getTag('option'):
            self.delChild('option')
        for opt in lst:
            self.addOption(opt)

    def addOption(self, opt):
        """
        Add one more label-option pair to this field
        """
        if isinstance(opt, list):
            self.addChild('option',
                          {'label': opt[0]}).setTagData('value', opt[1])
        else:
            self.addChild('option').setTagData('value', opt)

    def getType(self):
        """
        Get type of this field
        """
        return self.getAttr('type')

    def setType(self, val):
        """
        Set type of this field
        """
        return self.setAttr('type', val)

    def getVar(self):
        """
        Get 'var' attribute value of this field
        """
        return self.getAttr('var')

    def setVar(self, val):
        """
        Set 'var' attribute value of this field
        """
        return self.setAttr('var', val)

class DataForm(Node):
    """
    Used for manipulating dataforms in XMPP

    Relevant XEPs: 0004, 0068, 0122. Can be used in disco, pub-sub and many
    other applications.
    """
    def __init__(self, typ=None, data=None, title=None, node=None):
        """
        Create new dataform of type 'typ'. 'data' is the list of DataField
        instances that this dataform contains, 'title' - the title string.  You
        can specify the 'node' argument as the other node to be used as base for
        constructing this dataform

        title and instructions is optional and SHOULD NOT contain newlines.
        Several instructions MAY be present.
        'typ' can be one of ('form' | 'submit' | 'cancel' | 'result' )
        'typ' of reply iq can be ( 'result' | 'set' | 'set' | 'result' )
            respectively.
        'cancel' form can not contain any fields. All other forms contains
            AT LEAST one field.
        'title' MAY be included in forms of type "form" and "result"
        """
        Node.__init__(self, 'x', node=node)
        if node:
            newkids = []
            for n in self.getChildren():
                if n.getName() == 'field':
                    newkids.append(DataField(node=n))
                else:
                    newkids.append(n)
            self.kids = newkids
        if typ:
            self.setType(typ)
        self.setNamespace(Namespace.DATA)
        if title:
            self.setTitle(title)
        if data is not None:
            if isinstance(data, dict):
                newdata = []
                for name in data.keys():
                    newdata.append(DataField(name, data[name]))
                data = newdata
            for child in data:
                if child.__class__.__name__ == 'DataField':
                    self.kids.append(child)
                elif isinstance(child, Node):
                    self.kids.append(DataField(node=child))
                else:  # Must be a string
                    self.addInstructions(child)

    def getType(self):
        """
        Return the type of dataform
        """
        return self.getAttr('type')

    def setType(self, typ):
        """
        Set the type of dataform
        """
        self.setAttr('type', typ)

    def getTitle(self):
        """
        Return the title of dataform
        """
        return self.getTagData('title')

    def setTitle(self, text):
        """
        Set the title of dataform
        """
        self.setTagData('title', text)

    def getInstructions(self):
        """
        Return the instructions of dataform
        """
        return self.getTagData('instructions')

    def setInstructions(self, text):
        """
        Set the instructions of dataform
        """
        self.setTagData('instructions', text)

    def addInstructions(self, text):
        """
        Add one more instruction to the dataform
        """
        self.addChild('instructions', {}, [text])

    def getField(self, name):
        """
        Return the datafield object with name 'name' (if exists)
        """
        return self.getTag('field', attrs={'var': name})

    def setField(self, name):
        """
        Create if nessessary or get the existing datafield object with name
        'name' and return it
        """
        f = self.getField(name)
        if f:
            return f
        return self.addChild(node=DataField(name))

    def asDict(self):
        """
        Represent dataform as simple dictionary mapping of datafield names to
        their values
        """
        ret = {}
        for field in self.getTags('field'):
            name = field.getAttr('var')
            typ = field.getType()
            if typ and typ.endswith('-multi'):
                val = []
                for i in field.getTags('value'):
                    val.append(i.getData())
            else:
                val = field.getTagData('value')
            ret[name] = val
        if self.getTag('instructions'):
            ret['instructions'] = self.getInstructions()
        return ret

    def __getitem__(self, name):
        """
        Simple dictionary interface for getting datafields values by their names
        """
        item = self.getField(name)
        if item:
            return item.getValue()
        raise IndexError('No such field')

    def __setitem__(self, name, val):
        """
        Simple dictionary interface for setting datafields values by their names
        """
        return self.setField(name).setValue(val)
