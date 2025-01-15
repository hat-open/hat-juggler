#!/bin/sh

set -e

RUN_PATH=$(dirname "$(realpath "$0")")
PLAYGROUND_PATH=$RUN_PATH/..
. $PLAYGROUND_PATH/env.sh

exec $PYTHON $RUN_PATH/server.py $ROOT_PATH $RUN_PATH/index.html
