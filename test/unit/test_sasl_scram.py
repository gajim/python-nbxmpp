import unittest
from unittest.mock import Mock

from nbxmpp.sasl import SCRAM_SHA_1
from nbxmpp.util import b64encode

# Test vector from https://wiki.xmpp.org/web/SASL_and_SCRAM-SHA-1


class SCRAM(unittest.TestCase):
    def setUp(self):
        self.con = Mock()
        self.maxDiff = None
        self._username = 'user'
        self._password = 'pencil'
        self._mechanism = SCRAM_SHA_1(self._username, self._password, None)
        self._mechanism._client_nonce = 'fyko+d2lbbFgONRv9qkxdawL'

    def test_auth(self):
        initial = b64encode('n,,n=user,r=fyko+d2lbbFgONRv9qkxdawL')
        data = self._mechanism.get_initiate_data()
        self.assertEqual(data, initial)

        challenge = b64encode('r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=QSXCR+Q6sek8bf92,i=4096')
        data = self._mechanism.get_response_data(challenge)

        response = b64encode('c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=')
        self.assertEqual(data, response)

        success = b64encode('v=rmF9pqV8S7suAoZWja4dJRkFsKQ=')
        self._mechanism.validate_success_data(success)


if __name__ == '__main__':
    unittest.main()
