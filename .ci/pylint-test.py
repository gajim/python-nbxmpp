#!/usr/bin/env python3

import sys
import subprocess

DISABLED_CHECKS = [
    'C0103',  # invalid-name
    'C0201',  # consider-iterating-dictionary
    'C0206',  # consider-using-f-string
    'C0209',  # consider-using-dict-items
    'C0301',  # line-too-long
    'C0326',  # bad-whitespace
    'C0330',  # bad-continuation
    'W0201',  # attribute-defined-outside-init
    'W0212',  # protected-access
    'W0221',  # arguments-differ
    'W0223',  # abstract-method
    'W0231',  # super-init-not-called
    'W0233',  # non-parent-init-called
    'W0621',  # redefined-outer-name
    'W0622',  # redefined-builtin
    'W0707',  # raise-missing-from
    'R0201',  # no-self-use
    'R0801',  # duplicate-code
    'E1101',  # no-member
    'E1135',  # unsupported-membership-test
]


def run_pylint_test():

    cmd = [
        'pylint',
        'nbxmpp',
        f'--disable={",".join(DISABLED_CHECKS)}'
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        sys.exit('pylint test failed')


if __name__ == '__main__':
    run_pylint_test()
