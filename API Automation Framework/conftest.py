"""
conftest.py
Shared fixtures, environment setup, HTTP session configuration,
and reusable utilities for the API test framework.

Automatically discovered by pytest.
"""

import logging
import time
from functools import wraps
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright._impl._errors import TimeoutError
from pydantic import BaseModel, ValidationError

from runtime_config import ENV_CONFIG


# ============================================================
# ENVIRONMENT SETUP
# ============================================================

def pytest_addoption(parser):
    """
    Adds a custom CLI option:
        --env=<environment>
    Allows running tests against different environments (dev/prod/etc.).
    """
    parser.addoption(
        "--env",
        action="store",
        default="dev",
        help="Environment to run tests against: dev/prod"
    )


@pytest.fixture(scope="session")
def env_config(request) -> Dict[str, Any]:
    """
    Loads environment-specific configuration from ENV_CONFIG.
    Ensures the selected environment exists.
    """
    env = request.config.getoption("--env")

    if env not in ENV_CONFIG:
        raise ValueError(f"Unknown environment: {env}")

    cfg = ENV_CONFIG[env]
    cfg["env_name"] = env
    return cfg


@pytest.fixture(scope="session", autouse=True)
def env_print(env_config: dict):
    """
    Logs the selected environment at the start of the test session.
    """
    logging.info(f"Running on environment: {env_config['env_name']}\n")

# ============================================================
# LIGHTWEIGHT API CLIENT WRAPPER (Pydantic v1 compatible)
# ============================================================

class APIClient:
    """
    Simple API client wrapper around requests.Session.
    Adds:
    - base_url handling
    - automatic JSON parsing
    - optional schema validation
    """

    def __init__(self, session):
        self.session = session

    def request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.session.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        return response

    def get_json(self, method: str, endpoint: str, model=None, **kwargs):
        response = self.request(method, endpoint, **kwargs)
        response.raise_for_status()

        data = response.json()

        if model:
            return model(**data) 

        return data


@pytest.fixture(scope="session")
def api_client(api_session):
    """
    Provides a typed API client wrapper for cleaner test code.
    """
    return APIClient(api_session)

# ============================================================
# HTTP SESSION WITH RETRY LOGIC
# ============================================================

def create_retry_session():
    """
    Creates a requests.Session() with retry strategy applied.
    Retries transient errors such as 429, 500, 502, 503, 504.
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # Retry delays: 1s, 2s, 4s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


@pytest.fixture(scope="session")
def api_session(env_config: dict):
    """
    Provides a preconfigured HTTP session with retry logic.
    Adds base_url to simplify API calls inside tests.
    """
    session = create_retry_session()
    session.base_url = env_config["api_url"]

    yield session
    session.close()


# ============================================================
# RESPONSE SCHEMA VALIDATION (Pydantic Models)
# ============================================================

class TimePoint(BaseModel):
    """
    Represents a single time point in the price history response.
    """
    id: UUID
    timestamp: int
    date: datetime
    goldPrice: str
    silverPrice: str
    platinumPrice: str
    palladiumPrice: str


class PriceHistoryResponse(BaseModel):
    """
    Represents the full response structure for price history API.
    """
    total: int
    allTimePoints: List[TimePoint]


# ============================================================
# DECORATORS / WRAPPERS
# ============================================================

class Wrappers:
    """
    Collection of reusable decorators for logging and timing.
    """

    @staticmethod
    def error_logger(func):
        """
        Logs errors raised by the wrapped function.
        Useful for debugging flaky tests or API failures.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
            except (TimeoutError, ValueError, KeyError, ValidationError) as e:
                logging.error(f"{type(e).__name__} in {func.__name__}: {e}")
            else:
                logging.info(f"{func.__name__} executed without errors")
                return result

        return wrapper

    @staticmethod
    def time_counter(func):
        """
        Measures execution time of the wrapped function.
        Helps identify slow API endpoints or heavy operations.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            logging.info(f"{func.__name__} executed in {duration:.5f} seconds")
            return result

        return wrapper
