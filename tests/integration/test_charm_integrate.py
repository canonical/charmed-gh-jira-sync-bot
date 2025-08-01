import pytest
import asyncio
from pytest_operator.plugin import OpsTest
from tenacity import retry, stop_after_attempt, wait_fixed

from helpers import charm_resources

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
