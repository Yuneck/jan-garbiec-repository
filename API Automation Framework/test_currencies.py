"""
Tests for the /getCurrencies endpoint.

Validates:
- response schema
- timestamp freshness (prod only)
- base currency correctness
- currency code format
- currency price correctness
"""

import re
import time
import pytest
import logging


# ============================================================
# FIXTURE: Fetch currencies once per module
# ============================================================

@pytest.fixture(scope="module")
def currencies_data(api_client):
    logging.info("Fetching /getCurrencies data")
    response = api_client.request("GET", "/getCurrencies", timeout=5)
    response.raise_for_status()
    return response.json()


# ============================================================
# TESTS
# ============================================================

def test_currencies_schema(currencies_data):
    assert "rates" in currencies_data
    assert isinstance(currencies_data["rates"], dict)


def test_currencies_timestamp_is_recent(currencies_data, env_config):
    if env_config["run_prod_assertions"]:
        assert time.time() - currencies_data["timestamp"] <= 12 * 3600, \
            "Currency timestamp is older than 12 hours"
    else:
        logging.info("Timestamp freshness skipped for non-prod environment")


def test_currencies_base_is_usd(currencies_data):
    assert currencies_data["base"] == "USD", \
        f"Expected base currency 'USD', got {currencies_data['base']}"


def test_currency_codes_are_valid(currencies_data):
    for code in currencies_data["rates"].keys():
        assert re.fullmatch(r"[A-Z]{3}", code), \
            f"Invalid currency code format: {code}"


def test_currency_values_are_positive(currencies_data):
    for code, price in currencies_data["rates"].items():
        assert isinstance(price, (int, float)), f"{code} price must be numeric"
        assert price > 0, f"{code} price must be positive, got {price}"
