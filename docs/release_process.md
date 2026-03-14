# Release Process

This process keeps releases predictable and reviewable.

## 1. Versioning

- Use semantic version tags: `vMAJOR.MINOR.PATCH`
- Increment:
  - `PATCH` for bug fixes and maintenance
  - `MINOR` for backward-compatible features
  - `MAJOR` for breaking changes

## 2. Release Branch and Cut

1. Create a release branch from default branch:

```bash
git checkout -b release/vX.Y.Z
```

2. Ensure quality gates pass:

```bash
bash scripts/check_backend_quality.sh
```

3. Update `CHANGELOG.md` with release date and notable changes.

## 3. Review and Approval

- Open a PR from release branch to default branch.
- Require at least one maintainer review.
- PR must include:
  - test evidence
  - migration notes (if any)
  - known limitations

## 4. Tag and Publish

After merge:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Create a GitHub Release from the tag with:

- changelog highlights
- compatibility notes
- operational caveats

## 5. Post-Release

- Verify CI status on tagged commit.
- Track regressions in issues.
- If rollback is needed, publish a patch release instead of force-rewriting history.
