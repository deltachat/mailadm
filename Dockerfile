FROM docker.io/alpine:latest

# Install Pillow (py3-pillow) from Alpine repository to avoid compiling it.
RUN apk add py3-pip py3-pillow cmake clang clang-dev make gcc g++ libc-dev linux-headers cargo openssl-dev python3-dev libffi-dev
RUN pip install --break-system-packages -U pip

WORKDIR mailadm
RUN mkdir src
COPY setup.cfg pyproject.toml gunicorn.conf.py README.rst /mailadm/
COPY src src/
COPY assets assets/

RUN pip install --break-system-packages .
