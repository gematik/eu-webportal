# EU Web Portal Demonstrator

The EU Web Portal project is an in-development demonstrator for cross-border
health services in the NCPeH context. It contains an Angular frontend and a
Python tool for working with OpenAPI and Arazzo specifications.

This project is not a production service. Live API calls, authentication, and
submission of patient searches are not implemented.

## Project status and publication restrictions

This repository is not approved for public release. The team has selected
Apache-2.0. Publication requires a successful GitHub Repository Guidelines
Compliance Report and the agreed release approval.

Original ISM XML source data is non-public and must not be published on GitHub.
The default frontend uses synthetic examples from `frontend/ism/public`.
Original sources remain in the internal GitLab dataset. The GitHub export also
excludes the real-country examples in `specs/ism/examples/`, internal
documentation, ISM analyses derived from real-country sources and generated
data.
Do not publish the internal checkout or its history directly. Confirm that the
public export and release artifacts contain no restricted data before publication.
The export workflow must explicitly process `.githubignore`.

Fictional countries use generated flag images. Real countries prefer emoji flags,
with MIT-licensed [flag-icons](https://github.com/lipis/flag-icons) SVGs as a
automatic fallback. Dataset selection and flag configuration are described in
[the frontend README](frontend/README.md).
Rights and attribution requirements for the remaining third-party assets,
including logos, must still be confirmed before publication.

## Getting started

`npm --prefix frontend start` uses public examples.
An additional dataset can be selected with
`npm --prefix frontend run start:internal` when its inputs are available.

### Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/)
- Node.js `^22.22.3`, `^24.15.0`, or `>=26.0.0` for the frontend
- npm

### Install

From the repository root, install the Python package and frontend dependencies:

```powershell
uv sync --locked
npm --prefix frontend ci
```

## Usage

### Run the frontend

```powershell
npm --prefix frontend start
```

The frontend is available at `http://localhost:4200`.

The public ISM demonstration uses synthetic examples without access to internal
data. The internal dataset requires authorized access and must remain excluded
from the public export.

### Use the OpenAPI and Arazzo tool

The CLI validates OpenAPI 3.1.x and Arazzo 1.1.x specifications, checks their
consistency, and supports mock servers and workflow tests. Commands require a
configuration file that points to the specifications:

```powershell
uv run python -m tools.openapi_arazzo_tool.cli --help
uv run python -m tools.openapi_arazzo_tool.cli validate-all --config <path-to-config>
```

See the [tool documentation](tools/openapi_arazzo_tool/README.md) for
configuration examples and additional commands.

## Development

Build and test the frontend:

```powershell
npm --prefix frontend run build
npm --prefix frontend test -- --watch=false
npm --prefix frontend run test:ism
```

Run the Python unit tests:

```powershell
uv run python -m unittest discover -s tests
```

## Jenkins checks

Formatting checks use Prettier for frontend sources and tools, and Ruff for
Python sources and tests.
Type checking uses mypy for Python and strict TypeScript/Angular compiler
checks for the frontend. See the
[contribution guide](.github/CONTRIBUTING.md#formatting-and-linting) for local
check and formatting commands. Existing formatting and lint violations must
be resolved before these gates pass.

The root `Jenkinsfile` is intended for a Jenkins Multibranch Pipeline with the
`gematik-jenkins-shared-library`. Configure `GITLAB_PROJECT_ID` for
Dependency-Track uploads on `main`; npm and Python checks run in parallel.
The Python SBOM targets the runtime environment at `.venv/bin/python`.
Jenkins runs `cyclonedx-bom==7.5.0` in an isolated environment through
`uv tool run`, without requiring a preinstalled agent tool or adding it to
the project runtime dependencies.
Available dependency reports are archived even if a later check fails.
The ISM tool test script selects test files explicitly for Node.js 22 support.
`versions.toml` is the central source for project, portal and Python-tool
versions. CI checks the component versions against their manifests and lock
files. After all checks pass on `main`, Jenkins tags the checked commit as
`v<project-version>-b.<build-number>`.

### GitHub publication

Releases are published to GitHub as a filtered source export of a tagged
`main` build. `.githubignore` lists the paths excluded from the export.
Each export opens a pull request that is reviewed and merged manually.
Internal job setup is documented in `README.internal.md`, which is not part
of the export.

The pipeline generates the public ISM dataset but does not publish the frontend.
Default `prebuild` uses synthetic examples only. Internal builds are explicitly
selected and must never be published. Release approval still requires checking
the filtered source export, history, asset rights and release artifacts.

## Documentation

- [Release notes](ReleaseNotes.md)
- [Security policy](.github/SECURITY.md)
- [Contribution guide](.github/CONTRIBUTING.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)
- [Implementation plan](docs/implementation-plan.md)
- [Architecture decisions](docs/adr/)
- [Architecture diagrams](docs/architecture/)
- [Frontend documentation](frontend/README.md)
- [OpenAPI and Arazzo tool documentation](tools/openapi_arazzo_tool/README.md)

## Contributing and contact

See the [contribution guide](.github/CONTRIBUTING.md) and
[Code of Conduct](.github/CODE_OF_CONDUCT.md). External contributions remain
blocked until publication and contribution licensing have been approved.

## License

Copyright 2026 gematik GmbH

Apache License, Version 2.0

See [LICENSE](LICENSE) for permissions and limitations.
Third-party components retain their respective licenses and notices.
Required attribution notices are listed in [NOTICE](NOTICE).

## Additional Notes and Disclaimer from gematik GmbH

1. Copyright notice: Each published work result is accompanied by an explicit statement of the
   license conditions for use. These are regularly typical conditions in connection with open source
   or free software. Programs described/provided/linked here are free software, unless otherwise
   stated.
2. Permission notice: Permission is hereby granted, free of charge, to any person obtaining a copy
   of this software and associated documentation files (the "Software"), to deal in the Software
   without restriction, including without limitation the rights to use, copy, modify, merge,
   publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to
   whom the Software is furnished to do so, subject to the following conditions:
    1. The copyright notice (Item 1) and the permission notice (Item 2) shall be included in all
       copies or substantial portions of the Software.
    2. The software is provided "as is" without warranty of any kind, either express or implied,
       including, but not limited to, the warranties of fitness for a particular purpose,
       merchantability, and/or non-infringement. The authors or copyright holders shall not be
       liable in any manner whatsoever for any damages or other claims arising from, out of or in
       connection with the software or the use or other dealings with the software, whether in an
       action of contract, tort, or otherwise.
    3. The software is the result of research and development activities, therefore not necessarily
       quality assured and without the character of a liable product. For this reason, gematik does
       not provide any support or other user assistance (unless otherwise stated in individual cases
       and without justification of a legal obligation). Furthermore, there is no claim to further
       development and adaptation of the results to a more current state of the art.
3. Gematik may remove published results temporarily or permanently from the place of publication at
   any time without prior notice or justification.
4. Parts of this software and - in isolated cases - content such as text or images may have been
   developed using the support of AI tools. They are subject to the same reviews, tests, and
   security checks as any other contribution. The functionality of the software itself is not based
   on AI decisions.
