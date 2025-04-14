#!/bin/bash

# NEEDS TO BE RUN IN THE ROOT DIRECTORY OF THE REPOSITORY

RED="\033[0;31m"
GREEN="\033[0;32m"
NC="\033[0m" # No Color

# Define the Python versions to build
PYTHON_VERSIONS=("3.9" "3.10" "3.11")
POETRY_VERSION="2.1.1"
DOCKERFILE_PATH=".gitlab/docker/dockerfile"
REGISTRY_URL="git-reg.ptw.maschinenbau.tu-darmstadt.de"
IMAGE_PATH="/eta-fabrik/public/eta-nexus/"

docker login ${REGISTRY_URL}
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to login to the Docker registry${NC}"
    exit 1
fi

# Loop through each Python version and build/push the Docker image
for PYTHON_VERSION in "${PYTHON_VERSIONS[@]}"; do
    IMAGE_NAME="${REGISTRY_URL}${IMAGE_PATH}poetry${POETRY_VERSION}:py${PYTHON_VERSION}"

    echo "Building and pushing Docker image for Python ${PYTHON_VERSION}..."

    # Build the Docker image
    docker build -t ${IMAGE_NAME} -f ${DOCKERFILE_PATH} --build-arg="PYTHON_VERSION=${PYTHON_VERSION}" --build-arg="POETRY_VERSION=${POETRY_VERSION}" .
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to build Docker image for Python ${PYTHON_VERSION}${NC}"
        exit 1
    fi

    # Push the Docker image to the registry
    docker push ${IMAGE_NAME}
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to push Docker image for Python ${PYTHON_VERSION}${NC}"
        exit 1
    fi

    echo -e "${GREEN}Finished building and pushing Docker image for Python ${PYTHON_VERSION}${NC}"
done

echo -e "${GREEN}All Docker images built and pushed successfully.${NC}"
