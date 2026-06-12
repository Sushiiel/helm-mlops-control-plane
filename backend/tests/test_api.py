"""Smoke tests generated from the blueprint contract."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SMOKE = [
  {
    "method": "post",
    "path": "/api/models",
    "json": {
      "name": "churn",
      "version": "1.2.0",
      "metrics": {
        "auc": 0.91
      },
      "baseline_distribution": [
        5,
        10,
        20,
        25,
        15,
        10,
        7,
        4,
        3,
        1
      ]
    }
  },
  {
    "method": "post",
    "path": "/api/models/churn/promote"
  },
  {
    "method": "post",
    "path": "/api/drift",
    "json": {
      "name": "churn",
      "live_distribution": [
        2,
        6,
        14,
        22,
        20,
        14,
        10,
        6,
        4,
        2
      ]
    }
  }
]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_smoke_endpoints():
    for case in SMOKE:
        fn = getattr(client, case["method"])
        kwargs = {"json": case["json"]} if "json" in case else {}
        r = fn(case["path"], **kwargs)
        assert r.status_code < 500, f"{case['path']} -> {r.status_code}: {r.text}"
