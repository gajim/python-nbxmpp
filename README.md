# Welcome to python-nbxmpp

`python-nbxmpp` is a Python library that provides a way for Python applications to use the XMPP network. This library was initially a fork of `xmpppy`.

## Runtime Requirements

- [Python](https://www.python.org/) (>=3.10)
- [PyGObject](https://pypi.org/project/PyGObject/) (>=3.42.0)
- [GLib](https://gitlab.com/gnome/glib) (>=2.66.0)
- [libsoup3](https://libsoup.gnome.org/)
- [precis-i18n](https://pypi.org/project/precis-i18n/) (>=1.0.0)
- [packaging](https://pypi.org/project/packaging/)
- [idna](https://pypi.org/project/idna/)

## Optional Runtime Requirements

- [python-gssapi](https://pypi.org/project/gssapi/) GSSAPI authentication

## Build Requirements

- [setuptools](https://pypi.org/project/setuptools/) (>=65.0.0)

## Tests

- `python -m unittest discover -s test`

## Features

- List of [supported XEPs](https://xmpp.org/software/libraries/python-nbxmpp/)

### Setup

Run the following:

```shell
pip install .
```

or

```shell
    pip install .[gssapi]
```

to also install the optional dependency `gssapi`.

### Usage

To use python-nbxmpp, `import nbxmpp` in your application.

To see an example check out [nbxmpp-client](https://pypi.org/project/nbxmpp-client/)
