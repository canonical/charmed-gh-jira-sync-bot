#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for https://github.com/canonical/gh-jira-sync-bot (FastAPI 12-factor)."""

import logging
import typing

import ops
import paas_charm.fastapi

logger = logging.getLogger(__name__)


class GitHubJiraBotCharm(paas_charm.fastapi.Charm):
    """FastAPI charm service for the GitHub Jira sync bot."""

    def __init__(self, *args: typing.Any) -> None:
        """Initialize the instance.

        Args:
            args: passthrough to CharmBase.
        """
        super().__init__(*args)


if __name__ == "__main__":
    ops.main(GitHubJiraBotCharm)
