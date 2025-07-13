# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import cast
from typing import Literal
from typing import TYPE_CHECKING

import datetime
import logging
import re
from dataclasses import dataclass
from dataclasses import field

from nbxmpp.language import LanguageMap
from nbxmpp.language import LanguageTag
from nbxmpp.modules.base import BaseModule
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.date_and_time import to_xmpp_dt
from nbxmpp.modules.url_data import UrlData
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.simplexml import Node
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import create_language_map_from_nodes

if TYPE_CHECKING:
    from nbxmpp.client import Client


log = logging.getLogger("nbxmpp.m.sfs")

rx_mediatype = re.compile(r"[a-z\/-]*")


class StatelessFileSharing(BaseModule):
    def __init__(self, client: Client) -> None:
        BaseModule.__init__(self, client)
        self._client = client
        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_message,
                ns=Namespace.SFS,
                priority=15,
            ),
        ]

    def _process_message(
        self,
        _client: Client,
        stanza: Message,
        properties: MessageProperties,
    ) -> None:

        file_sharings: list[FileSharing] = []
        for file_sharing in stanza.getTags("file-sharing", namespace=Namespace.SFS):
            try:
                file_sharings.append(FileSharing.from_node(file_sharing))
            except Exception as e:
                self._log.warning("Unable to parse file sharing node: %s", e)
                self._log.warning(stanza)

        unique_ids = {fs.id for fs in file_sharings}
        if len(file_sharings) > len(unique_ids):
            self._log.warning("file ids are not unique")
            self._log.warning(stanza)
            return

        properties.sfs = file_sharings

        if file_sharings:
            return

        sources_list: list[FileSources] = []
        for sources in stanza.getTags("sources", namespace=Namespace.SFS):
            try:
                source = FileSources.from_node(sources)
            except Exception as e:
                self._log.warning("Unable to parse sources node: %s", e)
                self._log.warning(stanza)
                continue

            if source.id is None:
                self._log.warning("Source without id")
                self._log.warning(stanza)
                continue

            sources_list.append(source)

        unique_ids = {sources.id for sources in sources_list}
        if len(sources_list) > len(unique_ids):
            self._log.warning("source ids are not unique")
            self._log.warning(stanza)
            return

        properties.sfs_sources = sources_list


def parse_media_type(media_type: str | None) -> str | None:
    if not media_type:
        return None

    media_type = media_type.lower()
    if rx_mediatype.fullmatch(media_type) is None:
        log.warning("unallowed chars in media-type: %s", media_type)
        return None

    return media_type


def get_int_value_from_tag(node: Node, tag: str) -> int | None:
    try:
        return int(node.getTagData(tag) or "")
    except Exception:
        return None


def get_int_value_from_attr(node: Node, attr: str) -> int | None:
    try:
        return int(node.getAttr(attr) or "")
    except Exception:
        return None


@dataclass
class Thumbnail:
    uri: str
    media_type: str | None = None
    width: int | None = None
    height: int | None = None

    def to_node(self) -> Node:
        if not self.uri:
            raise ValueError("uri is a required field")

        attrs: dict[str, str] = {"uri": self.uri}
        if self.media_type:
            attrs["media-type"] = self.media_type

        if self.width:
            attrs["width"] = str(self.width)

        if self.height:
            attrs["height"] = str(self.height)

        return Node(tag=f"{Namespace.THUMBNAIL} thumbnail", attrs=attrs)

    @classmethod
    def from_node(cls, thumbnail: Node) -> Thumbnail:
        width = get_int_value_from_attr(thumbnail, "width")
        height = get_int_value_from_attr(thumbnail, "height")

        media_type = parse_media_type(thumbnail.getAttr("media-type"))

        uri = thumbnail.getAttr("uri")
        if not uri:
            raise ValueError("missing uri node")

        return cls(uri=uri, media_type=media_type, width=width, height=height)


@dataclass
class Hash:
    algo: str
    value: str

    def to_node(self) -> Node:
        if not self.algo or not self.value:
            raise ValueError("algo and value are required fields")

        return Node(
            tag=f"{Namespace.HASHES_2} hash",
            attrs={"algo": self.algo},
            payload=self.value,
        )

    @classmethod
    def from_node(cls, hash_: Node) -> Hash:
        algo = hash_.getAttr("algo")
        if not algo:
            raise ValueError("missing algo attr")

        value = hash_.getData()
        if not value:
            raise ValueError("missing hash value")

        return cls(algo=algo, value=value)


