FROM debian:unstable-slim

COPY requirements.txt requirements.txt
RUN apt-get update
RUN apt-get -y install \
    python3 \
    build-essential \
    dh-python \
    debhelper-compat \
    pkg-config \
    python-is-python3 \
    python3-all \
    pybuild-plugin-pyproject \
    python3-venv \
    python3-gi \
    python3-gi-cairo \
    python3-gssapi \
    python3-idna \
    python3-pip \
    python3-packaging \
    python3-precis-i18n \
    python3-setuptools \
    python3-wheel \
    gir1.2-soup-3.0 \
    nodejs \
    npm

RUN npm install -g pyright@1.1.394

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv --system-site-packages $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir -r requirements.txt

CMD bash
