set windows-shell := ["powershell", "-NoProfile", "-Command"]

# Arguments are positional: use `just validate my.yaml`, not `config=my.yaml`.
cli := "uv run python -m tools.openapi_arazzo_tool.cli"
config := "tool.yaml"

# Show all available recipes.
default:
    @just --list

help:
    {{cli}} --help

# --- Validation -----------------------------------------------------------

validate-openapi config=config:
    {{cli}} validate-openapi --config "{{config}}"

validate-arazzo config=config:
    {{cli}} validate-arazzo --config "{{config}}"

validate config=config:
    {{cli}} validate-all --config "{{config}}"

# --- Mocking --------------------------------------------------------------

# Export a versioned package without starting a server.
generate-mocks config=config:
    {{cli}} generate-mocks --config "{{config}}"

# Run the mock server in the foreground; stop it with Ctrl+C.
start-mocks config=config:
    {{cli}} start-mocks --config "{{config}}"

# Start exported routes without loading source specifications.
start-mock-package package_dir *arguments:
    {{cli}} start-mocks --package-dir "{{package_dir}}" {{arguments}}

stop-mocks config=config:
    {{cli}} stop-mocks --config "{{config}}"

# --- Workflows ------------------------------------------------------------

list-workflows config=config:
    {{cli}} list-workflows --config "{{config}}"

# Example: just run-workflow my-workflow --input 'id="42"'
run-workflow workflow *inputs:
    {{cli}} run-workflow {{workflow}} --config "{{config}}" {{inputs}}

test config=config:
    {{cli}} run-tests --config "{{config}}"

report config=config:
    {{cli}} report --config "{{config}}"

# --- Development ----------------------------------------------------------

unit:
    uv run python -m unittest discover -s tests

# --- Docker ---------------------------------------------------------------

docker-build:
    docker compose build

# Build an immutable image for a generated package version.
docker-build-mock package_dir version:
    docker build --build-arg MOCK_PACKAGE_DIR="{{replace(package_dir, "\\", "/")}}" --build-arg MOCK_PACKAGE_VERSION="{{version}}" --tag "euwp-mock:{{version}}" --file Dockerfile.mock .

# Example: just docker-run validate-all --config /workspace/config/tool.yaml
docker-run *arguments:
    docker compose run --rm tool {{arguments}}

# --- CI -------------------------------------------------------------------

# Verify a Git-tag checkout provided by the build system and validate it.
verify-checkout checkout repository-url tag config=config:
    uv run python -m tools.openapi_arazzo_tool.integration --checkout "{{checkout}}" --repository-url "{{repository-url}}" --tag "{{tag}}" --config "{{config}}"
