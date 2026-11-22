"""Fail if the repository would publish personal data.

This project is developed against a real door in a real home. Two things from that
environment must never reach the public repository:

* private network addresses (RFC 1918), which reveal the home network layout, and
* real e-mail addresses.

Tests and docs use the RFC 5737 documentation ranges (192.0.2.0/24, 198.51.100.0/24,
203.0.113.0/24) and RFC 2606 example domains instead.

Checked are:

* tracked and untracked (not ignored) files, so a leak is caught before it is
  committed,
* every line ever added in the history, because deleting a leak in a later commit
  does not unpublish it,
* commit messages, commit identities and the configured ``user.email``.

If git fails, the check fails: nothing checked must never look like a pass.

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

# Four dotted numbers that are not part of a longer dotted sequence (a trailing full
# stop is fine), optionally followed by a prefix length.
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?!\d|\.\d)(?:/(\d{1,2}))?")
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


class GitError(RuntimeError):
    """A git command failed, so the repository could not be checked."""


def _is_private_host(address: str, prefix: str | None) -> bool:
    """Return whether the match names a device in a private network.

    Octets with leading zeros count as the same address. A range in CIDR notation
    (``10.0.0.0/8``) describes a rule, not a device, and is not reported.
    """
    octets = [int(part) for part in address.split(".")]
    if any(octet > 255 for octet in octets):
        return False
    ip = ipaddress.IPv4Address(".".join(str(octet) for octet in octets))
    if not any(ip in net for net in PRIVATE_NETWORKS):
        return False
    if prefix is None or int(prefix) > 32:
        return True
    network = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
    return int(prefix) == 32 or network.network_address != ip


def is_allowed_email(address: str) -> bool:
    """Return whether an e-mail address may appear in the public repository."""
    lowered = address.lower()
    return lowered in ALLOWED_EMAILS or lowered.endswith(ALLOWED_EMAIL_SUFFIXES)


def find_problems(text: str) -> list[tuple[int, str]]:
    """Return (line number, description) for every finding in a text."""
    problems: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        problems.extend(
            (number, f"private IPv4 address {address}")
            for address, prefix in IPV4.findall(line)
            if _is_private_host(address, prefix or None)
        )
        problems.extend(
            (number, f"e-mail address {match}")
            for match in EMAIL.findall(line)
            if not is_allowed_email(match)
        )
    return problems


def _git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> str:
    """Run git and return stdout; raise GitError on an unexpected exit code."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode not in ok:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _check_files(repo: Path) -> list[str]:
    listing = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    problems: list[str] = []
    for name in sorted(set(filter(None, listing.split("\0")))):
        path = repo / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # Binary file.
        problems.extend(f"{name}:{line}: {what}" for line, what in find_problems(text))
    return problems


def _unique(prefix: str, text: str) -> list[str]:
    return [
        f"{prefix}: {what}"
        for what in dict.fromkeys(what for _, what in find_problems(text))
    ]


def _check_history(repo: Path) -> list[str]:
    problems: list[str] = []

    # Exit code 1 means "not set", which is fine (for example on a CI runner).
    configured = _git(repo, "config", "--get", "user.email", ok=(0, 1)).strip()
    if configured and not is_allowed_email(configured):
        problems.append(f"git: configured user.email {configured}")

    if not _git(repo, "rev-list", "--all", "--max-count=1").strip():
        return problems  # No commits yet.

    identities = _git(repo, "log", "--all", "--format=%ae%n%ce")
    problems.extend(
        f"git: commit identity {address}"
        for address in sorted(set(identities.split()))
        if not is_allowed_email(address)
    )
    problems.extend(
        _unique("git: commit message", _git(repo, "log", "--all", "--format=%B"))
    )

    diff = _git(repo, "log", "--all", "-p", "--format=", "--no-color", "--no-ext-diff")
    added = "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    problems.extend(_unique("git: file content in history", added))
    return problems


def check_repository(repo: Path) -> list[str]:
    """Return every privacy finding in the repository's files and history."""
    _git(repo, "rev-parse", "--is-inside-work-tree")
    return _check_history(repo) + _check_files(repo)


def main(argv: list[str] | None = None) -> int:
    """Print findings and return 0 (clean), 1 (findings) or 2 (check failed)."""
    args = sys.argv[1:] if argv is None else argv
    repo = Path(args[0]) if args else Path.cwd()
    try:
        problems = check_repository(repo)
    except GitError as err:
        print(f"privacy check could not run: {err}")
        return 2
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
