# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import logging

from nbxmpp.util import LogAdapter

if TYPE_CHECKING:
    from nbxmpp.client import Client


class BaseModule:

    _depends: dict[str, str] = {}

    def __init__(self, client: Client) -> None:
        logger_name = "nbxmpp.m.%s" % self.__class__.__name__.lower()
        self._log = LogAdapter(
            logging.getLogger(logger_name), {"context": client.log_context}
        )

    def __getattr__(self, name: str) -> Any:
        if name not in self._depends:
            raise AttributeError("Unknown method: %s" % name)

        module = self._client.get_module(self._depends[name])
        return getattr(module, name)
