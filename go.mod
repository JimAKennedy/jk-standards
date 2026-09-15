// Stub module, no Go code. This repository ships a pre-commit hook with
// language: golang (secrets-scan), and pre-commit unconditionally runs
// `go install ./...` in the hook repo before installing
// additional_dependencies — with no module file that build fails in every
// consumer's environment. The gitleaks binary itself comes from the hook's
// additional_dependencies pin in .pre-commit-hooks.yaml.
module github.com/JimAKennedy/jk-standards

go 1.24
