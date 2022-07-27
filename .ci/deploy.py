#!/usr/bin/env python3

import os
import sys
import subprocess
from pathlib import Path


REPO_DIR = Path(__file__).parent.parent
USERNAME = '__token__'
PASSWORD = os.environ['PYPI_TOKEN']


def build() -> None:
    cmd = [
        'python3',
        'setup.py',
        'sdist',
        'bdist_wheel'
    ]

    try:
        subprocess.run(cmd, cwd=REPO_DIR, check=True)
    except subprocess.CalledProcessError:
        sys.exit('build failed')


def upload() -> None:
    cmd = [
        'twine',
        'upload',
        '--username', USERNAME,
        '--password', PASSWORD,
        'dist/*'
    ]

    try:
        subprocess.run(cmd, cwd=REPO_DIR, check=True)
    except subprocess.CalledProcessError:
        sys.exit('upload failed')


if __name__ == '__main__':
    # build()
    upload()
