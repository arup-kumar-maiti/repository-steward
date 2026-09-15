# Copyright (c) 2026 Repository Steward contributors
"""Bootstrap Repository Steward in the current Git repository."""

from __future__ import annotations

import http.client
import shutil
import subprocess
import sys
from http import HTTPStatus
from pathlib import Path

HOOK_PATH = Path(".githooks/commit-msg")
INSTALLATION_FILES = (
    HOOK_PATH,
    Path(".github/PULL_REQUEST_TEMPLATE.md"),
    Path(".github/workflows/pr-conventions.yml"),
)
TEMPLATE_ROOT = Path(__file__).parent / "templates" / "child-repository"
RAW_CONTENT_HOST = "raw.githubusercontent.com"
RAW_CONTENT_PATH_PREFIX = (
    "/arup-kumar-maiti/repository-steward/main/templates/child-repository"
)


def main() -> None:
    """Install the currently supported Repository Steward templates."""
    repository_root = _repository_root()
    conflicts = _conflicts(repository_root)
    if conflicts:
        _fail("\n".join(["installation stopped; conflicts found:", *conflicts]))

    _copy_template_files(repository_root)
    _configure_hooks_path(repository_root)
    sys.stdout.write("Repository Steward bootstrap complete.\n")


def _repository_root() -> Path:
    """Return the current Git repository root or stop the installation."""
    result = _run_git("rev-parse", "--show-toplevel")
    if result.returncode != 0:
        _fail("run this script from the root of a Git repository.")

    repository_root = Path(result.stdout.strip()).resolve()
    if Path.cwd().resolve() != repository_root:
        _fail("run this script from the root of a Git repository.")
    return repository_root


def _run_git(
    *arguments: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a fixed Git command and capture its text output."""
    # The executable and every argument are controlled by this script.
    return subprocess.run(  # noqa: S603
        [_git_executable(), *arguments],
        capture_output=True,
        check=False,
        cwd=cwd,
        text=True,
    )


def _git_executable() -> str:
    """Return Git's absolute executable path or stop the installation."""
    executable = shutil.which("git")
    if executable is None:
        _fail("Git must be installed.")
    return executable


def _conflicts(repository_root: Path) -> list[str]:
    """Return every existing Repository Steward file or hook-path conflict."""
    conflicts = [
        str(destination)
        for destination in INSTALLATION_FILES
        if (repository_root / destination).exists()
        or (repository_root / destination).is_symlink()
    ]
    hooks_path = _local_hooks_path(repository_root)
    if hooks_path is not None and hooks_path != ".githooks":
        conflicts.append(f"core.hooksPath is already set to {hooks_path!r}")
    return conflicts


def _local_hooks_path(repository_root: Path) -> str | None:
    """Return the local Git hooks path, if configured."""
    result = _run_git(
        "config",
        "--local",
        "--get",
        "core.hooksPath",
        cwd=repository_root,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        _fail("could not read the local Git hooks path.")
    return result.stdout.strip()


def _copy_template_files(repository_root: Path) -> None:
    """Copy each template file after all conflicts have been ruled out."""
    for destination in INSTALLATION_FILES:
        target = repository_root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_template_content(destination))
        if destination == HOOK_PATH:
            target.chmod(0o755)


def _template_content(destination: Path) -> bytes:
    """Return local template content or download it for raw-script execution."""
    source = TEMPLATE_ROOT / destination
    if source.is_file():
        return source.read_bytes()
    return _download_template(destination)


def _download_template(destination: Path) -> bytes:
    """Download one template file from the public Repository Steward repository."""
    connection = http.client.HTTPSConnection(RAW_CONTENT_HOST, timeout=30)
    request_path = f"{RAW_CONTENT_PATH_PREFIX}/{destination.as_posix()}"
    try:
        connection.request("GET", request_path)
        response = connection.getresponse()
        if response.status != HTTPStatus.OK:
            _fail(f"could not download {destination}: HTTP {response.status}")
        return response.read()
    except (OSError, http.client.HTTPException) as error:
        _fail(f"could not download {destination}: {error}")
    finally:
        connection.close()


def _configure_hooks_path(repository_root: Path) -> None:
    """Configure Git to use the installed local hook directory."""
    result = _run_git(
        "config",
        "--local",
        "core.hooksPath",
        ".githooks",
        cwd=repository_root,
    )
    if result.returncode != 0:
        _fail("could not configure core.hooksPath.")


def _fail(message: str) -> None:
    """Report an installation error and stop."""
    sys.stderr.write(f"Bootstrap failure: {message}\n")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
