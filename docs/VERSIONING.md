# Versioning (JR Golden SD)

We use SemVer tags for releases and `git describe` for build identity.

## Release tags (human)
- Tags: `vMAJOR.MINOR.PATCH` (example: `v0.1.0`)
- Tag only when:
  - working tree is clean
  - service restarts cleanly
  - `/api/health` does NOT include `-dirty`

## Build identity (machine)
`git describe --tags --dirty --always`
Examples:
- `v0.1.0`
- `v0.1.0-3-gc80e171`
- `v0.1.0-3-gc80e171-dirty`

## /api/health fields
- `version`
- `semver`
- `git_describe`
- `git_commit`
- `git_dirty`
- `version_source`
