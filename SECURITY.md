# Security Policy

## Supported Versions

The following versions of this project are currently being supported with security updates:

| Version | Supported |
| ------- | --------- |
| main    | ✅ Yes    |
| < 1.0   | ❌ No     |

If you are using an unsupported version, please upgrade to a supported version before reporting a vulnerability.

---

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public issue**.

Instead, report it privately using **one of the following methods**:

- **GitHub Security Advisories**  
  Use the “Report a vulnerability” button on the repository’s _Security_ tab.

- **Email**  
  Send details to: **cristiano.solarino@gmail.com**

Please include:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any relevant logs, screenshots, or proof-of-concept code

---

## Response Expectations

We aim to:

- Acknowledge receipt within **72 hours**
- Provide a status update within **7 days**
- Release a fix or mitigation as soon as reasonably possible

---

## Disclosure Policy

We follow **responsible disclosure** principles.  
Please do not publicly disclose vulnerabilities until we have had an opportunity to investigate and release a fix.

---

## Security Updates

Security fixes will be released as:

- Patches to the `main` branch
- Tagged releases (when applicable)
- GitHub Security Advisories

## Automated Security Controls

- CodeQL scans Python changes on pull requests and protected branches, with a
  weekly scheduled scan for newly disclosed query coverage.
- The frozen uv environment is exported with hashes and checked by `pip-audit`
  on pull requests, protected branches, and a weekly schedule.
- Dependabot monitors uv and GitHub Actions dependencies weekly and targets
  maintenance pull requests to `dev`.
- Release artifacts are built once, provenance-attested, smoke-tested in clean
  environments, and published through PyPI Trusted Publishing.

Repository owners must also enable Dependabot security updates, secret scanning,
push protection, CodeQL, and required security checks in GitHub settings. These
server-side controls cannot be enabled by repository files alone.

---

## Thanks

We appreciate responsible security researchers and community members who help keep this project safe.
