import pytest
import asyncio
from pytest_operator.plugin import OpsTest
from tenacity import retry, stop_after_attempt, wait_fixed
import logging
from helpers import charm_resources, get_prometheus_targets, query_prometheus
logger = logging.getLogger(__name__)
#@pytest.mark.setup
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
    """Check that Syncbot appears in the Prometheus Scrape Targets."""
    assert ops_test.model is not None
    targets = await get_prometheus_targets(ops_test)
    logger.info("Targets %s", targets)
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