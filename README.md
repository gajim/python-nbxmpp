# Welcome to python-nbxmpp

`python-nbxmpp` is a Python library that provides a way for Python applications to use the XMPP network. This library was initially a fork of `xmpppy`.

## Runtime Requirements

- python >= 3.9.0
- PyGObject
- GLib >= 2.60
- libsoup
- precis-i18n
- packaging
- idna

## Optional Runtime Requirements

- python-gssapi (for GSSAPI authentication https://pypi.org/project/gssapi/)

## Features

* List of [supported XEPs](https://dev.gajim.org/gajim/python-nbxmpp/-/wikis/Supported-XEPs-in-python-nbxmpp/)

## Starting Points

* [Downloads](https://dev.gajim.org/gajim/python-nbxmpp/tags)
* You can also clone the [git repository](https://dev.gajim.org/gajim/python-nbxmpp.git)

### Setup

Run the following:

    pip install .

or

    pip install .[gssapi]

to also install the optional dependency `gssapi`.

### Usage

To use python-nbxmpp, `import nbxmpp` in your application.

or use the example client `python3 -m nbxmpp.examples.client`
