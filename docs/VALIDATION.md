# Validation

## Purpose

This document covers signal-quality validation only.

Software correctness testing is intentionally out of scope here. The focus is how to evaluate whether the stored signals are useful, stable, and defensible once the system is running on persisted history.

## Validation Objective

Validation should answer:

- are bullish and bearish calls directionally useful
- is confidence meaningfully calibrated
- are canonical daily runs stable and reproducible
- do certain tickers or regimes systematically underperform
- are failures caused by data quality, provider instability, or weak thresholds

## Validation Dataset

Signal validation should primarily use persisted canonical daily runs.

Preferred input set:

- canonical runs by trade date
- partial canonical runs only when no full canonical run exists
- raw reruns only for instability and provider-drift analysis

Each validation record should include:

- trade date
- ticker
- bias
- confidence
- regime
- option posture
- provider
- validation state
- selection status
- config fingerprint

## Outcome Definition

Validation only works if the realized-outcome definition is fixed in advance.

Candidate outcome definitions:

- close of day versus signal-time price
- 30-minute forward return after signal time
- maximum favorable excursion after signal time
- directional move beyond a fixed threshold

Rules:

- choose one primary outcome definition for headline reporting
- keep alternative definitions separate
- do not switch definitions after looking at results

## Core Metrics

Recommended first-pass metrics:

- directional hit rate
- bullish hit rate
- bearish hit rate
- neutral frequency
- average forward return by bias
- confidence-bucket hit rate
- ticker-level hit rate
- regime-level hit rate
- unavailable rate
- canonical versus raw-run disagreement rate

These should be segmented by:

- ticker
- provider
- config fingerprint
- regime
- confidence bucket

## Confidence Validation

Confidence should be validated as a calibration signal.

Suggested approach:

- split signals into confidence buckets such as `0-39`, `40-59`, `60-79`, `80-100`
- compare realized directional success across those buckets
- verify whether higher confidence corresponds to better realized quality

If confidence is not monotonic with realized quality, the scoring or confidence mapping should be revised.

## Stability Validation

Validation should explicitly measure repeat-run stability.

Questions to answer:

- how often do raw reruns disagree with the canonical run
- do reruns differ because of data completeness or because features drift
- how much do score, bias, or confidence move across repeated same-day runs

Useful stability metrics:

- rerun disagreement rate
- average absolute score change between reruns
- canonical promotion reason frequency

## Failure Analysis

Validation should preserve failure visibility.

Important failure slices:

- invalid runs
- partial canonical runs
- unavailable tickers
- ticker-specific underperformance
- provider instability days
- low-confidence false positives
- high-confidence false positives

The goal is to determine whether failures are coming from:

- bad data
- unstable provider inputs
- weak feature definitions
- poor thresholds
- poor outcome definitions

## Recommended Workflow

1. Persist all raw runs.
2. Let canonical selection identify the official daily run.
3. Run `opx-evaluate` to capture realized close-of-day outcomes for canonical runs.
4. Evaluate hit rate, return distribution, and calibration by ticker, regime, and confidence.
5. Review disagreement between canonical and non-canonical reruns.
6. Change one variable at a time.
7. Re-run the validation on the full stored history.

## Early Validation Exit Criteria

Before expanding scope, the project should be able to show:

- stable canonical-run selection behavior
- cutoff-stable feature computation
- reproducible persisted outputs
- explicit validation states for failures
- a documented outcome definition
- segmented signal-quality reporting by ticker and confidence
