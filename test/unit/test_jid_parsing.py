import unittest

from nbxmpp.protocol import LocalpartByteLimit
from nbxmpp.protocol import LocalpartNotAllowedChar
from nbxmpp.protocol import ResourcepartByteLimit
from nbxmpp.protocol import ResourcepartNotAllowedChar
from nbxmpp.protocol import DomainpartByteLimit
from nbxmpp.protocol import DomainpartNotAllowedChar
from nbxmpp.protocol import JID

class JIDParsing(unittest.TestCase):

    def test_valid_jids(self):
        tests = [
            'juliet@example.com',
            'juliet@example.com/foo',
            'juliet@example.com/foo bar',
            'juliet@example.com/foo@bar',
            'foo\\20bar@example.com',
            'fussball@example.com',
            'fu\U000000DFball@example.com',
            '\U000003C0@example.com',
            '\U000003A3@example.com/foo',
            '\U000003C3@example.com/foo',
            '\U000003C2@example.com/foo',
            'king@example.com/\U0000265A',
            'example.com',
            'example.com/foobar',
            'a.example.com/b@example.net',
        ]

        for jid in tests:
            JID(jid)

    def test_invalid_jids(self):
        tests = [
            ('"juliet"@example.com', LocalpartNotAllowedChar),
            ('foo bar@example.com', LocalpartNotAllowedChar),
            ('henry\U00002163@example.com', LocalpartNotAllowedChar),
            ('@example.com', LocalpartByteLimit),
            ('user@example.com/', ResourcepartByteLimit),
            ('user@example.com/\U00000001', ResourcepartNotAllowedChar),
            ('\U0000265A@example.com', LocalpartNotAllowedChar),
            ('user@host@example.com', DomainpartNotAllowedChar),
            ('juliet@', DomainpartByteLimit),
            ('/foobar', DomainpartByteLimit),
        ]

        for jid, exception in tests:
            with self.assertRaises(exception):
                JID(jid)

    def test_ip_literals(self):
        tests = [
            ('juliet@[2002:4559:1FE2::4559:1FE2]/res'),
            ('juliet@123.123.123.123/res'),
        ]

        for jid in tests:
            JID(jid)
