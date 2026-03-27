from __future__ import annotations

from dataclasses import asdict

from opx.config import ScoringConfig
from opx.models import FactorContribution, FeatureSet, SignalResult


def score_signal(ticker: str, signal_time, features: FeatureSet, config: ScoringConfig) -> SignalResult:
    contributions: list[FactorContribution] = []

    def add(name: str, score: int, rationale: str) -> None:
        contributions.append(FactorContribution(name=name, score=score, rationale=rationale))

    if features.price_vs_vwap_pct >= config.vwap_band_pct:
        add("price_vs_vwap_pct", 2, "trading above VWAP with room")
    elif features.price_vs_vwap_pct <= -config.vwap_band_pct:
        add("price_vs_vwap_pct", -2, "trading below VWAP")

    if features.first_15m_return >= config.strong_move_pct:
        add("first_15m_return", 2, "early move is strongly positive")
    elif features.first_15m_return <= -config.strong_move_pct:
        add("first_15m_return", -2, "early move is strongly negative")

    if features.first_15m_return_minus_qqq >= config.relative_strength_pct:
        add("first_15m_return_minus_qqq", 2, "materially outperforming QQQ")
    elif features.first_15m_return_minus_qqq <= -config.relative_strength_pct:
        add("first_15m_return_minus_qqq", -2, "materially underperforming QQQ")

    if features.opening_volume_multiple >= config.volume_multiple_threshold:
        move_score = 1 if features.first_15m_return > 0 else -1 if features.first_15m_return < 0 else 0
        if move_score:
            add("opening_volume_multiple", move_score, "opening participation confirms direction")

    if features.gap_hold_or_fade == "holding":
        add("gap_hold_or_fade", 2 if features.gap_pct > 0 else -2 if features.gap_pct < 0 else 0, "gap is holding")
    elif features.gap_hold_or_fade == "fading":
        add("gap_hold_or_fade", -2 if features.gap_pct > 0 else 2 if features.gap_pct < 0 else 0, "gap is fading")

    if features.opening_range_break_status == "break_above":
        add("opening_range_break_status", 1, "price broke above opening range")
    elif features.opening_range_break_status == "break_below":
        add("opening_range_break_status", -1, "price broke below opening range")

    raw_score = sum(item.score for item in contributions)
    bias = _map_bias(raw_score, config)
    regime = _map_regime(features, bias)
    confidence = _map_confidence(raw_score, contributions)
    posture = _map_posture(bias, regime)

    return SignalResult(
        ticker=ticker,
        signal_time=signal_time,
        bias=bias,
        confidence=confidence,
        regime=regime,
        option_posture=posture,
        raw_score=raw_score,
        factors=features.as_dict(),
        factor_summary=[asdict(item) for item in contributions],
    )


def _map_bias(raw_score: int, config: ScoringConfig) -> str:
    if raw_score >= config.bullish_threshold:
        return "bullish"
    if raw_score <= config.bearish_threshold:
        return "bearish"
    return "neutral"


def _map_confidence(raw_score: int, contributions: list[FactorContribution]) -> int:
    if not contributions:
        return 0
    same_direction = sum(1 for item in contributions if item.score > 0) if raw_score > 0 else sum(1 for item in contributions if item.score < 0)
    agreement = same_direction / len(contributions)
    magnitude = min(abs(raw_score) / 9.0, 1.0)
    return int(round((magnitude * 0.7 + agreement * 0.3) * 100))


def _map_regime(features: FeatureSet, bias: str) -> str:
    if bias == "neutral":
        return "choppy"
    if features.gap_hold_or_fade == "fading" and abs(features.price_vs_vwap_pct) < 0.1:
        return "mean_reversion"
    if abs(features.first_15m_return) >= 0.5 and abs(features.price_vs_vwap_pct) >= 0.1:
        return "trend_continuation"
    return "choppy"


def _map_posture(bias: str, regime: str) -> str:
    if bias == "bullish" and regime == "trend_continuation":
        return "bullish_premium_sale_favored"
    if bias == "bearish" and regime == "trend_continuation":
        return "defensive_bearish_premium_posture"
    if regime == "mean_reversion":
        return "fade_setup_only_if_risk_defined"
    return "patience_or_theta_oriented"
