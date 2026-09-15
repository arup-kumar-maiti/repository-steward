#!/usr/bin/env python3
# Copyright (c) 2026 Repository Steward contributors
"""Validate PR conventions."""

from __future__ import annotations

import http.client
import json
import os
import re
import sys
from http import HTTPStatus
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

SUBJECT_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9-]*(?:\([^)\r\n][^)\r\n]*\))?!?: [^\s].*$",
)
REQUIRED_SECTIONS = ("Summary", "Why", "Validation")
COMMITS_PER_PAGE = 100
REQUEST_TIMEOUT_SECONDS = 30


def main() -> None:
    """Validate the pull request described by the GitHub event payload."""
    event = load_event()
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        fail("this workflow must run for a pull request.")

    title = pull_request.get("title")
    body = pull_request.get("body") or ""
    number = event.get("number")
    repository = event.get("repository")
    if (
        not isinstance(title, str)
        or not isinstance(number, int)
        or not isinstance(repository, dict)
    ):
        fail("pull-request event payload is incomplete.")
    repository_name = repository.get("full_name")
    if not isinstance(repository_name, str):
        fail("pull-request repository is unavailable.")

    validate_subject(title, "PR title")
    validate_body(body)
    for subject in commit_subjects(repository_name, number):
        validate_subject(subject, "Commit subject")
    sys.stdout.write("PR conventions passed.\n")


def load_event() -> dict[str, object]:
    """Load the GitHub Actions event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        fail("GITHUB_EVENT_PATH is not set.")
    try:
        return json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"could not read the GitHub event payload: {error}")


def validate_subject(subject: str, label: str) -> None:
    """Validate a Conventional Commits subject."""
    if not SUBJECT_PATTERN.fullmatch(subject):
        message = (
            f"{label} must use Conventional Commits syntax: "
            "type(scope): description. Scope and ! are optional."
        )
        fail(message)


def validate_body(body: str) -> None:
    """Ensure every required PR section has content."""
    for heading in REQUIRED_SECTIONS:
        content = section_content(body, heading)
        if not content:
            fail(f"PR description needs meaningful content under '## {heading}'.")


def section_content(body: str, heading: str) -> str | None:
    """Return the non-comment content beneath one PR heading."""
    match = re.search(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",
        body,
    )
    if not match:
        return None
    return re.sub(r"(?s)<!--.*?-->", "", match.group(1)).strip()


def commit_subjects(repository: str, number: int) -> list[str]:
    """Read every pull-request commit subject through GitHub's API."""
    token = os.environ.get("GITHUB_TOKEN")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    if not token:
        fail("GITHUB_TOKEN is not set.")

    api_parts = urlsplit(api_url)
    if api_parts.scheme != "https" or not api_parts.netloc:
        fail("GITHUB_API_URL must be an HTTPS URL.")

    subjects: list[str] = []
    page = 1
    while True:
        commits = fetch_commit_page(api_parts, token, repository, number, page)
        subjects.extend(commit_subject(commit) for commit in commits)
        if len(commits) < COMMITS_PER_PAGE:
            return subjects
        page += 1


def fetch_commit_page(
    api_parts: SplitResult,
    token: str,
    repository: str,
    number: int,
    page: int,
) -> list[object]:
    """Request one page of pull-request commits from GitHub."""
    request_path = (
        f"{api_parts.path.rstrip('/')}/repos/{repository}/pulls/{number}/commits?"
        f"per_page={COMMITS_PER_PAGE}&page={page}"
    )
    connection = http.client.HTTPSConnection(
        api_parts.netloc,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    try:
        connection.request(
            "GET",
            request_path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response = connection.getresponse()
        if response.status >= HTTPStatus.BAD_REQUEST:
            message = (
                "could not read pull-request commits from GitHub: "
                f"HTTP {response.status}"
            )
            fail(message)
        commits = json.load(response)
    except (OSError, http.client.HTTPException, json.JSONDecodeError) as error:
        fail(f"could not read pull-request commits from GitHub: {error}")
    finally:
        connection.close()
    if not isinstance(commits, list):
        fail("GitHub returned an invalid pull-request commit response.")
    return commits


def commit_subject(commit: object) -> str:
    """Extract a commit's first message line from a GitHub API response."""
    if not isinstance(commit, dict):
        fail("GitHub returned an invalid commit entry.")
    commit_details = commit.get("commit")
    if not isinstance(commit_details, dict):
        fail("GitHub returned an invalid commit entry.")
    message = commit_details.get("message")
    if not isinstance(message, str):
        fail("GitHub returned a commit without a message.")
    return message.splitlines()[0]


def fail(message: str) -> None:
    """Exit with a PR convention error."""
    sys.stderr.write(f"PR convention failure: {message}\n")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
