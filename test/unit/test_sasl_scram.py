import unittest
from unittest.mock import Mock

from nbxmpp.auth import SCRAM_SHA_1


class SCRAM(unittest.TestCase):
    def setUp(self):
        self.con = Mock()
        self._method = SCRAM_SHA_1(self.con, None)
        self._method._client_nonce = '4691d8f313ddb02d2eed511d5617a5c6f72efa671613c598'

        self._username = 'philw'
        self._password = 'testtest123'

        self.auth = '<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl" mechanism="SCRAM-SHA-1">eSwsbj1waGlsdyxyPTQ2OTFkOGYzMTNkZGIwMmQyZWVkNTExZDU2MTdhNWM2ZjcyZWZhNjcxNjEzYzU5OA==</auth>'
        self.challenge = 'cj00NjkxZDhmMzEzZGRiMDJkMmVlZDUxMWQ1NjE3YTVjNmY3MmVmYTY3MTYxM2M1OThDaEJpZGEyb0NJeks5S25QdGsxSUZnPT0scz1iZFkrbkRjdUhuVGFtNzgyaG9neHNnPT0saT00MDk2'
        self.response = '<response xmlns="urn:ietf:params:xml:ns:xmpp-sasl">Yz1lU3dzLHI9NDY5MWQ4ZjMxM2RkYjAyZDJlZWQ1MTFkNTYxN2E1YzZmNzJlZmE2NzE2MTNjNTk4Q2hCaWRhMm9DSXpLOUtuUHRrMUlGZz09LHA9NUd5a09hWCtSWlllR3E2L2U3YTE2UDVBeFVrPQ==</response>'
        self.success = 'dj1qMGtuNlVvT1FjTmJ0MGFlYnEwV1QzYWNkSW89'

    def test_auth(self):
        self._method.initiate(self._username, self._password)
        self.assertEqual(self.auth, str(self.con.send.call_args[0][0]))

        self._method.response(self.challenge)
        self.assertEqual(self.response, str(self.con.send.call_args[0][0]))

        self._method.success(self.success)
