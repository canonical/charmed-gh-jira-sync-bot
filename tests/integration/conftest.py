import pytest
from pytest_operator.plugin import OpsTest
import functools
import logging
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import os
import asyncio
store = defaultdict(str)

logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def cos_channel():
    return "2/edge"

@pytest.fixture(scope="session")
def config():
    return {key:key for key in ["app-id", "jira-instance", "jira-username", "jira-token", "private-key","webhook-secret"]}

def timed_memoizer(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        fname = func.__qualname__
        logger.info("Started: %s" % fname)
        start_time = datetime.now()
        if fname in store.keys():
            ret = store[fname]
        else:
            logger.info("Return for {} not cached".format(fname))
            ret = await func(*args, **kwargs)
            store[fname] = ret
        logger.info("Finished: {} in: {} seconds".format(fname, datetime.now() - start_time))
        return ret

    return wrapper

@pytest.fixture(scope="module")
def syncbot_charm(ops_test: OpsTest):
    """syncbot charm used for integration testing."""

    @timed_memoizer
    async def _build():
        if charm_file := os.environ.get("CHARM_PATH"):
            return Path(charm_file)
        charm = await ops_test.build_charm(".")
        assert charm
        return str(charm)

    return asyncio.run(_build())
