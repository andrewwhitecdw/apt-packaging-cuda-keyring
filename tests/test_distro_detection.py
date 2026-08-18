"""Regression test: default DISTRO detection in debian/rules.

Bug: when DISTRO is not passed on the make command line, debian/rules
derived it with:

    grep -oP '(?<=^ID=).*|(?<=^VERSION_ID=).*' /etc/os-release | paste -sd '\\0'

which (1) kept the quotes around VERSION_ID verbatim and (2) depended on
ID preceding VERSION_ID in the file. On Ubuntu 24.04 (VERSION_ID first)
that produced `"24.04"ubuntu` instead of `ubuntu2404`, yielding a
malformed apt sources.list pointing at a non-existent repo path.

Fix: source /etc/os-release and strip dots:

    . /etc/os-release && echo "${ID}${VERSION_ID}" | tr -d '.'

This test extracts the DISTRO shell pipeline from debian/rules and runs
it against fixture os-release files (both field orderings), asserting
the derived distro token.

Run: uv run --with pytest pytest tests/test_distro_detection.py
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES = REPO_ROOT / "debian" / "rules"

# (fixture os-release content, expected DISTRO)
CASES = [
    # Ubuntu 24.04 ordering: VERSION_ID appears before ID.
    (
        'PRETTY_NAME="Ubuntu 24.04 LTS"\n'
        'NAME="Ubuntu"\n'
        'VERSION_ID="24.04"\n'
        'VERSION="24.04 LTS (Noble Numbat)"\n'
        'VERSION_CODENAME=noble\n'
        'ID=ubuntu\n'
        'ID_LIKE=debian\n',
        "ubuntu2404",
    ),
    # Alternate ordering: ID before VERSION_ID.
    (
        'NAME="Ubuntu"\n'
        'ID=ubuntu\n'
        'ID_LIKE=debian\n'
        'PRETTY_NAME="Ubuntu 22.04.5 LTS"\n'
        'VERSION_ID="22.04"\n'
        'VERSION="22.04.5 LTS (Jammy Jellyfish)"\n'
        'VERSION_CODENAME=jammy\n',
        "ubuntu2204",
    ),
]


def _distro_pipeline() -> str:
    """Extract the shell command behind `DISTRO ?= $(shell ...)` from debian/rules."""
    match = re.search(r"^DISTRO\s*\?=\s*\$\(shell (.*)\)$", RULES.read_text(), re.M)
    assert match, "no DISTRO ?= $(shell ...) line found in debian/rules"
    command = match.group(1)
    # Undo make's $$ escaping so the command is runnable in a plain shell.
    return command.replace("$$", "$")


@pytest.mark.parametrize("os_release,expected", CASES)
def test_distro_detection(os_release, expected, tmp_path):
    fixture = tmp_path / "os-release"
    fixture.write_text(os_release)
    command = _distro_pipeline().replace("/etc/os-release", str(fixture))
    result = subprocess.run(
        ["bash", "-c", command], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == expected
