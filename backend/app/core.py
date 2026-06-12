"""Model registry + canary promotion + drift gate (PSI) — the control plane of an MLOps platform."""
import math, time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ModelVersion(BaseModel):
    name: str
    version: str
    metrics: dict[str, float]          # e.g. {"auc": 0.91, "latency_ms": 42}
    baseline_distribution: list[float] = []   # reference feature histogram (10 bins)

REGISTRY: dict[str, dict] = {}        # name -> {versions: {v: data}, stages: {...}}

@router.post("/models")
def register(mv: ModelVersion):
    entry = REGISTRY.setdefault(mv.name, {"versions": {}, "stages": {"production": None, "staging": None}})
    entry["versions"][mv.version] = {**mv.model_dump(), "registered_at": time.time()}
    entry["stages"]["staging"] = mv.version
    return {"registered": f"{mv.name}:{mv.version}", "stage": "staging"}

@router.get("/models")
def list_models():
    return {n: {"stages": e["stages"], "versions": list(e["versions"])} for n, e in REGISTRY.items()}

@router.post("/models/{name}/promote")
def promote(name: str, min_auc: float = 0.85):
    e = REGISTRY.get(name)
    if not e or not e["stages"]["staging"]:
        raise HTTPException(404, "no staging candidate")
    v = e["stages"]["staging"]
    auc = e["versions"][v]["metrics"].get("auc", 0)
    if auc < min_auc:
        return {"promoted": False, "reason": f"auc {auc} < gate {min_auc}"}
    e["stages"]["production"], e["stages"]["staging"] = v, None
    return {"promoted": True, "production": v}

class DriftCheck(BaseModel):
    name: str
    live_distribution: list[float]     # current feature histogram, same bins

@router.post("/drift")
def drift(d: DriftCheck):
    e = REGISTRY.get(d.name)
    if not e or not e["stages"]["production"]:
        raise HTTPException(404, "no production model")
    base = e["versions"][e["stages"]["production"]].get("baseline_distribution") or []
    if len(base) != len(d.live_distribution) or not base:
        raise HTTPException(400, "distributions must share bin count")
    def norm(xs):
        s = sum(xs) or 1.0
        return [max(x / s, 1e-6) for x in xs]
    b, l = norm(base), norm(d.live_distribution)
    psi = sum((li - bi) * math.log(li / bi) for bi, li in zip(b, l))
    status = "stable" if psi < 0.1 else "moderate_drift" if psi < 0.25 else "severe_drift"
    return {"psi": round(psi, 4), "status": status,
            "action": "retrain + shadow deploy" if psi >= 0.25 else "monitor"}
