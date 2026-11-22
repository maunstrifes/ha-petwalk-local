"""Fail if the repository would publish personal data.

This project is developed against a real door in a real home. Two things from that
environment must never reach the public repository:

* private network addresses (RFC 1918), which reveal the home network layout, and
* real e-mail addresses, in files, commit messages or commit identities.

Tests and docs use the RFC 5737 documentation ranges (192.0.2.0/24, 198.51.100.0/24,
203.0.113.0/24) and RFC 2606 example domains instead.

The check covers tracked and untracked (not ignored) files, so it catches a leak
before it is committed, as well as every commit in the history.

Usage: python scripts/check_privacy.py [REPOSITORY]
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
import re
import subprocess
import sys

PRIVATE_NETWORKS = [
    ipaddress.ip_network(net)
    for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
]

# Four dotted numbers, not part of a longer dotted sequence, not a CIDR range.
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.]|/\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-\[\]]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

ALLOWED_EMAILS = {"noreply@anthropic.com", "noreply@github.com"}
ALLOWED_EMAIL_SUFFIXES = (
    "@users.noreply.github.com",
    # RFC 2606 reserved names.
    "@example.com",
    "@example.net",
    "@example.org",
    ".example.com",
    ".example.net",
    ".example.org",
    ".example",
    ".invalid",
    ".test",
)


def _is_private(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in net for net in PRIVATE_NETWORKS)


def is_allowed_email(address: str) -> bool:
    """Return whether an e-mail address may appear in the public repository."""
    lowered = address.lower()
    return lowered in ALLOWED_EMAILS or lowered.endswith(ALLOWED_EMAIL_SUFFIXES)


def find_problems(text: str) -> list[tuple[int, str]]:
    """Return (line number, description) for every finding in a text."""
    problems: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        problems.extend(
            (number, f"private IPv4 address {match}")
            for match in IPV4.findall(line)
            if _is_private(match)
        )
        problems.extend(
            (number, f"e-mail address {match}")
            for match in EMAIL.findall(line)
            if not is_allowed_email(match)
        )
    return problems


def _git(repo: Path, *args: str) -> str | None:
    """Run git and return stdout, or None if git reports an error."""
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def _check_files(repo: Path) -> list[str]:
    listing = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    problems: list[str] = []
    for name in sorted(set(filter(None, (listing or "").split("\0")))):
        path = repo / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # Binary file.
        problems.extend(f"{name}:{line}: {what}" for line, what in find_problems(text))
    return problems


def _check_history(repo: Path) -> list[str]:
    problems: list[str] = []

    configured = (_git(repo, "config", "user.email") or "").strip()
    if configured and not is_allowed_email(configured):
        problems.append(f"git: configured user.email {configured}")

    identities = _git(repo, "log", "--all", "--format=%ae%n%ce") or ""
    problems.extend(
        f"git: commit identity {address}"
        for address in sorted(set(identities.split()))
        if not is_allowed_email(address)
    )

    messages = _git(repo, "log", "--all", "--format=%B") or ""
    problems.extend(
        f"git: commit message: {what}"
        for what in dict.fromkeys(what for _, what in find_problems(messages))
    )
    return problems


def check_repository(repo: Path) -> list[str]:
    """Return every privacy finding in the repository's files and history."""
    return _check_history(repo) + _check_files(repo)


def main(argv: list[str] | None = None) -> int:
    """Print findings and return a process exit code."""
    args = sys.argv[1:] if argv is None else argv
    repo = Path(args[0]) if args else Path.cwd()
    problems = check_repository(repo)
    for problem in problems:
        print(problem)
    if problems:
        print(
            f"\n{len(problems)} privacy finding(s). Use RFC 5737 addresses "
            "(192.0.2.x) and example.com in tests and docs, and commit with the "
            "GitHub noreply address."
        )
        return 1
    print("privacy check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
