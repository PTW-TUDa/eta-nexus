@echo off
setlocal enabledelayedexpansion

REM NEEDS TO BE RUN IN THE ROOT OF THE REPOSITORY

REM Define the Python versions to build
set "PYTHON_VERSIONS=3.9 3.10 3.11"
set "POETRY_VERSION=2.1.1"
set "DOCKERFILE_PATH=.gitlab/docker/dockerfile"
set "REGISTRY_URL=git-reg.ptw.maschinenbau.tu-darmstadt.de"
set "IMAGE_PATH=/eta-fabrik/public/eta-connect/"

REM Login to the Docker registry
docker login %REGISTRY_URL%
if errorlevel 1 (
    echo Failed to login to the Docker registry.
    exit /b 1
)

rem Loop through each Python version and build/push the Docker image
for %%V in (%PYTHON_VERSIONS%) do (
    set "PYTHON_VERSION=%%V"
    set "IMAGE_NAME=%REGISTRY_URL%%IMAGE_PATH%poetry%POETRY_VERSION%:py!PYTHON_VERSION!"

    echo Building and pushing Docker image for Python !PYTHON_VERSION!...

    rem Build the Docker image
    docker build -t !IMAGE_NAME! -f %DOCKERFILE_PATH% --build-arg PYTHON_VERSION=!PYTHON_VERSION! --build-arg POETRY_VERSION=%POETRY_VERSION% .
    if errorlevel 1 (
        echo Failed to build Docker image for Python !PYTHON_VERSION!
        exit /b 1
    )

    rem Push the Docker image to the registry
    docker push !IMAGE_NAME!
    if errorlevel 1 (
        echo Failed to push Docker image for Python !PYTHON_VERSION!
        exit /b 1
    )

    echo Finished building and pushing Docker image for Python !PYTHON_VERSION!
)

echo All Docker images built and pushed successfully.
