# Repository Steward

A GitHub-first system for bootstrapping repositories with consistent changes,
on-demand code quality, and semantic releases.

## Available now

Reusable GitHub Actions workflow and template for PR conventions.

It checks:

- Conventional Commits headers for PR titles and commits
- `Summary`, `Why`, and `Validation` in PR descriptions

## Adopt

1. Copy the contents of `templates/child-repository` into the target
   repository's root.
2. Run:

   ```sh
   git config core.hooksPath .githooks
   ```

3. Create a `main` ruleset requiring pull requests and the
   `PR conventions / pr-conventions` check. Block force pushes and deletion.
