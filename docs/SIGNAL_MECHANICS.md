# Signal Mechanics

This document describes the current engine behavior that turns early-session market data into a directional signal.

## High-Level Flow

The signal is produced in three stages:

1. collect normalized intraday and daily bars for each ticker and benchmark
2. compute a fixed set of post-open features at the configured signal time
3. score those features with a deterministic rule engine that maps to bias, regime, confidence, and option posture

The current implementation is intentionally simple and explainable. It does not use a trained model. It encodes a working hypothesis: once the most unstable part of the open begins to clear, the combination of early price position, opening strength or weakness, relative performance, and participation can reveal a directional bias that remains useful through the rest of the session.

## Signal Snapshot

The engine evaluates each ticker from a single morning snapshot instead of continuously updating intraday.

Current default assumptions:

- signal time: `09:45 ET`
- bar interval: `5m`
- minimum intraday bars before scoring: `3`
- minimum completed daily history before scoring: `6` sessions

That means the default signal is based on the first three 5-minute bars of the session, which together define the first 15-minute opening structure.

## Inputs To The Signal

The engine combines three kinds of context:

- opening behavior for the ticker itself
- recent historical context for that ticker
- relative context versus `QQQ` and `SPY`

The current feature set includes:

- opening gap versus prior close
- first 5-minute, 10-minute, and 15-minute returns
- first 15-minute range and close versus open
- price versus session VWAP at the signal timestamp
- opening volume versus the ticker's historical first-15-minute average
- whether price has broken above or below the first-15-minute opening range
- whether the opening gap is holding or fading
- opening candle body quality
- current location within the session's high-low range
- previous-day, three-day, and five-day context
- ATR-normalized recent move
- first-15-minute relative performance versus `QQQ` and `SPY`
- gap behavior relative to `QQQ` and `SPY`

Not every feature directly contributes to the score yet. Some are persisted because they are useful for later review, validation, and future rule expansion.

## Current Scoring Rules

The rule engine adds signed contributions from a small set of explainable checks. The final `raw_score` is the sum of those contributions.

### 1. Price Versus VWAP

- if `price_vs_vwap_pct >= 0.15`, add `+2`
- if `price_vs_vwap_pct <= -0.15`, add `-2`

Interpretation: trading meaningfully above VWAP supports bullish control; trading below VWAP supports bearish control.

### 2. First 15-Minute Move Strength

- if `first_15m_return >= 0.75`, add `+2`
- if `first_15m_return <= -0.75`, add `-2`

Interpretation: a strong early directional move is treated as meaningful evidence rather than noise.

### 3. Relative Strength Versus QQQ

- if `first_15m_return_minus_qqq >= 0.30`, add `+2`
- if `first_15m_return_minus_qqq <= -0.30`, add `-2`

Interpretation: the ticker is rewarded for outperforming the primary growth benchmark and penalized for underperforming it.

### 4. Opening Participation

- if `opening_volume_multiple >= 1.5`, add `+1` when the first 15-minute return is positive
- if `opening_volume_multiple >= 1.5`, add `-1` when the first 15-minute return is negative

Interpretation: heavy opening participation confirms the move only when the move already has a direction.

### 5. Gap Hold Or Fade

- if the gap is `holding`, add `+2` for a positive gap and `-2` for a negative gap
- if the gap is `fading`, add `-2` for a positive gap and `+2` for a negative gap

Interpretation: held gaps support continuation; fading gaps support reversal pressure.

### 6. Opening Range Break

- if price is above the first-15-minute high, add `+1`
- if price is below the first-15-minute low, add `-1`

Interpretation: a break outside the opening range is treated as an additional directional confirmation.

## Mapping Score To Bias

After summing all rule contributions:

- `raw_score >= 3` maps to `bullish`
- `raw_score <= -3` maps to `bearish`
- otherwise the signal maps to `neutral`

This means the engine requires multiple pieces of aligned evidence before it stops calling the tape neutral.

## Mapping Bias To Regime

The regime is a second interpretation layer built on top of the score and a few feature conditions.

- `neutral` bias maps to `choppy`
- if the gap is fading and price is still close to VWAP, the regime maps to `mean_reversion`
- if the first 15-minute move is at least `0.5%` in magnitude and price is at least `0.1%` away from VWAP, the regime maps to `trend_continuation`
- all other non-neutral cases currently map to `choppy`

This regime logic is intentionally coarse. It is meant to separate clean directional conditions from weaker or more conflicted states, not to classify every microstructure pattern.

## Confidence

Confidence is not a separate model output. It is derived from the score composition.

The current formula blends:

- score magnitude, capped at a maximum normalized magnitude of `9`
- agreement ratio, meaning the share of contributing rules that point in the same direction as the final score

Magnitude contributes `70%` of the confidence calculation and agreement contributes `30%`.

This means the engine expresses higher confidence when the signal is both strong and internally consistent.

## Option Posture Mapping

The engine also maps signal state to a high-level options posture:

- bullish + trend continuation -> `bullish_premium_sale_favored`
- bearish + trend continuation -> `defensive_bearish_premium_posture`
- mean reversion -> `fade_setup_only_if_risk_defined`
- everything else -> `patience_or_theta_oriented`

These are posture labels, not trade instructions. They summarize the kind of options environment the engine believes is most compatible with the observed regime.

## What The Engine Is Actually Testing

At a practical level, the current rules are testing a compact market-structure hypothesis:

- is the ticker trading above or below a fair intraday reference point
- did it move with enough force in the first 15 minutes to matter
- is it stronger or weaker than the broader tape
- is participation confirming that move
- is the opening gap continuing or being rejected
- has price escaped the opening range or failed inside it

When several of those answers line up in the same direction, the engine produces a directional bias. When they conflict or remain weak, the engine stays neutral or marks the regime as choppy.

## Important Limitations

The current signal mechanics are deliberately narrow.

- the score is rule-based, not statistically optimized
- most rules use fixed thresholds from configuration defaults
- only `QQQ` relative strength is used directly in scoring today
- several computed features are stored for analysis but do not yet affect the score
- the engine is designed for once-per-day post-open evaluation, not all-day intraday forecasting

For the exact fields emitted by the engine, see [FIELD_REFERENCE.md](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md). For the product-level contract and runtime model, see [PROJECT_SPEC.md](/Users/emt/Workspace/opx-directionality/docs/PROJECT_SPEC.md).
