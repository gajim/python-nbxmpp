FROM python:3.10-alpine

RUN apk update
RUN apk add --no-cache git python3 py3-pip
RUN pip install --no-cache-dir git+https://gitlab.com/gajim/release-helper.git
RUN pip install --no-cache-dir twine

CMD bash
