# Welcome to the EU Web Portal contributing guide

Thank you for investing your time in contributing to our project!

Read our [Code of Conduct](CODE_OF_CONDUCT.md) to keep our community
approachable and respectful.

## Publication status

This project is not yet approved for public release. External contributions
can be enabled only after publication and contribution licensing have been
approved.

## Reporting a security vulnerability

Do not report vulnerabilities or security incidents in public issues or pull
requests. Contact the
[Open Source Program Office](mailto:ospo@gematik.de?subject=%5BGitHub%5D%20eu-webportal)
or use the [contact form](https://fachportal.gematik.de/kontaktformular).
See also the [security policy](SECURITY.md).

## New contributor guide

To get an overview of the project, read the [README](../README.md).
Development commands are documented in its
[development section](../README.md#development).

## Getting started

### Issues

Once the project is published, everyone may submit issues and pull requests.
Search existing issues before opening a new report.

Scan existing issues for work you would like to contribute.

Issues and pull requests must describe the problem and the proposed solution.
Provide as much detail as necessary while keeping the description concise.

### Commit your update

Commit your changes once they are ready for review.
Branch names are unrestricted. Including the related issue number is
recommended when available.

### Formatting and linting

Use Prettier for frontend TypeScript, Angular templates, styles and JavaScript
tools. Use Ruff for Python formatting and linting.
Enabled Ruff rule groups are `E4`, `E7`, `E9`, `F`, `I`, `UP` and `B`.

```sh
npm --prefix frontend run format:check
uv run --locked ruff format --check tools tests
uv run --locked ruff check tools tests
```

These checks must pass in Jenkins before merge. To apply formatting locally,
run `npm --prefix frontend run format` and
`uv run --locked ruff format tools tests`.

### Coding conventions

Use English for identifiers, comments, documentation and user-facing text.
Tests must cover new and changed behavior.
Do not include confidential data in logs.
Team Eurovision is responsible for architecture decisions.

Use the existing Apache-2.0 source header for project-owned TypeScript,
JavaScript and Python files, including tests. Keep the README date reference
and preserve third-party copyright and license notices.
Record required attribution in [NOTICE](../NOTICE). Keep copied third-party
files unmodified where possible. Modified copies must state their source,
license and the change.

Avoid TypeScript `any`. Treat untrusted external data as `unknown` and
validate it before use.
Annotate parameters and return values of project-owned Python functions.
Reviewers verify these typing conventions. Ruff is not a type checker.
Jenkins checks Python annotations with mypy and frontend types with the
TypeScript and Angular compilers, including strict template checking.

```sh
npm --prefix frontend run typecheck
uv run --locked mypy
```

Python functions require complete parameter and return annotations.
TypeScript strict mode rejects implicit `any`. Explicit `any` must still be
avoided and reviewed, since the compiler does not prohibit it.

### Pull Request Process

1. Submit your changes through a fork and pull request.
2. Describe the purpose and behavior of your changes. Complete the pull request
   template if one is provided and link the related issue when resolving one.
3. Include tests for new logic and changed behavior. Update the
   [README](../README.md), relevant documentation and
   [release notes](../ReleaseNotes.md) when behavior or interfaces change.
4. Update version numbers in affected files and documentation as appropriate
   for the release. Follow [Semantic Versioning](https://semver.org/).
   The web portal and Python tools are versioned independently.
   Update the web portal version in `frontend/package.json` and its lockfile.
   Update the Python tools version in `pyproject.toml` and `uv.lock`.
   Only update the versions of components affected by the release.
5. A project team member will review your proposal and may request changes or
   additional information. Commit further changes to your fork and mark review
   conversations as resolved when addressed.
6. Changes to protected `main` must go through a pull request.
   At least one other developer must review and approve the changes,
   including dependency changes and applicable license obligations.
   If you lack permission to merge, ask an authorized team member.
   The project pipeline must also pass for the latest commit being merged.

### Your PR is merged!

Once the project is published, merged contributions will be publicly visible
on the [gematik GitHub page](https://github.com/gematik/).

## Release approval

Releases of both the web portal and Python tools require approval by the
Product Owner or their deputy in Team Eurovision. Required OSPO and legal
approvals remain separate prerequisites.

Successful CI checks and a completed review are required before release.
Document the CI results and approval by at least one other developer in the pull
request. The release record must reference the reviewed commit, its CI run
and the release approval.

A team member creates release tags and triggers publication after approval by
the Product Owner or their deputy. The release owner verifies and documents
license obligations using the internal release checklist, involving OSPO or
Legal where required.

## Restricted content

The currently planned publication scope includes all project components
except ISM data. This does not approve publication of models or media derived
from that data.

Do not include non-public ISM XML sources, unapproved derived models or media,
credentials or personal data in contributions. Do not upload builds or test
reports containing restricted content.

## Licensing

The team has selected Apache-2.0 for the project. See [LICENSE](../LICENSE).
Third-party components retain their respective licenses and notices.
Required attribution notices are listed in [NOTICE](../NOTICE).
External contributions remain blocked until publication and contribution
licensing have been approved.
