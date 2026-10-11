"""Adaptive AR Classifier for ScrapeBuster Phase 2 (PRD M2 / FR-2.1, FR-2.2, FR-2.4, FR-2.6).

Maintains per-route asset ratio EMA baselines, computes per-session trust scores (0-100),
tracks consecutive API anomaly streaks, and enforces fail-offensive cold starts.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import (
    get_ar_alpha,
    get_ar_anomaly_streak,
    get_baseline_min_samples,
    get_mutation_mode,
    get_trust_threshold,
)
from ..edge.session import Session
from .store import (
    get_route_baseline,
    list_route_baselines,
    reset_classifier_store,
    update_route_baseline,
)

logger = logging.getLogger("sb.classifier")


@dataclass
class ClassificationResult:
    decision: str  # "FAST_PATH" | "SANDBOX"
    state: str  # "FAST" | "SANDBOX"
    trust_score: float  # 0.0 - 100.0
    confidence_score: float  # 0.0 - 1.0
    route_class: str  # "browser_cascade", "scraper_recon", "cold_start", "locked_sandbox", "forced_sandbox"
    reasons: list[str] = field(default_factory=list)
    baseline_ar: float = 0.0
    sample_count: int = 0
    is_mature: bool = False
    anomaly_streak: int = 0
    locked: bool = False
    ar_classifier_decision: str = "likely_browser"
    router_decision: str = "FAST_PATH"
    window_ar: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "state": self.state,
            "trust_score": self.trust_score,
            "confidence_score": self.confidence_score,
            "route_class": self.route_class,
            "reasons": list(self.reasons),
            "baseline_ar": self.baseline_ar,
            "sample_count": self.sample_count,
            "is_mature": self.is_mature,
            "anomaly_streak": self.anomaly_streak,
            "locked": self.locked,
            "ar_classifier_decision": self.ar_classifier_decision,
            "router_decision": self.router_decision,
            "window_ar": self.window_ar,
        }


class ARClassifier:
    """Adaptive Asset Ratio Classifier evaluating incoming session cascades against route baselines."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Any]] = {}
        # Operational performance & audit metrics
        self._total_evaluations: int = 0
        self._fast_path_count: int = 0
        self._sandbox_count: int = 0
        self._locked_sandbox_count: int = 0
        self._cold_start_count: int = 0
        self._latencies_ms: list[float] = []
        self._confidence_distribution: dict[str, int] = {
            "high": 0,    # confidence >= 0.8
            "medium": 0,  # 0.5 <= confidence < 0.8
            "low": 0,     # 0.1 <= confidence < 0.5
            "zero": 0,    # confidence < 0.1
        }

    def _get_or_load_baseline(self, route: str) -> dict[str, Any]:
        """Fetch route baseline from memory cache or load from durable store."""
        with self._lock:
            if route not in self._cache:
                stored = get_route_baseline(route)
                if stored is not None:
                    self._cache[route] = stored
                else:
                    self._cache[route] = {
                        "route": route,
                        "ar_ema": 0.0,
                        "sample_count": 0,
                        "updated_at": "",
                    }
            return dict(self._cache[route])

    def record_sample(self, route: str, asset_ratio: float) -> dict[str, Any]:
        """Record live asset ratio sample for route and update EMA baseline (PRD FR-2.1).

        AR_baseline(route) = alpha * AR_current + (1 - alpha) * AR_historical.
        """
        alpha = get_ar_alpha()
        with self._lock:
            updated = update_route_baseline(route, asset_ratio, alpha=alpha)
            self._cache[route] = updated
            return updated

    def get_baseline(self, route: str) -> dict[str, Any]:
        """Return current baseline info for route including maturity status."""
        b = self._get_or_load_baseline(route)
        min_samples = get_baseline_min_samples()
        sample_count = int(b.get("sample_count", 0))
        return {
            "route": route,
            "ar_ema": float(b.get("ar_ema", 0.0)),
            "sample_count": sample_count,
            "updated_at": str(b.get("updated_at", "")),
            "is_mature": sample_count >= min_samples,
        }

    def classify_session(self, session: Session, route: str) -> ClassificationResult:
        """Classify session for route based on asset ratio comparison, EMA baseline, and streak history."""
        t_start = time.perf_counter()
        with self._lock:
            self._total_evaluations += 1

            mutation_mode = get_mutation_mode()
            if mutation_mode == "always":
                self._sandbox_count += 1
                self._confidence_distribution["high"] += 1
                session.ar_classifier_decision = "likely_scraper"
                session.router_decision = "SANDBOX"
                res = ClassificationResult(
                    decision="SANDBOX",
                    state="SANDBOX",
                    trust_score=0.0,
                    confidence_score=1.0,
                    route_class="forced_sandbox",
                    reasons=["MUTATION_MODE_ALWAYS"],
                    anomaly_streak=getattr(session, "ar_anomaly_streak", 0),
                    locked=bool(getattr(session, "locked_sandbox", False)),
                    ar_classifier_decision="likely_scraper",
                    router_decision="SANDBOX",
                )
                self._record_latency(t_start)
                return res

            anomaly_streak_thresh = get_ar_anomaly_streak()
            min_samples = get_baseline_min_samples()
            trust_thresh = get_trust_threshold()

            current_streak = getattr(session, "ar_anomaly_streak", 0)
            is_locked = bool(getattr(session, "locked_sandbox", False)) or (current_streak >= anomaly_streak_thresh)

            # FR-2.4 Sticky sandbox lock once anomaly streak triggers
            if is_locked:
                session.locked_sandbox = True
                session.state = "SANDBOX"
                session.decision = "SANDBOX"
                session.trust_score = 0.0
                session.ar_classifier_decision = "likely_scraper"
                session.router_decision = "SANDBOX"
                self._sandbox_count += 1
                self._locked_sandbox_count += 1
                self._confidence_distribution["high"] += 1
                res = ClassificationResult(
                    decision="SANDBOX",
                    state="SANDBOX",
                    trust_score=0.0,
                    confidence_score=1.0,
                    route_class="locked_sandbox",
                    reasons=["SANDBOX_LOCKED_ANOMALY_STREAK"],
                    anomaly_streak=current_streak,
                    locked=True,
                    ar_classifier_decision="likely_scraper",
                    router_decision="SANDBOX",
                )
                self._record_latency(t_start)
                return res

            baseline = self.get_baseline(route)
            sample_count = baseline["sample_count"]
            baseline_ar = baseline["ar_ema"]
            is_mature = baseline["is_mature"]

            # FR-2.6 Cold start: with no baseline, ALL sessions receive watermarking until baseline matures
            if not is_mature:
                session.state = "SANDBOX"
                session.decision = "SANDBOX"
                session.trust_score = 0.0
                session_ar = getattr(session, "asset_ratio", 0.0)
                ar_heuristic = "likely_browser" if session_ar >= 3.0 else ("likely_scraper" if session_ar < 1.0 else "ambiguous")
                session.ar_classifier_decision = ar_heuristic
                session.router_decision = "SANDBOX"
                self._sandbox_count += 1
                self._cold_start_count += 1
                self._confidence_distribution["zero"] += 1
                res = ClassificationResult(
                    decision="SANDBOX",
                    state="SANDBOX",
                    trust_score=0.0,
                    confidence_score=0.0,
                    route_class="cold_start",
                    reasons=["COLD_START_IMMATURE_BASELINE"],
                    baseline_ar=baseline_ar,
                    sample_count=sample_count,
                    is_mature=False,
                    anomaly_streak=current_streak,
                    locked=False,
                    ar_classifier_decision=ar_heuristic,
                    router_decision="SANDBOX",
                )
                self._record_latency(t_start)
                return res

            # Sliding window AR over last 50 requests & overall session AR
            session_ar = getattr(session, "asset_ratio", 0.0)
            window_ar = getattr(session, "window_asset_ratio", session_ar)
            window_len = len(getattr(session, "request_window", []))
            effective_ar = window_ar if window_len >= 5 else session_ar

            # 1. Heuristic Decision Tree:
            # AR >= 3.0 (likely browser), AR < 1.0 (likely scraper), 1.0-3.0 (ambiguous)
            if effective_ar >= 3.0:
                ar_heuristic = "likely_browser"
            elif effective_ar < 1.0:
                ar_heuristic = "likely_scraper"
            else:
                ar_heuristic = "ambiguous"

            # 2. Compute confidence score based on consistency and request pattern stability
            sample_stability = min(1.0, max(0.1, sample_count / (min_samples * 2)))
            window_stability = min(1.0, max(0.1, window_len / 20.0))
            if effective_ar > 0.0:
                drift = abs(session_ar - window_ar) / max(0.1, max(session_ar, window_ar))
                pattern_consistency = max(0.0, 1.0 - drift)
            else:
                pattern_consistency = 1.0
            streak_stability = max(0.0, 1.0 - (current_streak / max(1, anomaly_streak_thresh)))
            raw_confidence = (0.4 * sample_stability + 0.3 * window_stability + 0.3 * pattern_consistency) * streak_stability
            confidence_score = round(max(0.05, min(1.0, raw_confidence)), 2)

            # FR-2.2 Per-session Trust Score (0-100) comparing live asset cascade against route baseline
            if baseline_ar > 0.0:
                ratio = effective_ar / baseline_ar
                base_score = min(100.0, max(0.0, ratio * 100.0))
                if current_streak > 0:
                    penalty = (current_streak / max(1, anomaly_streak_thresh)) * 50.0
                    base_score = max(0.0, base_score - penalty)
            else:
                if effective_ar > 0.0:
                    base_score = 100.0
                else:
                    base_score = max(0.0, 100.0 - (current_streak / max(1, anomaly_streak_thresh)) * 100.0)

            trust_score = round(base_score, 2)
            session.trust_score = trust_score

            # Confidence bucket
            if confidence_score >= 0.8:
                self._confidence_distribution["high"] += 1
            elif confidence_score >= 0.5:
                self._confidence_distribution["medium"] += 1
            elif confidence_score >= 0.1:
                self._confidence_distribution["low"] += 1
            else:
                self._confidence_distribution["zero"] += 1

            # Dynamic Router Integration:
            # - Route high-confidence browser: FAST_PATH (bypass sandboxing, direct origin forward)
            # - Route high-confidence scraper: SANDBOX (full canary injection, offense hooks)
            # - Route ambiguous (1.0-3.0 or moderate trust): ADAPTIVE (graduated canary injection)
            if ar_heuristic == "likely_browser" and trust_score >= trust_thresh:
                decision = "FAST_PATH"
                router_decision = "FAST_PATH"
                state = "FAST"
                route_class = "browser_cascade"
                reasons = ["HIGH_TRUST_ASSET_CASCADE", "LIKELY_BROWSER"]
                self._fast_path_count += 1
            elif ar_heuristic == "likely_scraper" or trust_score < 40.0:
                decision = "SANDBOX"
                router_decision = "SANDBOX"
                state = "SANDBOX"
                route_class = "scraper_recon"
                reasons = ["LOW_TRUST_ASSET_DIVERGENCE", "LIKELY_SCRAPER"]
                self._sandbox_count += 1
            else:
                decision = "SANDBOX"
                router_decision = "ADAPTIVE"
                state = "ADAPTIVE"
                route_class = "ambiguous"
                reasons = ["AMBIGUOUS_ASSET_RATIO_ADAPTIVE"]
                self._sandbox_count += 1

            session.state = state
            session.decision = decision
            session.ar_classifier_decision = ar_heuristic
            session.confidence_score = confidence_score
            session.router_decision = router_decision

            res = ClassificationResult(
                decision=decision,
                state=state,
                trust_score=trust_score,
                confidence_score=confidence_score,
                route_class=route_class,
                reasons=reasons,
                baseline_ar=baseline_ar,
                sample_count=sample_count,
                is_mature=True,
                anomaly_streak=current_streak,
                locked=False,
                ar_classifier_decision=ar_heuristic,
                router_decision=router_decision,
                window_ar=window_ar,
            )
            self._record_latency(t_start)
            return res

    def _record_latency(self, t_start: float) -> None:
        duration_ms = (time.perf_counter() - t_start) * 1000.0
        self._latencies_ms.append(duration_ms)
        if len(self._latencies_ms) > 1000:
            self._latencies_ms = self._latencies_ms[-1000:]

    def get_latency_stats(self) -> dict[str, float]:
        if not self._latencies_ms:
            return {"p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "mean_ms": 0.0}
        samples = sorted(self._latencies_ms)
        n = len(samples)

        def pct(p: float) -> float:
            idx = int(round((n - 1) * p))
            return samples[min(max(idx, 0), n - 1)]

        return {
            "p50_ms": round(pct(0.50), 4),
            "p95_ms": round(pct(0.95), 4),
            "p99_ms": round(pct(0.99), 4),
            "mean_ms": round(sum(samples) / n, 4),
        }

    def get_status(self) -> dict[str, Any]:
        """Produce full status snapshot for /api/v1/classifier/status endpoint."""
        with self._lock:
            all_baselines = list_route_baselines()
            min_samples = get_baseline_min_samples()
            routes_info = []
            matured_count = 0
            for b in all_baselines:
                is_mature = b["sample_count"] >= min_samples
                if is_mature:
                    matured_count += 1
                routes_info.append({
                    "route": b["route"],
                    "ar_ema": b["ar_ema"],
                    "sample_count": b["sample_count"],
                    "updated_at": b["updated_at"],
                    "is_mature": is_mature,
                })

            lat_stats = self.get_latency_stats()
            return {
                "status": "ok",
                "mutation_mode": get_mutation_mode(),
                "alpha": get_ar_alpha(),
                "trust_threshold": get_trust_threshold(),
                "anomaly_streak_threshold": get_ar_anomaly_streak(),
                "baseline_min_samples": min_samples,
                "total_routes": len(all_baselines),
                "matured_routes": matured_count,
                "metrics": {
                    "total_evaluations": self._total_evaluations,
                    "fast_path_count": self._fast_path_count,
                    "sandbox_count": self._sandbox_count,
                    "locked_sandbox_count": self._locked_sandbox_count,
                    "cold_start_count": self._cold_start_count,
                    "latency_p50_ms": lat_stats["p50_ms"],
                    "latency_p95_ms": lat_stats["p95_ms"],
                    "confidence_distribution": dict(self._confidence_distribution),
                },
                "routes": routes_info,
            }

    def reset(self) -> None:
        """Reset in-memory state and clear durable baselines."""
        with self._lock:
            self._cache.clear()
            self._total_evaluations = 0
            self._fast_path_count = 0
            self._sandbox_count = 0
            self._locked_sandbox_count = 0
            self._cold_start_count = 0
            self._latencies_ms.clear()
            for k in self._confidence_distribution:
                self._confidence_distribution[k] = 0
            reset_classifier_store()


classifier = ARClassifier()
