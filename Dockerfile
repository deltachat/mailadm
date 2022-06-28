FROM docker.io/alpine:latest

# Install Pillow (py3-pillow) from Alpine repository to avoid compiling it.
RUN apk add git py3-pip py3-pillow cmake clang clang-dev make gcc g++ libc-dev linux-headers cargo openssl-dev python3-dev libffi-dev

COPY . mailadm
WORKDIR mailadm
RUN pip install -U pip
RUN pip install .
