import yaml
from typing import Dict
from pytest_operator.plugin import OpsTest
from typing import Any
import requests
import logging
import subprocess
from tenacity import retry, stop_after_attempt, wait_fixed
import time

logger = logging.getLogger(__name__)

def charm_resources(metadata_file="metadata.yaml") -> Dict[str, str]:
    with open(metadata_file, "r") as file:
        metadata = yaml.safe_load(file)
    resources = {}
    for res, data in metadata["resources"].items():
        resources[res] = data["upstream-source"]
    return resources

async def get_leader_unit_number(ops_test: OpsTest, app_name: str) -> int:
    """Get the unit number of the leader of an application.

    Raises an exception if no leader is found.
    """
    assert ops_test.model
    status = await ops_test.model.get_status()
    app = status["applications"][app_name]
    if app is None:
        raise ValueError(f"no app exists with name {app_name}")

    for name, unit in app["units"].items():
        if unit["leader"]:
            return int(name.split("/")[1])

    raise ValueError(f"no leader found for app {app_name}")


async def get_unit_address(ops_test: OpsTest, app_name: str, unit_no: int) -> str:
    assert ops_test.model is not None
    status = await ops_test.model.get_status()
    app = status["applications"][app_name]
    if app is None:
        assert False, f"no app exists with name {app_name}"
    unit = app["units"].get(f"{app_name}/{unit_no}")
    if unit is None:
        assert False, f"no unit exists in app {app_name} with index {unit_no}"
    return unit["address"]

async def get_prometheus_targets(
    ops_test: OpsTest, prometheus_app: str = "prometheus"
) -> Dict[str, Any]:
    """Get the Scrape Targets from Prometheus using the HTTP API.

    HTTP API Response format:
        {"status": "success", "data": {"activeTargets": [{"discoveredLabels": {..., "juju_charm": <charm>, ...}}]}}
    """
    assert ops_test.model is not None
    leader_unit_number = await get_leader_unit_number(ops_test, prometheus_app)
    prometheus_url = await get_unit_address(ops_test, prometheus_app, leader_unit_number)
    response = requests.get(f"http://{prometheus_url}:9090/api/v1/targets")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    return response.json()["data"]

async def query_prometheus(
    ops_test: OpsTest, query: str, app: str = "prometheus"
) -> Dict[str, Any]:
    leader_unit_number = await get_leader_unit_number(ops_test, app)
    prometheus_url = await get_unit_address(ops_test, app, leader_unit_number)

    response = requests.get(
        f"http://{prometheus_url}:9090/api/v1/query",
        params={"query": query},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"  # the query was successful
    return response.json()["data"]["result"]

async def get_pebble_plan(
    model_name: str, app_name: str, unit_num: int, container_name: str
) -> str:
    cmd = [
        "juju",
        "ssh",
        "--model",
        model_name,
        "--container",
        container_name,
        f"{app_name}/{unit_num}",
        "./charm/bin/pebble",
        "plan",
    ]
    try:
        res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logger.error(e.stdout.decode())
        raise e
    return res.stdout.decode("utf-8")

async def curl_syncbot(
    ops_test: OpsTest, app: str = "syncbot"
) -> Dict[str, Any]:
    leader_unit_number = await get_leader_unit_number(ops_test, app)
    syncbot_url = await get_unit_address(ops_test, app, leader_unit_number)

    response = requests.get(
        f"http://{syncbot_url}:3000/non-existing-endpoint",
    )

    assert response.status_code == 404

async def query_loki(
    ops_test: OpsTest, query: str, app: str = "loki"
) -> Dict[str, Any]:
    leader_unit_number = await get_leader_unit_number(ops_test, app)
    loki_url = await get_unit_address(ops_test, app, leader_unit_number)

    end_ns = int(time.time() * 1e9)
    start_ns = int((time.time() - 3600) * 1e9)

    params = {
        "query": query,
        "start": str(start_ns),
        "end": str(end_ns),
        "limit": "1000",
        "direction": "forward"
    }

    response = requests.get(
        f"http://{loki_url}:3100/loki/api/v1/query_range",
        params=params,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    return response.json()["data"]["result"]
