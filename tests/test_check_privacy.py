"""Tests for scripts/check_privacy.py, the guard against leaking personal data."""

from pathlib import Path
import subprocess

import pytest

from scripts import check_privacy


def _ip(*parts: int) -> str:
    """Build an address from parts so this file does not trip the check it tests."""
    return ".".join(str(part) for part in parts)


PRIVATE_HOSTS = [
    _ip(10, 1, 2, 3),
    _ip(172, 16, 0, 9),
    _ip(172, 31, 255, 1),
    _ip(192, 168, 1, 20),
]
PUBLIC_OR_DOC_HOSTS = [
    "192.0.2.10",
    "198.51.100.7",
    "203.0.113.1",
    "172.32.0.1",
    "8.8.8.8",
]
LEAK = _ip(10, 0, 0, 5)
NOREPLY = "1+tester@users.noreply.github.com"


@pytest.mark.parametrize("host", PRIVATE_HOSTS)
def test_private_ipv4_is_reported(host: str) -> None:
    """Addresses from the RFC 1918 ranges are personal network details."""
    assert check_privacy.find_problems(f"host: {host}\n") == [
        (1, f"private IPv4 address {host}")
    ]


@pytest.mark.parametrize("host", PUBLIC_OR_DOC_HOSTS)
def test_documentation_and_public_addresses_pass(host: str) -> None:
    """RFC 5737 documentation addresses are what tests and docs should use."""
    assert check_privacy.find_problems(f"host = '{host}'") == []


def test_network_notation_is_not_a_host() -> None:
    """A CIDR range describes a rule, not somebody's device."""
    assert check_privacy.find_problems(f"ranges: {_ip(10, 0, 0, 0)}/8") == []
    assert check_privacy.find_problems(f"lan {_ip(192, 168, 0, 0)}/16.") == []


def test_host_with_prefix_length_is_reported() -> None:
    """An interface address like a.b.c.d/24 still names a device."""
    host = _ip(192, 168, 1, 20)
    assert check_privacy.find_problems(f"address {host}/24") == [
        (1, f"private IPv4 address {host}")
    ]


def test_address_at_the_end_of_a_sentence_is_reported() -> None:
    """A trailing full stop must not hide an address."""
    assert check_privacy.find_problems(f"The door is at {LEAK}.") == [
        (1, f"private IPv4 address {LEAK}")
    ]


def test_zero_padded_address_is_reported() -> None:
    """Leading zeros are another spelling of the same address."""
    padded = "192." + "168.001.020"
    assert check_privacy.find_problems(padded) == [
        (1, f"private IPv4 address {padded}")
    ]


def test_version_numbers_are_not_addresses() -> None:
    """Dotted versions with fewer or more parts must not match."""
    assert check_privacy.find_problems("ha 2026.8.2 and 1.2.3.4.5") == []


@pytest.mark.parametrize(
    "address",
    [
        "someone" + "@company.example.co",
        "first.last" + "@gmail.com",
    ],
)
def test_email_address_is_reported(address: str) -> None:
    """Real mailboxes must not be published."""
    assert check_privacy.find_problems(f"contact {address}") == [
        (1, f"e-mail address {address}")
    ]


@pytest.mark.parametrize(
    "address",
    [
        "1200404+someone@users.noreply.github.com",
        "noreply@anthropic.com",
        "noreply@github.com",
        # Dependabot's Signed-off-by trailer.
        "support@github.com",
        "user@example.com",
        "admin@petwalk.example.org",
    ],
)
def test_allowed_email_addresses_pass(address: str) -> None:
    """GitHub noreply and bot trailers, the co-author trailer and RFC 2606 domains."""
    assert check_privacy.find_problems(f"by {address}") == []


def test_line_numbers_point_at_the_finding() -> None:
    """Each finding names its line so it can be fixed quickly."""
    assert check_privacy.find_problems(f"ok\nok\nip {LEAK}\n") == [
        (3, f"private IPv4 address {LEAK}")
    ]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _make_repo(tmp_path: Path, email: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "user.email", email)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def test_commit_with_private_email_fails(tmp_path: Path) -> None:
    """A commit identity outside the allow list would be public forever."""
    address = "me" + "@company.example.co"
    repo = _make_repo(tmp_path, address)

    problems = check_privacy.check_repository(repo)

    assert f"git: commit identity {address}" in problems
    assert f"git: configured user.email {address}" in problems


def test_clean_repository_passes(tmp_path: Path) -> None:
    """A repository using the noreply identity and clean files passes."""
    repo = _make_repo(tmp_path, NOREPLY)

    assert check_privacy.check_repository(repo) == []


def test_untracked_files_are_scanned_before_they_are_committed(tmp_path: Path) -> None:
    """The check must catch a leak before it enters the history."""
    repo = _make_repo(tmp_path, NOREPLY)
    (repo / "notes.txt").write_text(f"door at {LEAK}\n", encoding="utf-8")

    assert check_privacy.check_repository(repo) == [
        f"notes.txt:1: private IPv4 address {LEAK}"
    ]


def test_binary_files_are_skipped(tmp_path: Path) -> None:
    """Images and other binary files cannot be scanned as text."""
    repo = _make_repo(tmp_path, NOREPLY)
    (repo / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")

    assert check_privacy.check_repository(repo) == []


def test_commit_messages_are_scanned(tmp_path: Path) -> None:
    """A commit message is published just like a file."""
    repo = _make_repo(tmp_path, NOREPLY)
    _git(repo, "commit", "-q", "--allow-empty", "-m", f"fix door at {LEAK}")

    assert check_privacy.check_repository(repo) == [
        f"git: commit message: private IPv4 address {LEAK}"
    ]


def test_removed_file_content_in_history_is_reported(tmp_path: Path) -> None:
    """Deleting a leak in a later commit does not take it out of the history."""
    repo = _make_repo(tmp_path, NOREPLY)
    (repo / "notes.txt").write_text(f"door at {LEAK}\n", encoding="utf-8")
    _git(repo, "add", "notes.txt")
    _git(repo, "commit", "-q", "-m", "add notes")
    _git(repo, "rm", "-q", "notes.txt")
    _git(repo, "commit", "-q", "-m", "remove notes")

    assert check_privacy.check_repository(repo) == [
        f"git: file content in history: private IPv4 address {LEAK}"
    ]


def test_repository_without_commits_is_checked(tmp_path: Path) -> None:
    """Before the first commit, files and configured identity are still checked."""
    repo = tmp_path / "fresh"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", NOREPLY)
    (repo / "notes.txt").write_text(f"door at {LEAK}\n", encoding="utf-8")

    assert check_privacy.check_repository(repo) == [
        f"notes.txt:1: private IPv4 address {LEAK}"
    ]


def test_failing_git_fails_the_check(tmp_path: Path) -> None:
    """Outside a repository nothing can be checked, which must not pass."""
    with pytest.raises(check_privacy.GitError):
        check_privacy.check_repository(tmp_path)

    assert check_privacy.main([str(tmp_path)]) == 2


def test_main_returns_nonzero_on_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command line entry point fails the build and names the finding."""
    repo = _make_repo(tmp_path, NOREPLY)
    (repo / "notes.txt").write_text(f"door at {LEAK}\n", encoding="utf-8")

    assert check_privacy.main([str(repo)]) == 1
    assert "notes.txt:1" in capsys.readouterr().out


def test_main_returns_zero_when_clean(tmp_path: Path) -> None:
    """A clean repository passes."""
    repo = _make_repo(tmp_path, NOREPLY)

    assert check_privacy.main([str(repo)]) == 0
