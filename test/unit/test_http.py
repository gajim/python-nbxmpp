import os
import tempfile
import unittest
from pathlib import Path
from test.lib.util import raise_all_exceptions
from unittest.mock import Mock

from gi.repository import GLib
from gi.repository import Soup

from nbxmpp.const import HTTPRequestError
from nbxmpp.http import HTTPSession

SMALL_FILE_URL = "https://gajim.org/downloads/ci/unittest_small_file"  # 200 KB
BIG_FILE_URL = "https://gajim.org/downloads/ci/unittest_big_file"  # 7   MB
LARGE_FILE_URL = "https://gajim.org/downloads/ci/unittest_large_file"  # 80  MB
NO_FILE_URL = "https://gajim.org/downloads/ci/no-file"


# import logging
# consoleloghandler = logging.StreamHandler()
# log = logging.getLogger('nbxmpp.http')
# log.setLevel(logging.DEBUG)
# log.addHandler(consoleloghandler)


@unittest.skipUnless(
    os.environ.get("NBXMPP_EXTERNAL_UNIT_TESTS"), "ENV var for external tests not set"
)
class HTTP(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def test_download_to_file(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        callback_mock = Mock()

        temp_dir = tempfile.gettempdir()
        request.set_response_body_from_path(Path(temp_dir) / "file")
        request.connect("response-progress", callback_mock.progress)
        request.connect("starting-response-body", callback_mock.starting)
        request.connect("finished", callback_mock.finished)
        request.connect("destroy", lambda *args: mainloop.quit())

        request.send("GET", SMALL_FILE_URL, timeout=10)

        mainloop.run()

        self.assertTrue(request.is_complete())
        self.assertTrue(request.is_finished())
        self.assertIsNone(request.get_error())

        callback_mock.progress.assert_called()
        callback_mock.starting.assert_called()
        callback_mock.finished.assert_called()

    def test_in_memory_download(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        callback_mock = Mock()
        request.connect("response-progress", callback_mock.progress)
        request.connect("starting-response-body", callback_mock.starting)
        request.connect("finished", callback_mock.finished)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", SMALL_FILE_URL, timeout=10)

        mainloop.run()

        self.assertTrue(request.is_complete())
        self.assertTrue(request.is_finished())
        self.assertIsNone(request.get_error())

        callback_mock.progress.assert_called()
        callback_mock.starting.assert_called()
        callback_mock.finished.assert_called()

    def test_download_cancelled_before_start(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        callback_mock = Mock()
        request.connect("response-progress", callback_mock.progress)
        request.connect("starting-response-body", callback_mock.starting)
        request.connect("finished", callback_mock.finished)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", SMALL_FILE_URL, timeout=10)

        GLib.timeout_add(10, request.cancel)

        mainloop.run()

        self.assertFalse(request.is_complete())
        self.assertTrue(request.is_finished())
        self.assertEqual(request.get_error(), HTTPRequestError.CANCELLED)

        callback_mock.progress.assert_not_called()
        callback_mock.starting.assert_not_called()
        callback_mock.finished.assert_called()

    def test_download_cancelled_after_start(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        def _on_start(req):
            req.cancel()

        callback_mock = Mock()
        request.connect("starting-response-body", _on_start)
        request.connect("finished", callback_mock.finished)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", LARGE_FILE_URL, timeout=10)

        mainloop.run()

        self.assertFalse(request.is_complete())
        self.assertTrue(request.is_finished())
        self.assertEqual(request.get_error(), HTTPRequestError.CANCELLED)

        callback_mock.finished.assert_called()

    def test_download_failed_404(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        callback_mock = Mock()
        request.connect("finished", callback_mock.finished)
        request.connect("response-progress", callback_mock.progress)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", NO_FILE_URL, timeout=5)

        mainloop.run()

        self.assertFalse(request.is_complete())
        self.assertTrue(request.is_finished())
        self.assertEqual(request.get_error(), HTTPRequestError.STATUS_NOT_OK)
        self.assertEqual(request.get_status(), Soup.Status.NOT_FOUND)

        callback_mock.progress.assert_not_called()
        callback_mock.finished.assert_called()

    def test_cancel_with_timeout(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        callback_mock = Mock()
        request.connect("starting-response-body", callback_mock.starting)
        request.connect("finished", callback_mock.finished)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", LARGE_FILE_URL, timeout=1)

        mainloop.run()

        self.assertTrue(request.is_finished())
        self.assertFalse(request.is_complete())
        self.assertEqual(request.get_error(), HTTPRequestError.TIMEOUT)

        callback_mock.starting.assert_called()
        callback_mock.finished.assert_called()

    def test_signal_propagation(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        callback_mock = Mock()
        request.connect("starting", callback_mock.starting, 1, 2, 3)
        request.connect("got-body", callback_mock.got_body)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", SMALL_FILE_URL, timeout=10)

        mainloop.run()

        self.assertTrue(request.is_finished())
        self.assertTrue(request.is_complete())

        callback_mock.starting.assert_called_with(request, 1, 2, 3)
        callback_mock.got_body.assert_called_with(request)

    def test_parallel_download(self):

        mainloop = GLib.MainLoop()

        request1 = HTTPSession().create_request()
        request1.send("GET", SMALL_FILE_URL, timeout=5)

        request2 = HTTPSession().create_request()
        request2.send("GET", SMALL_FILE_URL, timeout=5)

        request3 = HTTPSession().create_request()
        request3.send("GET", SMALL_FILE_URL, timeout=5)

        request4 = HTTPSession().create_request()
        request4.send("GET", SMALL_FILE_URL, timeout=5)

        GLib.timeout_add_seconds(5, mainloop.quit)

        mainloop.run()

        self.assertTrue(request1.is_finished())
        self.assertTrue(request1.is_complete())

        self.assertTrue(request2.is_finished())
        self.assertTrue(request2.is_complete())

        self.assertTrue(request3.is_finished())
        self.assertTrue(request3.is_complete())

        self.assertTrue(request4.is_finished())
        self.assertTrue(request4.is_complete())

    @raise_all_exceptions
    def test_content_overflow(self):

        mainloop = GLib.MainLoop()

        session = HTTPSession()
        request = session.create_request()

        def _on_starting(req) -> None:
            req._received_size = 100000000000

        callback_mock = Mock()
        request.connect("starting-response-body", _on_starting)
        request.connect("finished", callback_mock.finished)
        request.connect("destroy", lambda *args: mainloop.quit())
        request.send("GET", SMALL_FILE_URL, timeout=10)

        mainloop.run()

        self.assertTrue(request.is_finished())
        self.assertFalse(request.is_complete())
        self.assertEqual(request.get_error(), HTTPRequestError.CONTENT_OVERFLOW)

        callback_mock.finished.assert_called()


if __name__ == "__main__":
    unittest.main()
