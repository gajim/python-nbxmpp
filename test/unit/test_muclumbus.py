from __future__ import annotations

from typing import Any

import os
import unittest

from gi.repository import GLib

from nbxmpp.client import Client
from nbxmpp.http import HTTPSession
from nbxmpp.modules.muclumbus import Muclumbus
from nbxmpp.structs import MuclumbusResult

# Test vector from https://wiki.xmpp.org/web/SASL_and_SCRAM-SHA-1

API_URL = "https://search.jabber.network/api/1.0/search"


@unittest.skipUnless(
    os.environ.get("NBXMPP_EXTERNAL_UNIT_TESTS"), "ENV var for external tests not set"
)
class TestMuclumbus(unittest.TestCase):
    def setUp(self):
        self._client = Client()
        self._client.set_http_session(HTTPSession())
        self._module = Muclumbus(self._client)

    def test_http_request(self):

        mainloop = GLib.MainLoop()

        def _result(task: Any) -> None:
            result = task.finish()
            assert isinstance(result, MuclumbusResult)
            assert len(result.items) > 0
            mainloop.quit()

        self._module.set_http_search(API_URL, "gajim", callback=_result)

        mainloop.run()


if __name__ == "__main__":
    unittest.main()
