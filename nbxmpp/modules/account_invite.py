# Copyright (C) 2026 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of nbxmpp.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import datetime as dt

from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.protocol import Node
from nbxmpp.structs import AccountInviteResult


def parse_account_invite(form: Node) -> AccountInviteResult:
    form = SimpleDataForm(extend=form)
    assert isinstance(form, SimpleDataForm)
    # TODO: Check form type once its standardized
    # field = form.vars.get("FORM_TYPE")
    # if field is None:
    #     return None

    try:
        uri = form["uri"].value
    except Exception:
        raise ValueError("uri field is missing")

    assert isinstance(uri, str)
    if not uri:
        raise ValueError("empty uri value")

    try:
        landing_url = form["landing-url"].value or None
    except Exception:
        landing_url = None

    assert isinstance(landing_url, str | None)

    try:
        expire = parse_datetime(form["expire"].value)
    except Exception:
        expire = None

    assert isinstance(expire, dt.datetime | None)

    return AccountInviteResult(
        uri=uri,
        landing_url=landing_url,
        expire=expire,
    )
