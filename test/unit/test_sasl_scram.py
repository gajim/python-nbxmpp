import unittest
from unittest.mock import Mock

from nbxmpp.auth import SCRAM_SHA_1
from nbxmpp.util import b64encode

# Test vector from https://wiki.xmpp.org/web/SASL_and_SCRAM-SHA-1

class SCRAM(unittest.TestCase):
    def setUp(self):
        self.con = Mock()
        self._method = SCRAM_SHA_1(self.con, None)
        self._method._client_nonce = 'fyko+d2lbbFgONRv9qkxdawL'
        self.maxDiff = None
        self._username = 'user'
        self._password = 'pencil'

        self.auth = '<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl" mechanism="SCRAM-SHA-1">%s</auth>' % b64encode('n,,n=user,r=fyko+d2lbbFgONRv9qkxdawL')
        self.challenge = b64encode('r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=QSXCR+Q6sek8bf92,i=4096')
        self.response = '<response xmlns="urn:ietf:params:xml:ns:xmpp-sasl">%s</response>' % b64encode('c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=')
        self.success = b64encode('v=rmF9pqV8S7suAoZWja4dJRkFsKQ=')

    def test_auth(self):
        self._method.initiate(self._username, self._password)
        self.assertEqual(self.auth, str(self.con.send_nonza.call_args[0][0]))

        self._method.response(self.challenge)
        self.assertEqual(self.response, str(self.con.send_nonza.call_args[0][0]))

        self._method.success(self.success)


if __name__ == '__main__':
    unittest.main()
