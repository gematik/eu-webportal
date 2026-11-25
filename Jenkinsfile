@Library('gematik-jenkins-shared-library') _

pipeline {
    agent none

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 45, unit: 'MINUTES')
        timestamps()
    }

    parameters {
        string(
            name: 'GITLAB_PROJECT_ID',
            defaultValue: '2380',
            description: 'Required for Dependency-Track uploads on the main branch'
        )
        string(
            name: 'DTRACK_PARENT_PROJECT',
            defaultValue: 'EU-Webportal',
            description: 'Dependency-Track parent project name'
        )
    }

    stages {
        stage('Compliance and dependency checks') {
            parallel {
                stage('OSPO repository checks') {
                    agent { label 'k8-backend-small' }
                    steps {
                        openSourceGuidelineCheck()
                    }
                }

                stage('npm checks') {
                    agent { label 'k8-web' }
                    steps {
                        script {
                            npmLogin()
                            npmInstall('', true)
                            npmCollectDependencyLicenses(
                                false,
                                '[OSPO-Policy-Bot] Add root npm dependency license texts',
                                false
                            )
                            npmAuditScan('--omit=dev', false, false, 'high')
                            npmCreateSBOM('json', '--omit dev', '1.6', false)
                        }

                        dir('frontend') {
                            script {
                                npmInstall('', true)
                            }
                            sh 'npm run format:check'
                            sh 'npm run typecheck'
                            sh 'npm run ism:generate'
                            sh 'npm test -- --watch=false'
                            sh 'npm run test:ism'

                            script {
                                npmCollectDependencyLicenses(
                                    false,
                                    '[OSPO-Policy-Bot] Add frontend dependency license texts',
                                    false
                                )
                                npmAuditScan('--omit=dev', false, false, 'high')
                                npmCreateSBOM('json', '--omit dev', '1.6', false)
                            }
                        }

                        archiveArtifacts(
                            artifacts: 'sbom.json,third-party-licenses/**,audit.json,frontend/sbom.json,frontend/third-party-licenses/**,frontend/audit.json',
                            allowEmptyArchive: false,
                            fingerprint: true
                        )

                        script {
                            if (env.BRANCH_NAME == 'main') {
                                if (!params.GITLAB_PROJECT_ID?.trim()) {
                                    error('Set GITLAB_PROJECT_ID to upload npm SBOM to Dependency-Track.')
                                }
                                if (!params.DTRACK_PARENT_PROJECT?.trim()) {
                                    error('Set DTRACK_PARENT_PROJECT for Dependency-Track uploads.')
                                }
                                dir('frontend') {
                                    npmDependencyTrack(
                                        params.GITLAB_PROJECT_ID.trim(),
                                        params.DTRACK_PARENT_PROJECT.trim(),
                                        'sbom.json'
                                    )
                                }
                            }
                        }
                    }
                    post {
                        unsuccessful {
                            archiveArtifacts(
                                artifacts: 'sbom.json,third-party-licenses/**,audit.json,frontend/sbom.json,frontend/third-party-licenses/**,frontend/audit.json',
                                allowEmptyArchive: true,
                                fingerprint: true
                            )
                        }
                    }
                }

                stage('Python checks') {
                    agent { label 'k8-backend-small' }
                    steps {
                        sh 'uv sync --locked'
                        sh 'uv run --locked python tools/check_versions.py'
                        sh 'uv run --locked ruff format --check tools tests'
                        sh 'uv run --locked ruff check tools tests'
                        sh 'uv run --locked mypy'
                        sh 'uv run --locked python -m unittest discover -s tests'
                        sh 'uv sync --locked --no-dev'
                        sh(
                            label: 'Create Python runtime SBOM',
                            script: '''mkdir -p reports
uv tool run --from cyclonedx-bom==7.5.0 cyclonedx-py environment .venv/bin/python \
  --mc-type application \
  --gather-license-texts \
  --output-reproducible \
  --output-format json \
  --output-file reports/sbom-python.json'''
                        )
                        archiveArtifacts(
                            artifacts: 'reports/sbom-python.json',
                            allowEmptyArchive: false,
                            fingerprint: true
                        )

                        script {
                            if (env.BRANCH_NAME == 'main') {
                                if (!params.GITLAB_PROJECT_ID?.trim()) {
                                    error('Set GITLAB_PROJECT_ID to upload Python SBOM to Dependency-Track.')
                                }
                                if (!params.DTRACK_PARENT_PROJECT?.trim()) {
                                    error('Set DTRACK_PARENT_PROJECT for Dependency-Track uploads.')
                                }
                                def parentProjectId = dependencyTrackGetProjectByName(
                                    params.DTRACK_PARENT_PROJECT.trim(),
                                    true
                                )
                                if (!parentProjectId?.trim()) {
                                    error('Could not resolve the Dependency-Track parent project.')
                                }
                                def pythonVersion = sh(
                                    returnStdout: true,
                                    script: ".venv/bin/python -c \"import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])\""
                                ).trim()
                                dependencyTrackPublish(
                                    'EU-Webportal Python',
                                    pythonVersion,
                                    '',
                                    params.GITLAB_PROJECT_ID.trim(),
                                    'Python runtime dependencies',
                                    'eu-webportal',
                                    parentProjectId,
                                    'reports/sbom-python.json'
                                )
                            }
                        }
                    }
                    post {
                        unsuccessful {
                            archiveArtifacts(
                                artifacts: 'reports/sbom-python.json',
                                allowEmptyArchive: true,
                                fingerprint: true
                            )
                        }
                    }
                }
            }
        }

        stage('Tag successful main build') {
            when {
                branch 'main'
            }
            agent { label 'k8-backend-small' }
            steps {
                script {
                    def projectVersion = sh(
                        returnStdout: true,
                        script: 'uv run --locked --no-sync --python 3.11 ' +
                            'python tools/check_versions.py --project-version'
                    ).trim()
                    def sourceCommit = sh(
                        returnStdout: true,
                        script: 'git rev-parse HEAD'
                    ).trim()
                    def sourceVersionTag = "v${projectVersion}-b.${env.BUILD_NUMBER}"

                    withEnv([
                        "SOURCE_VERSION_TAG=${sourceVersionTag}",
                        "SOURCE_COMMIT_SHA=${sourceCommit}"
                    ]) {
                        sh(
                            label: 'Tag and push successful main commit',
                            script: '''set -eu
        git tag "$SOURCE_VERSION_TAG" "$SOURCE_COMMIT_SHA"
        git push origin "refs/tags/$SOURCE_VERSION_TAG"'''
                        )
                    }
                }
            }
        }
    }
}
