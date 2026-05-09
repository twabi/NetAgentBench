# Security Policy

## Reporting a vulnerability

Please report security issues **privately** via [GitHub Security Advisories](https://github.com/twabi/network-benchmark/security/advisories/new) for this repository, or by opening a confidential issue if advisories are unavailable. Include steps to reproduce, affected versions, and impact.

We aim to acknowledge reports within a few business days.

## Scope

- This project runs **local containers** (Docker / Containerlab), **LLM API clients**, and coordinates with a separate **agent HTTP service** (for example dagent). Treat any host that runs the benchmark as executing **untrusted container images** you pull and **network-facing services** you bind.
- Never commit **API keys**, **tokens**, or **`.env`** files. Use `.env` locally (gitignored) and CI secrets for automation.
- If you **rewrote git history** (for example to purge accidental secrets), **assume old keys are compromised** and rotate them at the provider.

## Dependency scanning

Maintainers should periodically run `poetry run pip install pip-audit` and audit a **frozen** dependency list. Editable installs of this package may confuse `pip-audit`; prefer auditing the generated lock metadata or CI images that install from `--no-editable` wheels.

Upstream advisories landed after your last bump should be tracked here or in release notes once mitigations ship.
