#! /usr/bin/env bash
# Restart JuliaApiBox server

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../..`

source ${DIR}/../jbapi_common.sh

cp_tornado_userconf

sudo supervisorctl -c ${PWD}/host/supervisord.conf restart all
