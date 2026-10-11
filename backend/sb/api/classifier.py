"""Classifier API endpoints for ScrapeBuster Phase 2 (PRD M2 / FR-2.1 - FR-2.6).

Exposes classifier performance metrics, maturity counts, baseline EMA states, and configuration.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..classifier.classifier import classifier
from ..contracts import ClassifierStatus

router = APIRouter()


@router.get("/classifier/status", response_model=ClassifierStatus)
async def get_classifier_status() -> ClassifierStatus:
    """Return active classifier status, route baseline EMA metrics, and evaluation counters."""
    data = classifier.get_status()
    return ClassifierStatus.model_validate(data)
