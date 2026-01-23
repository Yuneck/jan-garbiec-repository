"""
Tests for the /timePoints endpoint.

Validates:
- response schema
- timestamp ordering and uniqueness
- timestamp freshness
- max allowed gap between points
- metal price correctness
"""

import time
import pytest
import logging

from conftest import PriceHistoryResponse
from utils.commonMethods import CommonMethods as CM


# ============================================================
# FIXTURE: Fetch timepoints once per module
# ============================================================

@pytest.fixture(scope="module")
def timepoints_data(api_client):
    logging.info("Fetching /timePoints data")
    response = api_client.request("GET", "/timePoints", timeout=5)
    response.raise_for_status()
    return PriceHistoryResponse(**response.json())


# ============================================================
# TESTS
# ============================================================

def test_timepoints_schema(timepoints_data):
    assert isinstance(timepoints_data, PriceHistoryResponse)


def test_timepoints_are_sorted(timepoints_data):
    timestamps = [tp.timestamp for tp in timepoints_data.allTimePoints]
    assert timestamps == sorted(timestamps), "Timestamps must be sorted ascending"


def test_timepoints_are_unique(timepoints_data):
    timestamps = [tp.timestamp for tp in timepoints_data.allTimePoints]
    assert len(timestamps) == len(set(timestamps)), "Duplicate timestamps detected"


def test_timepoints_are_recent(timepoints_data):
    last_timestamp = timepoints_data.allTimePoints[-1].timestamp
    assert time.time() - last_timestamp <=12 * 3600, "Last timestamp is older than 12 hours"


def test_timepoints_gap_is_valid(timepoints_data):
    timestamps = [tp.timestamp for tp in timepoints_data.allTimePoints]
    for prev, curr in zip(timestamps, timestamps[1:]):
        assert curr - prev <= 120 * 3600, "Gap between timestamps exceeds 120 hours"


def test_timepoints_prices_are_positive(timepoints_data):
    for tp in timepoints_data.allTimePoints:
        for metal in CM.metalTypes:
            value = float(getattr(tp, metal))
            assert value > 0, f"{metal} price must be positive, got {value}"
