#!/bin/sh
# Runs a single `mailadm` command inside a temporary container.
SCRIPTS=$(realpath -- $(dirname "$0"))
DATA="$SCRIPTS/../docker-data"
ENVFILE="$SCRIPTS/../.env"
sudo docker run --mount type=bind,source="$DATA",target=/mailadm/docker-data --env-file "$ENVFILE" --rm mailadm-mailcow mailadm "$@"
