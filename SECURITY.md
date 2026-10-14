<!-- SPDX-License-Identifier: MIT -->
# Security policy

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability.

Report it privately through GitHub's **"Report a vulnerability"** flow under the repository's
**Security** tab (Security → Advisories → Report a vulnerability). This opens a private security
advisory visible only to the maintainers.

Please include:

- a description of the issue and its impact;
- steps to reproduce (a minimal proof of concept if possible);
- affected version or commit.

You can expect an acknowledgement and a coordinated path to a fix and disclosure. Please allow a
reasonable window before any public disclosure.

## Supported versions

This project is at an initial public release (`0.1.x`). Security fixes are applied to the latest
release.

## Scope notes

- The engine parses documents **in memory** and does not persist source files; source text is
  kept out of logs, traces, and error payloads.
- The supported core ships **no** deployment, authentication, storage, or secrets handling. The
  reference service under `examples/` is an **unsupported example**: if you deploy it, you own
  authentication, storage, secrets, network controls, and data-retention policy for your
  environment.
- The engine ships no API key. When you configure an LLM judge, protect your provider key using
  your environment's secrets practices.
