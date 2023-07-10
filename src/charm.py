"""Charm code for https://github.com/canonical/gh-jira-sync-bot."""
import logging

import ops

logger = logging.getLogger(__name__)


class GitHubJiraBotCharm(ops.CharmBase):
    """Charm class for https://github.com/canonical/gh-jira-sync-bot."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.gh_jira_bot_pebble_ready, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

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
    ops.main(GitHubJiraBotCharm)
