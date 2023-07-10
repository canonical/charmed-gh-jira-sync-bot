import logging

import ops

logger = logging.getLogger(__name__)


class GitHubJiraBotCharm(ops.CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.gh_jira_bot_pebble_ready, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        port = self.config["port"]

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
        env = {
            "APP_ID": self.config["app-id"],
            "PRIVATE_KEY": self.config["private-key"],
            "WEBHOOK_SECRET": self.config["webhook-secret"],
            "JIRA_INSTANCE": self.config["jira-instance"],
            "JIRA_USERNAME": self.config["jira-username"],
            "JIRA_TOKEN": self.config["jira-token"]
        }
        if bot_config := self.config["bot-config"]:
            env["DEFAULT_BOT_CONFIG"] = bot_config
        if bot_name := self.config["bot-name"]:
            env["BOT_NAME"] = bot_name

        return env

    @property
    def _pebble_layer(self):

        return {
            "summary": "httpbin layer",
            "description": "pebble config layer for httpbin",
            "services": {
                "httpbin": {
                    "override": "replace",
                    "summary": "httpbin",
                    "command": "gunicorn -b 0.0.0.0:80 httpbin:app -k gevent",
                    "startup": "enabled",
                    "environment": self.app_environment,
                }
            },
        }


if __name__ == "__main__":  # pragma: nocover
    ops.main(GitHubJiraBotCharm)
