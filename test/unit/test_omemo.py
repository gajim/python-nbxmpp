import unittest

from nbxmpp.modules.omemo import _parse_bundle
from nbxmpp.modules.omemo import _parse_devicelist
from nbxmpp.simplexml import Node


class OMEMOTest(unittest.TestCase):

    def test_parsing(self):

        devicelist = """
          <item id="current">
            <list xmlns="eu.siacs.conversations.axolotl">
              <device id="912561474" />
              <device id="532656838" />
              <device id="1" xmlns="test.namespace" />
            </list>
          </item>"""

        devices = _parse_devicelist(Node(node=devicelist))
        self.assertEqual(devices, [912561474, 532656838])

        bundle = """
          <item id='current'>
            <bundle xmlns='eu.siacs.conversations.axolotl'>
              <signedPreKeyPublic signedPreKeyId='1'>dGVzdHBheWxvYWQ=</signedPreKeyPublic>
              <signedPreKeySignature>dGVzdHBheWxvYWQ=</signedPreKeySignature>
              <identityKey>dGVzdHBheWxvYWQ=</identityKey>
              <prekeys>
                <preKeyPublic preKeyId='1'>dGVzdHBheWxvYWQ=</preKeyPublic>
                <preKeyPublic preKeyId='2'>dGVzdHBheWxvYWQ=</preKeyPublic>
                <preKeyPublic preKeyId='3'>dGVzdHBheWxvYWQ=</preKeyPublic>
                <preKeyPublic preKeyId='3' xmlns="test.namespace">dGVzdHBheWxvYWQ=</preKeyPublic>
              </prekeys>
            </bundle>
          </item>"""

        omemo_bundle = _parse_bundle(Node(node=bundle), 1)
        self.assertEqual(len(omemo_bundle.otpks), 3)
