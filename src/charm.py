#!/usr/bin/env python3
"""Charm code for https://github.com/canonical/gh-jira-sync-bot."""
import logging
import os

import ops

from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.redis_k8s.v0.redis import RedisRequires, RedisRelationCharmEvents
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

logger = logging.getLogger(__name__)


class GitHubJiraBotCharm(ops.CharmBase):
    """Charm class for https://github.com/canonical/gh-jira-sync-bot."""

    on = RedisRelationCharmEvents()

    def __init__(self, *args):
        super().__init__(*args)

        require_nginx_route(
            charm=self,
            service_hostname=self.app.name,
            service_name=self.app.name,
            service_port=int(self.config["port"])
        )

        self.redis = RedisRequires(self, "redis")

        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            "metrics-endpoint",
            jobs=[
                {
                    "job_name": self.model.app.name,
                    "metrics_path": "/metrics",
                    "static_configs": [{"targets": [f"*:{self.config['port']}"]}],
                    "scrape_interval": "15s",  # TODO: move to config.yaml
                    "scrape_timeout": "10s",
                }
            ],
        )

        self.framework.observe(self.on.gh_jira_bot_pebble_ready, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.redis_relation_updated, self._on_config_changed)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        self._handle_ports()

        container = self.unit.get_container("gh-jira-bot")
        if container.can_connect():
            # Push an updated layer with the new config
            container.add_layer("gh_jira_bot", self._pebble_layer, combine=True)
            container.replan()

            self.unit.status = ops.ActiveStatus()
        else:
            # We were unable to connect to the Pebble API, so we defer this event
            event.defer()
            self.unit.status = ops.WaitingStatus("Waiting for Pebble API")

    @property
    def app_environment(self):
        """Environment variables extracted from config."""
        env = {
            "APP_ID": self.config["app-id"],
            "PRIVATE_KEY": self.config["private-key"],
            "WEBHOOK_SECRET": self.config["webhook-secret"],
            "JIRA_INSTANCE": self.config["jira-instance"],
            "JIRA_USERNAME": self.config["jira-username"],
            "JIRA_TOKEN": self.config["jira-token"],
        }
        if bot_config := self.config["bot-config"]:
            env["DEFAULT_BOT_CONFIG"] = bot_config
        if bot_name := self.config["bot-name"]:
            env["BOT_NAME"] = bot_name
        # Proxy settings, if applicable.
        http_proxy = os.environ.get("HTTP_PROXY", "")
        https_proxy = os.environ.get("HTTPS_PROXY", "")
        no_proxy = os.environ.get("NO_PROXY", "")
        if http_proxy and https_proxy:
            logger.info(
                "Proxy settings found: HTTP_PROXY=%s, HTTPS_PROXY=%s, NO_PROXY=%s",
                http_proxy, https_proxy, no_proxy
            )
            env["HTTP_PROXY"] = http_proxy
            env["HTTPS_PROXY"] = https_proxy
            env["NO_PROXY"] = no_proxy

        if self.model.get_relation("redis"):
            redis_host = self.redis.relation_data.get("hostname")
            redis_port = self.redis.relation_data.get("port")

            if redis_port and redis_host:
                env["REDIS_HOST"] = redis_host
                env["REDIS_PORT"] = redis_port
        return env

    @property
    def _pebble_layer(self):
        command = " ".join(
            [
                "uvicorn",
                "github_jira_sync_app.main:app",
                "--host=0.0.0.0",
                f"--port={self.config['port']}",
            ]
        )

        return {
            "summary": "gh-jira-bot layer",
            "services": {
                "gh-jira-bot-service": {
                    "override": "replace",
                    "summary": "httpbin",
                    "command": command,
                    "startup": "enabled",
                    "environment": self.app_environment,
                }
            },
        }

    def _handle_ports(self):
        port = int(self.config["port"])
        opened_ports = self.unit.opened_ports()

        if port in [i.port for i in opened_ports]:
            return

        for o_port in opened_ports:
            self.unit.close_port(o_port.protocol, o_port.port)

        self.unit.open_port("tcp", port)


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GitHubJiraBotCharm)
