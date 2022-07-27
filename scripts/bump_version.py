#!/usr/bin/env python3

import re
import argparse
from pathlib import Path
import subprocess

REPO_DIR = Path(__file__).resolve().parent.parent


INIT = REPO_DIR / 'nbxmpp' / '__init__.py'
CFG = REPO_DIR / 'setup.cfg'
CHANGELOG = REPO_DIR / 'ChangeLog'

VERSION_RX = r'\d+\.\d+\.\d+'


def get_current_version() -> str:
    content = INIT.read_text(encoding='utf8')
    match = re.search(VERSION_RX, content)
    if match is None:
        exit('Unable to find current version')
    return match[0]


def bump_version(current_version: str, new_version: str) -> None:
    content = INIT.read_text(encoding='utf8')
    content = content.replace(current_version, new_version, 1)
    INIT.write_text(content, encoding='utf8')

    content = CFG.read_text(encoding='utf8')
    content = content.replace(current_version, new_version, 1)
    CFG.write_text(content, encoding='utf8')


def make_changelog(new_version: str) -> None:

    cmd = [
        'git-chglog',
        '--next-tag',
        new_version
    ]

    result = subprocess.run(cmd,
                            cwd=REPO_DIR,
                            text=True,
                            check=True,
                            capture_output=True)

    changes = result.stdout
    changes = changes.removeprefix('\n')

    current_changelog = CHANGELOG.read_text()

    with CHANGELOG.open('w') as f:
        f.write(changes + current_changelog)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bump Version')
    parser.add_argument('version', help='The new version, e.g. 1.5.0')
    args = parser.parse_args()

    current_version = get_current_version()

    bump_version(current_version, args.version)
    make_changelog(args.version)