@dataclass
class FileMetadata:
    date: datetime.datetime | None
    desc: LanguageMap | None
    hashes: list[Hash]
    height: int | None
    width: int | None
    length: int | None
    media_type: str | None
    name: str | None
    size: int | None
    thumbnails: list[Thumbnail] = field(default_factory=list)

    def add_desc(self, desc: str, lang: str | None = None) -> None:
        if self.desc is None:
            self.desc = LanguageMap()

        tag = LanguageTag(tag=lang) if lang else None
        self.desc[tag] = desc

    def to_node(self) -> Node:
        metadata = Node(tag=f"{Namespace.FILE_METADATA} file")
        if self.date is not None:
            metadata.setTagData("date", to_xmpp_dt(self.date))

        if self.desc is not None:
            lang, desc = cast(tuple[str | None, str], self.desc.any())
            attrs: dict[str, str] = {}
            if lang is not None:
                attrs = {"xml:lang": lang}

            metadata.addChild("desc", attrs=attrs, payload=[desc])

        for hash_ in self.hashes:
            metadata.addChild(node=hash_.to_node())

        if self.height is not None:
            metadata.setTagData("height", self.height)

        if self.width is not None:
            metadata.setTagData("width", self.width)

        if self.length is not None:
            metadata.setTagData("length", self.length)

        if self.media_type is not None:
            metadata.setTagData("media-type", self.media_type)

        if self.name is not None:
            metadata.setTagData("name", self.name)

        if self.size is not None:
            metadata.setTagData("size", self.size)

        for thumbnail in self.thumbnails:
            metadata.addChild(node=thumbnail.to_node())

        return metadata

    @classmethod
    def from_node(cls, metadata: Node) -> FileMetadata:
        date = parse_datetime(metadata.getTagData("date"))
        assert isinstance(date, (datetime.datetime | None))

        desc = create_language_map_from_nodes(metadata.getTags("desc")) or None

        name = metadata.getTagData("name") or None
        media_type = (
            parse_media_type(metadata.getTagData("media-type"))
            or "application/octet-stream"
        )

        height = get_int_value_from_tag(metadata, "height")
        width = get_int_value_from_tag(metadata, "width")
        length = get_int_value_from_tag(metadata, "length")
        size = get_int_value_from_tag(metadata, "size")

        hashes: list[Hash] = []
        for hash_ in metadata.getTags("hash", namespace=Namespace.HASHES_2):
            try:
                hashes.append(Hash.from_node(hash_))
            except Exception as e:
                log.warning("Unable to parse hash node: %s", e)
                log.warning(hash_)

        if not hashes:
            raise ValueError("hash missing")

        thumbnails: list[Thumbnail] = []
        for thumbnail in metadata.getTags("thumbnail", namespace=Namespace.THUMBNAIL):
            try:
                thumbnails.append(Thumbnail.from_node(thumbnail))
            except Exception as e:
                log.warning("Unable to parse thumbnail node: %s", e)
                log.warning(thumbnail)

        return cls(
            date=date,
            desc=desc,
            hashes=hashes,
            height=height,
            width=width,
            length=length,
            media_type=media_type,
            name=name,
            size=size,
            thumbnails=thumbnails,
        )


@dataclass
class FileSources:
    id: str | None
    sources: list[UrlData] = field(default_factory=list)

    def to_node(self) -> Node:
        sources = Node(tag=f"{Namespace.SFS} sources")
        for source in self.sources:
            sources.addChild(node=source.to_node())

        return sources

    @classmethod
    def from_node(cls, sources_node: Node) -> FileSources:
        id_ = sources_node.getAttr("id") or None

        sources: list[UrlData] = []
        for data in sources_node.getTags("url-data", namespace=Namespace.URL_DATA):
            sources.append(UrlData.from_node(data))

        return cls(id=id_, sources=sources)


@dataclass
class FileSharing:
    file: FileMetadata
    id: str | None = None
    disposition: Literal["inline", "attachment"] | None = None
    sources: FileSources | None = None

    def to_node(self) -> Node:
        fs = Node(tag=f"{Namespace.SFS} file-sharing")
        if self.id:
            fs.setAttr("id", self.id)
        if self.disposition:
            fs.setAttr("disposition", self.disposition)

        fs.addChild(node=self.file.to_node())
        if self.sources:
            fs.addChild(node=self.sources.to_node())
        return fs

    @classmethod
    def from_node(cls, sfs: Node) -> FileSharing:
        disposition = sfs.getAttr("disposition")
        if disposition not in ("inline", "attachment"):
            disposition = None

        id_ = sfs.getAttr("id") or None

        metadata = sfs.getTag("file", namespace=Namespace.FILE_METADATA)
        if metadata is None:
            raise ValueError("missing file node")
        file = FileMetadata.from_node(metadata)

        sources = sfs.getTag("sources", namespace=Namespace.SFS)
        if sources is not None:
            sources = FileSources.from_node(sources)
        else:
            sources = None

        if id_ is None and sources is None:
            raise ValueError("fileshare id is missing")

        return cls(file=file, sources=sources, id=id_, disposition=disposition)
