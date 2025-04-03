# Ensure script runs in the repository root
$ErrorActionPreference = "Stop"

# Load DEPLOY_TOKEN variable from .env file
$envFile = ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^(.*?)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
} else {
    Write-Host "ERROR: .env file not found!"
    exit 1
}

# Define variables
$PYTHON_VERSIONS = @("3.10", "3.11", "3.12")
$POETRY_VERSION = "2.1.1"
$DOCKERFILE_PATH = ".gitlab/docker/dockerfile"
$REGISTRY_URL = "git-reg.ptw.maschinenbau.tu-darmstadt.de"
$IMAGE_PATH = "eta-fabrik/public/eta-connect/"

# Ensure DEPLOY_TOKEN is set
if (-not $env:DEPLOY_TOKEN) {
    Write-Host "ERROR: DEPLOY_TOKEN is not set. Please check your .env file."
    exit 1
}

# Log in to Docker registry
$loginCommand = "echo $env:DEPLOY_TOKEN | docker login $REGISTRY_URL --username PRIVATE-TOKEN --password-stdin"
Invoke-Expression $loginCommand
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to log in to the Docker registry."
    exit 1
}

# Loop through Python versions and build/push images
foreach ($PYTHON_VERSION in $PYTHON_VERSIONS) {
    $IMAGE_NAME = "$REGISTRY_URL`/$IMAGE_PATH`poetry$POETRY_VERSION`:py$PYTHON_VERSION"

    Write-Host "Building and pushing Docker image for Python $PYTHON_VERSION..."

    # Build Docker image
    $buildCommand = "docker build -t $IMAGE_NAME -f $DOCKERFILE_PATH --build-arg PYTHON_VERSION=$PYTHON_VERSION --build-arg POETRY_VERSION=$POETRY_VERSION ."
    Invoke-Expression $buildCommand
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to build Docker image for Python $PYTHON_VERSION"
        exit 1
    }

    # Push Docker image
    $pushCommand = "docker push $IMAGE_NAME"
    Invoke-Expression $pushCommand
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to push Docker image for Python $PYTHON_VERSION"
        exit 1
    }

    Write-Host "Finished building and pushing Docker image for Python $PYTHON_VERSION!"
}

Write-Host "All Docker images built and pushed successfully!"
