

from precis_i18n import get_profile


_localpart_disallowed_chars = set('"&\'/:<>@')


def enforce_precis_username(localpart: str) -> str:
    if _localpart_disallowed_chars & set(localpart):
        raise ValueError('Input contains prohibited codepoint: %s' % localpart)

    username = get_profile('UsernameCaseMapped')
    return username.enforce(localpart)


def enforce_precis_opaque(resourcepart: str) -> str:
    opaque = get_profile('OpaqueString')
    return opaque.enforce(resourcepart)
