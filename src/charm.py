import logging

import ops

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)


class GitHubJiraBotCharm(ops.CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.gh_jira_bot_pebble_ready, self._on_httpbin_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_httpbin_pebble_ready(self, event: ops.PebbleReadyEvent):
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Add initial Pebble config layer using the Pebble API
        container.add_layer("httpbin", self._pebble_layer, combine=True)
        # Make Pebble reevaluate its plan, ensuring any services are started if enabled.
        container.replan()
        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        log_level = self.model.config["log-level"].lower()

        container = self.unit.get_container("httpbin")
        # Verify that we can connect to the Pebble API in the workload container
        if container.can_connect():
            # Push an updated layer with the new config
            container.add_layer("httpbin", self._pebble_layer, combine=True)
            container.replan()

            logger.debug("Log level for gunicorn changed to '%s'", log_level)
            self.unit.status = ops.ActiveStatus()
        else:
            # We were unable to connect to the Pebble API, so we defer this event
            event.defer()
            self.unit.status = ops.WaitingStatus("waiting for Pebble API")


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
                    "environment": {
                        "GUNICORN_CMD_ARGS": f"--log-level {self.model.config['log-level']}"
                    },
                }
            },
        }


if __name__ == "__main__":  # pragma: nocover
    ops.main(GitHubJiraBotCharm)
