import datetime
from test.lib.util import StanzaHandlerTest

from nbxmpp.language import LanguageRange
from nbxmpp.modules.sfs import StatelessFileSharing
from nbxmpp.modules.sfs import UrlData
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties


class TestSFS(StanzaHandlerTest):

    def test_single_file(self):
        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='sharing-a-file'>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo1'>
                <file xmlns='urn:xmpp:file:metadata:0'>
                  <media-type>image/jpeg</media-type>
                  <name>summit.jpg</name>
                  <size>3032449</size>
                  <width>4096</width>
                  <height>2160</height>
                  <length>100</length>
                  <date>2015-07-26T21:46:00+01:00</date>
                  <hash xmlns='urn:xmpp:hashes:2' algo='sha3-256'>2XarmwTlNxDAMkvymloX3S5+VbylNrJt/l5QyPa+YoU=</hash>
                  <hash xmlns='urn:xmpp:hashes:2' algo='blake2b-256'>2AfMGH8O7UNPTvUVAM9aK13mpCY=</hash>
                  <desc>Photo from the summit.</desc>
                  <desc xml:lang='de-DE'>Foto vom summit.</desc>
                  <thumbnail xmlns='urn:xmpp:thumbs:1' uri='cid:sha1+ffd7c8d28e9c5e82afea41f97108c6b4@bob.xmpp.org' media-type='image/png' width='128' height='96'/>
                </file>
                <sources id='photo1'>
                  <url-data xmlns='http://jabber.org/protocol/url-data' target='https://download.montague.lit/4a771ac1-f0b2-4a4a-9700-f2a26fa2bb67/summit.jpg' />
                  <jinglepub xmlns='urn:xmpp:jinglepub:1' from='romeo@montague.lit/resource' id='9559976B-3FBF-4E7E-B457-2DAA225972BB'>
                    <description xmlns='urn:xmpp:jingle:apps:file-transfer:5' />
                  </jinglepub>
                </sources>
              </file-sharing>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module = StatelessFileSharing(self.client)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs), 1)
        self.assertEqual(len(props.sfs_sources), 0)
        fs = props.sfs[0]

        self.assertEqual(fs.id, "photo1")
        self.assertEqual(fs.disposition, "inline")

        self.assertEqual(fs.file.media_type, "image/jpeg")
        self.assertEqual(fs.file.name, "summit.jpg")
        self.assertEqual(fs.file.size, 3032449)
        self.assertEqual(fs.file.width, 4096)
        self.assertEqual(fs.file.height, 2160)
        self.assertEqual(fs.file.length, 100)

        tz = datetime.timezone(datetime.timedelta(hours=1))
        self.assertEqual(
            fs.file.date,
            datetime.datetime(2015, 7, 26, 21, 46, 0, tzinfo=tz),
        )

        self.assertEqual(len(fs.file.thumbnails), 1)
        thumbnail = fs.file.thumbnails[0]

        self.assertEqual(
            thumbnail.uri, "cid:sha1+ffd7c8d28e9c5e82afea41f97108c6b4@bob.xmpp.org"
        )
        self.assertEqual(thumbnail.media_type, "image/png")
        self.assertEqual(thumbnail.width, 128)
        self.assertEqual(thumbnail.height, 96)

        self.assertEqual(len(fs.file.hashes), 2)
        hash1, hash2 = fs.file.hashes

        self.assertEqual(hash1.algo, "sha3-256")
        self.assertEqual(hash1.value, "2XarmwTlNxDAMkvymloX3S5+VbylNrJt/l5QyPa+YoU=")
        self.assertEqual(hash2.algo, "blake2b-256")
        self.assertEqual(hash2.value, "2AfMGH8O7UNPTvUVAM9aK13mpCY=")

        assert fs.file.desc is not None

        self.assertEqual(fs.file.desc.any(), (None, "Photo from the summit."))
        self.assertEqual(
            fs.file.desc.lookup([LanguageRange(tag="de")]),
            ("de-DE", "Foto vom summit."),
        )

        assert fs.sources is not None
        self.assertEqual(fs.sources.id, "photo1")

        self.assertEqual(len(fs.sources.sources), 1)
        url_data = fs.sources.sources[0]
        self.assertIsInstance(url_data, UrlData)

    def test_multiple_files(self):
        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='sharing-files'>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo1.jpg'>
                <file xmlns='urn:xmpp:file:metadata:0'>
                  <name>photo1.jpg</name>
                  <hash xmlns='urn:xmpp:hashes:2' algo='blake2b-256'>2AfMGH8O7UNPTvUVAM9aK13mpCa=</hash>
                </file>
              </file-sharing>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo2.jpg'>
                <file xmlns='urn:xmpp:file:metadata:0'>
                  <name>photo2.jpg</name>
                  <hash xmlns='urn:xmpp:hashes:2' algo='blake2b-256'>2AfMGH8O7UNPTvUVAM9aK13mpCb=</hash>
                </file>
              </file-sharing>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo3.jpg'>
                <file xmlns='urn:xmpp:file:metadata:0'>
                  <name>photo3.jpg</name>
                  <hash xmlns='urn:xmpp:hashes:2' algo='blake2b-256'>2AfMGH8O7UNPTvUVAM9aK13mpCc=</hash>
                </file>
              </file-sharing>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module = StatelessFileSharing(self.client)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs), 3)
        fs1, fs2, fs3 = props.sfs

        self.assertEqual(fs1.id, "photo1.jpg")
        self.assertEqual(fs2.id, "photo2.jpg")
        self.assertEqual(fs3.id, "photo3.jpg")

    def test_attach_sources(self):
        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='adding-photo1'>
              <attach-to id='sharing-files' xmlns='urn:xmpp:message-attaching:1'/>
              <sources xmlns='urn:xmpp:sfs:0' id='photo1.jpg'>
                <url-data xmlns='http://jabber.org/protocol/url-data' target='https://download.montague.lit/4a771ac1-f0b2-4a4a-9700-f2a26fa2bb67/photo1.jpg' />
              </sources>
              <fallback xmlns='urn:xmpp:fallback:0' for='urn:xmpp:sfs:0'><body/></fallback>
              <body>https://download.montague.lit/4a771ac1-f0b2-4a4a-9700-f2a26fa2bb67/photo1.jpg</body>
              <x xmlns='jabber:x:oob'><url>https://download.montague.lit/4a771ac1-f0b2-4a4a-9700-f2a26fa2bb67/photo1.jpg</url></x>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module = StatelessFileSharing(self.client)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs), 0)
        self.assertEqual(len(props.sfs_sources), 1)
        source = props.sfs_sources[0]

        self.assertEqual(source.id, "photo1.jpg")
        self.assertIsInstance(source.sources[0], UrlData)

    def test_errors(self):

        module = StatelessFileSharing(self.client)

        # file missing

        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='sharing-files'>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo1.jpg'>
              </file-sharing>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs), 0)

        # hash algo missing

        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='sharing-files'>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo1.jpg'>
                <file xmlns='urn:xmpp:file:metadata:0'>
                  <name>photo1.jpg</name>
                  <hash xmlns='urn:xmpp:hashes:2'>2XarmwTlNxDAMkvymloX3S5+VbylNrJt/l5QyPa+YoU=</hash>
                </file>
              </file-sharing>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs), 0)

        # non-unique file ids

        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='sharing-files'>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo1.jpg'>
                <file xmlns='urn:xmpp:file:metadata:0' id="photo1">
                  <name>photo1.jpg</name>
                  <hash xmlns='urn:xmpp:hashes:2' algo='blake2b-256'>2AfMGH8O7UNPTvUVAM9aK13mpCa=</hash>
                </file>
              </file-sharing>
              <file-sharing xmlns='urn:xmpp:sfs:0' disposition='inline' id='photo1.jpg'>
                <file xmlns='urn:xmpp:file:metadata:0' id="photo1">
                  <name>photo2.jpg</name>
                  <hash xmlns='urn:xmpp:hashes:2' algo='blake2b-256'>2AfMGH8O7UNPTvUVAM9aK13mpCb=</hash>
                </file>
              </file-sharing>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs), 0)

        # non-unique source ids

        # language=XML
        xml = """
            <message to='juliet@shakespeare.lit' from='romeo@montague.lit/resource' id='sharing-files'>
              <sources xmlns='urn:xmpp:sfs:0' id='photo1.jpg'>
                <url-data xmlns='http://jabber.org/protocol/url-data' target='target2' />
              </sources>
              <sources xmlns='urn:xmpp:sfs:0' id='photo1.jpg'>
                <url-data xmlns='http://jabber.org/protocol/url-data' target='target1' />
              </sources>
            </message>
        """

        props = MessageProperties(own_jid=JID.from_string("example.com"))
        message = Message(node=xml)
        module._process_message(self.client, message, props)

        self.assertEqual(len(props.sfs_sources), 0)
