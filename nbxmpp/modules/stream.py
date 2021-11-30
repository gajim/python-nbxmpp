# This file is part of nbxmpp.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Optional
from typing import cast

from nbxmpp.namespaces import Namespace
from nbxmpp.elements import Base
from nbxmpp.elements import Nonza
from nbxmpp.builder import E
from nbxmpp.elements import register_class_lookup
from nbxmpp.elements import register_sub_element_lookup


class Features(Nonza):

    def has_starttls(self) -> tuple[bool, bool]:
        tls = self.find_tag('starttls', namespace=Namespace.TLS)
        if tls is not None:
            required = tls.find_tag('required') is not None
            return True, required
        return False, False

    def has_sasl(self) -> bool:
        return self.find_tag('mechanisms',
                             namespace=Namespace.XMPP_SASL) is not None

    def get_mechs(self) -> set[str]:
        mechanisms = self.find_tag('mechanisms', namespace=Namespace.XMPP_SASL)
        if mechanisms is None:
            return set()

        mechs = mechanisms.find_tags('mechanism')
        mechs = list(filter(lambda m: m.text is not None, mechs))
        return cast(set[str], {mech.text for mech in mechs})

    def get_domain_based_name(self) -> Optional[str]:
        hostname = self.find_tag('hostname',
                               namespace=Namespace.DOMAIN_BASED_NAME)
        if hostname is not None:
            return hostname.text or ''
        return None

    def has_bind(self) -> bool:
        return self.find_tag('bind', namespace=Namespace.BIND) is not None

    def session_required(self) -> bool:
        session = self.find_tag('session', namespace=Namespace.SESSION)
        if session is not None:
            optional = session.find_tag('optional') is not None
            return not optional
        return False

    def has_sm(self) -> bool:
        return self.find_tag('sm', namespace=Namespace.STREAM_MGMT) is not None

    def has_roster_version(self) -> bool:
        return self.find_tag('ver', namespace=Namespace.ROSTER_VER) is not None

    def has_register(self) -> bool:
        return self.find_tag(
            'register', namespace=Namespace.REGISTER_FEATURE) is not None

    def has_anonymous(self) -> bool:
        return 'ANONYMOUS' in self.get_mechs()


def make_bind_request(resource: Optional[str]) -> Base:
    iq = E('iq', type='set')
    bind = iq.add_tag('bind', namespace=Namespace.BIND)
    if resource is not None:
        res = bind.add_tag('resource')
        res.text = resource
    return iq


register_class_lookup('features', Namespace.STREAMS, Features)

register_sub_element_lookup(f'{{{Namespace.CLIENT}}}iq',
                            f'{{{Namespace.BIND}}}bind',
                            Nonza)
