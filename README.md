# Welcome to python-nbxmpp

`python-nbxmpp` is a Python library that provides a way for Python applications to use the XMPP network. This library was initially a fork of `xmpppy`.

## Runtime Requirements

- [Python](https://www.python.org/) (>=3.9)
- [PyGObject](https://pypi.org/project/PyGObject/) (>=3.42.0)
- [GLib](https://gitlab.com/gnome/glib) (>=2.60.0)
- [libsoup3](https://libsoup.org/)
- [precis-i18n](https://pypi.org/project/precis-i18n/)
- [packaging](https://pypi.org/project/packaging/)
- [idna](https://pypi.org/project/idna/)

## Optional Runtime Requirements

- [python-gssapi](https://pypi.org/project/gssapi/) GSSAPI authentication

## Build Requirements

- [setuptools](https://pypi.org/project/setuptools/)

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
