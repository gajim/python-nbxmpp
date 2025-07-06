import unittest

from nbxmpp.modules.url_data import HTTPUrlSchemeAuth
from nbxmpp.modules.url_data import HTTPUrlSchemeCookie
from nbxmpp.modules.url_data import HTTPUrlSchemeData
from nbxmpp.modules.url_data import UrlData
from nbxmpp.namespaces import Namespace
from nbxmpp.simplexml import Node


class TestUrlData(unittest.TestCase):

    def test_url_data(self):
        data = """
            <url-data xmlns='http://jabber.org/protocol/url-data' sid='sid1' target='https://example.com' />
        """

        url_data = UrlData.from_node(Node(node=data))
        self.assertEqual(url_data.target, "https://example.com")
        self.assertEqual(url_data.sid, "sid1")
        self.assertEqual(len(url_data.scheme_data), 0)

        # Required attribute missing

        data = "<url-data xmlns='http://jabber.org/protocol/url-data' sid='sid1' />"

        with self.assertRaises(ValueError) as cm:
            UrlData.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "missing target attribute")

        # Optional attribute missing

        data = "<url-data xmlns='http://jabber.org/protocol/url-data' target='https://example.com' />"

        url_data = UrlData.from_node(Node(node=data))
        self.assertEqual(url_data.target, "https://example.com")
        self.assertIsNone(url_data.sid)
        self.assertFalse(bool(url_data.scheme_data))

    def test_http_scheme_data(self):
        data = """
          <url-data xmlns='http://jabber.org/protocol/url-data'
              xmlns:http='http://jabber.org/protocol/url-data/scheme/http'
              target='https://example.com'>
            <http:auth scheme='basic'>
              <http:auth-param name='realm' value='www.jabber.org'/>
              <http:auth-param name='username' value='defaultuser'/>
            </http:auth>
            <http:cookie name='jsessionid'
                domain='jabber.org'
                max-age='1234000'
                path='/members'
                comment='Web Session Identifier'
                version='1.0'
                secure='true'
                value='1243asd234190sa32ds'/>
            <http:header name='data1' value='value1'/>
            <http:header name='data2' value='value2'/>
          </url-data>
        """

        url_data = UrlData.from_node(Node(node=data))
        self.assertEqual(url_data.target, "https://example.com")

        http_data = url_data.scheme_data[Namespace.URL_DATA_HTTP_SCHEME]
        self.assertIsInstance(http_data, HTTPUrlSchemeData)

        auth = http_data.auth
        assert auth is not None
        self.assertEqual(auth.scheme, "basic")

        params = [
            ("realm", "www.jabber.org"),
            ("username", "defaultuser"),
        ]

        self.assertListEqual(auth.params, params)

        cookie = http_data.cookie
        assert cookie is not None
        self.assertEqual(cookie.name, "jsessionid")
        self.assertEqual(cookie.domain, "jabber.org")
        self.assertEqual(cookie.max_age, 1234000)
        self.assertEqual(cookie.path, "/members")
        self.assertEqual(cookie.comment, "Web Session Identifier")
        self.assertEqual(cookie.version, "1.0")
        self.assertIs(cookie.secure, True)

        headers = [
            ("data1", "value1"),
            ("data2", "value2"),
        ]

        self.assertListEqual(http_data.headers, headers)

    def test_http_scheme_errors(self):

        # Cookie

        data = "<http:cookie name='jsessionid' max-age='-1' />"

        with self.assertRaises(ValueError) as cm:
            HTTPUrlSchemeCookie.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "invalid max-age: -1")

        data = "<http:cookie />"

        with self.assertRaises(ValueError) as cm:
            HTTPUrlSchemeCookie.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "missing name attribute")

        data = "<http:cookie name='jsessionid' secure='null' />"

        with self.assertRaises(ValueError) as cm:
            HTTPUrlSchemeCookie.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "unable to parse secure attribute")

        # Auth

        data = """
            <http:auth />
        """

        with self.assertRaises(ValueError) as cm:
            HTTPUrlSchemeAuth.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "missing scheme attribute")

        data = """
            <http:auth scheme='basic' xmlns:http='http://jabber.org/protocol/url-data/scheme/http'>
              <http:auth-param value='www.jabber.org'/>
              <http:auth-param name='username' value='defaultuser'/>
            </http:auth>
        """

        with self.assertRaises(ValueError) as cm:
            HTTPUrlSchemeAuth.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "missing name attribute")

        # Headers

        data = """
          <url-data xmlns='http://jabber.org/protocol/url-data'
              xmlns:http='http://jabber.org/protocol/url-data/scheme/http'
              target='https://example.com'>
            <http:header value='value1'/>
            <http:header name='data2' value='value2'/>
          </url-data>
        """

        with self.assertRaises(ValueError) as cm:
            HTTPUrlSchemeData.from_node(Node(node=data))

        self.assertEqual(str(cm.exception), "missing name attribute")

    def test_http_scheme_defaults(self):
        data = "<http:cookie name='jsessionid' />"

        cookie = HTTPUrlSchemeCookie.from_node(Node(node=data))

        self.assertIs(cookie.secure, False)
        self.assertEqual(cookie.version, "1.0")
        self.assertEqual(cookie.max_age, 0)
