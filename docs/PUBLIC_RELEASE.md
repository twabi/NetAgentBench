# Publishing this repository

This checklist is for maintainers after a **security / history cleanup** (for example purging `.env` or other secrets from git history).

## Before you push

1. **Rotate credentials** that were ever committed or shared. History rewrite does **not** revoke API keys.
2. **Clone fresh** or run `git fetch --all` after collaborators rewrite history; old clones may reference removed objects.
3. **Document breaking changes** in release notes if `main` history was rewritten.

## History rewrite (already done in this repo if you used `git filter-repo`)

To remove a path such as `.env` from all commits:

```bash
poetry run pip install git-filter-repo
cd /path/to/network-benchmark
poetry run git filter-repo --invert-paths --path .env --force
git remote add origin https://github.com/<org>/<repo>.git   # filter-repo removes remotes
```

Then **force-push** every branch you publish:

```bash
git push origin --force --all
git push origin --force --tags
```

Notify collaborators to **re-clone** or hard-reset to the new `main`.

## Public mirror

To push only a branch to another remote (for example a public fork):

```bash
git remote add public https://github.com/<org>/<public-repo>.git
git push public main:main
```

Replace URLs and branch names as needed.

## References

- [git-filter-repo](https://github.com/newren/git-filter-repo)
- [SECURITY.md](../SECURITY.md)
