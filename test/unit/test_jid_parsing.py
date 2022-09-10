import os
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
            JID.from_string(jid)

    def test_invalid_jids(self):
        tests = [
            ('"juliet"@example.com', LocalpartNotAllowedChar),
            ('foo bar@example.com', LocalpartNotAllowedChar),
            ('@example.com', LocalpartByteLimit),
            ('user@example.com/', ResourcepartByteLimit),
            ('user@example.com/\U00000001', ResourcepartNotAllowedChar),
            ('user@host@example.com', DomainpartNotAllowedChar),
            ('juliet@', DomainpartByteLimit),
            ('/foobar', DomainpartByteLimit),
        ]

        for jid, exception in tests:
            with self.assertRaises(exception):
                JID.from_string(jid)

    def test_invalid_precis_jids(self):
        os.environ['NBXMPP_ENFORCE_PRECIS'] = 'true'
        tests = [
            ('henry\U00002163@example.com', LocalpartNotAllowedChar),
            ('\U0000265A@example.com', LocalpartNotAllowedChar),
        ]

        for jid, exception in tests:
            with self.assertRaises(exception):
                JID.from_string(jid)

        del os.environ['NBXMPP_ENFORCE_PRECIS']

    def test_ip_literals(self):
        tests = [
            ('juliet@[2002:4559:1FE2::4559:1FE2]/res'),
            ('juliet@123.123.123.123/res'),
        ]

        for jid in tests:
            JID.from_string(jid)

    def test_jid_equality(self):
        tests = [
            'juliet@example.com',
            'juliet@example.com/foo',
            'example.com',
        ]

        for jid in tests:
            self.assertTrue(JID.from_string(jid) == JID.from_string(jid))

    def test_jid_escaping(self):
        # (user input, escaped)
        tests = [
            (r'space cadet@example.com',
             r'space\20cadet@example.com'),

            (r'call me "ishmael"@example.com',
             r'call\20me\20\22ishmael\22@example.com'),

            (r'at&t guy@example.com',
             r'at\26t\20guy@example.com'),

            ('d\'artagnan@example.com',
             r'd\27artagnan@example.com'),

            (r'/.fanboy@example.com',
             r'\2f.fanboy@example.com'),

            (r'::foo::@example.com',
             r'\3a\3afoo\3a\3a@example.com'),

            (r'<foo>@example.com',
             r'\3cfoo\3e@example.com'),

            (r'user@host@example.com',
             r'user\40host@example.com'),

            (r'c:\net@example.com',
             r'c\3a\net@example.com'),

            (r'c:\\net@example.com',
             r'c\3a\\net@example.com'),

            (r'c:\cool stuff@example.com',
             r'c\3a\cool\20stuff@example.com'),

            (r'c:\5commas@example.com',
             r'c\3a\5c5commas@example.com'),

            (r'call me\20@example.com',
             r'call\20me\5c20@example.com'),
        ]

        tests2 = [
            'juliet@example.com',
            'juliet@example.com',
            'juliet@example.com',
            'juliet@example.com',
            'fussball@example.com',
            'fu\U000000DFball@example.com',
            '\U000003C0@example.com',
            '\U000003A3@example.com',
            '\U000003C3@example.com',
            '\U000003C2@example.com',
            'example.com',
        ]

        test3 = [
            '\\20callme\\20@example.com',
            '\\20callme@example.com',
            'callme\\20@example.com',
        ]

        test4 = [
            ('call\\20me@example.com', 'call me@example.com',)
        ]

        fail_tests = [
            r'c:\5commas@example.com/asd',
            r'juliet@example.com/test'
        ]

        for user_input, escaped in tests:
            # Parse user input and escape it
            jid = JID.from_user_input(user_input)

            self.assertTrue(jid.domain == 'example.com')
            self.assertTrue(str(jid) == escaped)
            self.assertTrue(jid.to_user_string() == user_input)

            # We must fail on invalid JIDs
            with self.assertRaises(Exception):
                JID.from_string(user_input)

            # Parse escaped JIDs
            jid = JID.from_string(escaped)
            self.assertTrue(str(jid) == escaped)
            self.assertTrue(jid.domain == 'example.com')

        for jid in tests2:
            # show that from_string() and from_user_input() produce the same
            # result for valid bare JIDs
            self.assertTrue(JID.from_string(jid) == JID.from_user_input(jid))

        for jid in test3:
            # JIDs starting or ending with \20 are not escaped
            self.assertTrue(JID.from_string(jid).to_user_string() == jid)

        for user_input, user_string in test4:
            # Test escaped keyword argument
            self.assertTrue(JID.from_user_input(user_input, escaped=True) != JID.from_user_input(user_input))
            self.assertTrue(JID.from_user_input(user_input, escaped=True).to_user_string() == user_string)

        for user_input in fail_tests:
            # from_user_input does only support bare jids
            with self.assertRaises(Exception):
                JID.from_user_input(user_input)
