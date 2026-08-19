import base64
import unittest
from unittest.mock import Mock

from nbxmpp.modules.omemo import OMEMO
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties

B64 = base64.b64encode(b"key-material").decode()


def _message(
    keys: str,
    *,
    sid: str = "27183",
    iv: str = B64,
    extra: str = "",
) -> Message:
    return Message(
        node=f"<message xmlns='jabber:client'>"
        f"<encrypted xmlns='{Namespace.OMEMO_TEMP}'><header sid='{sid}'>{keys}"
        f"<iv>{iv}</iv></header><payload>{B64}</payload></encrypted>{extra}</message>"
    )


class TestOmemoMessageHandler(unittest.TestCase):
    def test_malformed_envelope_preserves_error_metadata(self):
        stanza = _message(
            f"<key rid='1'>{B64}</key>",
            sid="23",
            iv="AB",
        )
        properties = MessageProperties(JID.from_string("romeo@example.test/gajim"))
        module = OMEMO(Mock(log_context="test"))

        module._process_omemo_message(Mock(), stanza, properties)

        self.assertIsNone(properties.omemo)
        error = properties.encryption_error
        assert error is not None
        self.assertEqual(error.protocol, "OMEMO")
        self.assertEqual(error.reason, "malformed-envelope")
        self.assertEqual(error.device_id, 23)


if __name__ == "__main__":
    unittest.main()
