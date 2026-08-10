import unittest

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
