#! /usr/bin/env bash
# Pull JuliaApiBox docker images

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
JBOX_DIR=`readlink -e ${DIR}/../..`

DOCKER_IMAGE_VER=$(grep "^# Version:" ${JBOX_DIR}/docker/Dockerfile | cut -d":" -f2)
DOCKER_IMAGE=juliabox/juliaboxapi

function build_docker_image {
    echo "Building docker image ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ..."
    sudo docker build --rm=true -t ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} docker/
    sudo docker tag ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ${DOCKER_IMAGE}:latest
}

function pull_docker_image {
    echo "Pulling docker image ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER} ..."
    sudo docker pull tanmaykm/juliaboxapi:${DOCKER_IMAGE_VER}
    sudo docker tag tanmaykm/juliaboxapi:${DOCKER_IMAGE_VER} ${DOCKER_IMAGE}:${DOCKER_IMAGE_VER}
    sudo docker tag tanmaykm/juliaboxapi:${DOCKER_IMAGE_VER} ${DOCKER_IMAGE}:latest
}

if [ "$1" == "pull" ]
then
    pull_docker_image
elif [ "$1" == "build" ]
then
    build_docker_image
else
    echo "Usage: img_create.sh <pull | build>"
fi

echo
echo "DONE!"
