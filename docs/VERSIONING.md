# Versioning (JR Golden SD)

We use SemVer tags for releases and `git describe` for build identity.

## Release tags (human)
- Tag format: `vMAJOR.MINOR.PATCH` (example: `v0.1.0`)
- Tag only when:
  - worktree clean
  - `./scripts/preflight.sh` passes
  - `/api/health` does NOT show `git_dirty: true`

## Build identity (machine)
`git describe --tags --dirty --always`
Examples:
- `v0.1.0`
- `v0.1.0-3-gc80e171`
- `v0.1.0-3-gc80e171-dirty`

## /api/health version fields
- `version` (primary display string)
- `semver`
- `git_describe`
- `git_commit`
- `git_dirty`
- `version_source` (`git` or `env`)

## Release checklist
1) `git status` is clean
2) `./scripts/preflight.sh`
3) `./scripts/tag-release.sh vX.Y.Z`
