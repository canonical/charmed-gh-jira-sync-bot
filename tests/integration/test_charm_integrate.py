import pytest
import asyncio
from pytest_operator.plugin import OpsTest
from tenacity import retry, stop_after_attempt, wait_fixed
import logging
import yaml
from helpers import charm_resources, get_prometheus_targets, query_prometheus, get_pebble_plan, curl_syncbot, query_loki

logger = logging.getLogger(__name__)

@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, syncbot_charm: str, cos_channel, config):
    """Build the charm-under-test and deploy it together with related charms."""
    assert ops_test.model is not None  # for pyright
    await asyncio.gather(
        ops_test.model.deploy(syncbot_charm, "syncbot", resources=charm_resources(), trust=True, config=config),
        ops_test.model.deploy("prometheus-k8s", "prometheus", channel=cos_channel, trust=True),
        ops_test.model.deploy("loki-k8s", "loki", channel=cos_channel, trust=True),
    )

    await ops_test.model.wait_for_idle(
        apps=["prometheus", "loki", "syncbot"], status="active"
    )

@pytest.mark.abort_on_fail
async def test_integrate(ops_test: OpsTest):
    assert ops_test.model is not None
    await asyncio.gather(
        ops_test.model.integrate("syncbot", "loki"),
        ops_test.model.integrate("syncbot", "prometheus"),
    )

    await ops_test.model.wait_for_idle(
        apps=[
            "syncbot",
            "prometheus",
            "loki",
        ],
        status="active",
        timeout=300,
    )

@retry(wait=wait_fixed(10), stop=stop_after_attempt(6))
async def test_metrics_endpoint(ops_test: OpsTest):
    """Check that Syncbot appears in the Prometheus scrape targets."""
    assert ops_test.model is not None
    targets = await get_prometheus_targets(ops_test)

    targets = [
        target
        for target in targets["activeTargets"]
        if target["discoveredLabels"]["juju_charm"] == "charmed-github-jira-bot"
    ]
    assert targets

@retry(wait=wait_fixed(10), stop=stop_after_attempt(6))
async def test_metrics_in_prometheus(ops_test: OpsTest):
    """Check that the metrics sent by this charm appear in Prometheus."""
    result = await query_prometheus(ops_test, query='up{juju_charm=~"charmed-github-jira-bot"}')
    assert result

async def test_log_targets(ops_test: OpsTest):
    """Check that the log targets appear in the Pebble plan in the workload container."""

    workload_plan = await get_pebble_plan(ops_test.model_name, "syncbot", 0, "gh-jira-bot")

    assert "log-targets" in yaml.safe_load(workload_plan)

@retry(wait=wait_fixed(10), stop=stop_after_attempt(6))
async def test_logs_in_loki(ops_test: OpsTest):
    """Check that logs from the Syncbot appear in Loki."""

    # First, we will query a non-existing endpoint in the charm. This will trigger a "404 Not Found" log
    await curl_syncbot(ops_test=ops_test)

    # Query Loki and see if the expected logs show up
    result = await query_loki(ops_test=ops_test, query='{juju_application="syncbot"}')

    assert result, "No result returned from Loki (empty list)."

    # Ensure at least one stream exists with values
    assert any("values" in stream and stream["values"] for stream in result), \
        "No log values found in any Loki stream."
    
    # Ensure that the initial log on the startup of the application is sent to Loki. This is a log by FastAPI saying "Application Startup Complete"
    found_startup_log = any("Application startup complete" in log_line for stream in result for _, log_line in stream.get("values", []))
    assert found_startup_log, "Expected log line with '200 OK' not found in Loki logs."

    # Ensure that the logs for the Prometheus scrape job appear. Whenever Prometheus successfully scrapes /metrics, a log is added: "GET /metrics/ HTTP/1.1" 200 OK
    scrape_response_code = any("200 OK" in log_line for stream in result for _, log_line in stream.get("values", []))
    assert scrape_response_code, "Expected log line with '200 OK' not found in Loki logs."

    # Ensure that the log from earlier call to the non-existing endpoint saying "404 Not Found" is found when querying Loki
    not_found_response_code = any("404 Not Found" in log_line for stream in result for _, log_line in stream.get("values", []))
    assert not_found_response_code, "Expected log line with '200 OK' not found in Loki logs."

