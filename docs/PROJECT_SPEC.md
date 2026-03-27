# Project Specification

## 1. Overview

`opx-directionality` is a post-open directionality engine for a fixed watchlist.

The project fetches intraday and recent historical market data for selected tickers and benchmark ETFs, normalizes all provider payloads into a shared internal schema, computes deterministic post-open features, produces an explainable directional bias at a fixed signal time, persists run outputs through a swappable storage layer, captures run logs, and supports later realized-outcome evaluation.

Core product rules:

- the engine is post-open only
- one configured data provider is active for a run
- the persisted signal schema is a product contract
- feature definitions must remain stable and exactly reproducible in backtests
- the scoring engine must remain explainable in v1
- the core engine must remain independent of news and social inputs in v1
- provider-specific details must remain behind explicit provider interfaces
- storage must remain swappable without changing scoring or feature code

Current minimum supported runtime:

- Python `3.9+`

### 1.1 Implementation Progress

Completed in the current milestone set:

- provider-neutral normalized market-data contract
- swappable `file` and `sqlite` storage backends
- per-run and aggregate logging
- canonical daily run selection metadata across repeated runs
- structured validation metadata for signals and runs
- signal-cutoff-stable feature computation for intraday and daily context

Still expected in later milestones:

- richer evaluation against realized outcomes
- manual canonical override workflow
- additional providers beyond `yfinance`

## 2. Core Objective

Build a once-per-day, on-demand trading aid for morning options decision-making on a selected watchlist.

The engine is intended to answer:

- is the ticker acting strong, weak, or choppy after the open
- is the early move more consistent with continuation, mean reversion, or indecision
- what high-level options posture fits that regime

The engine is not intended to:

- act as a general stock prediction platform
- stream live intraday updates
- place trades automatically
- select exact option contracts in v1
- depend on discretionary news or social inputs in the scoring core

## 3. Naming And Packaging

The project name, repository name, package path, and docs naming should use `opx-directionality`.

Naming rules:

- the Python package path is `opx`
- user-facing commands and docs use `opx-directionality`
- fetch pipeline entry point should map to `opx.fetcher:main`
- viewer entry point should map to `opx.viewer:main`
- the primary tracked product spec file is `docs/PROJECT_SPEC.md`
- stable interfaces should use explicit version fields rather than implicit behavior changes

## 4. Runtime Model

### 4.1 Single Daily Signal Run

The v1 runtime model is one on-demand signal run per trading day.

Behavior:

- a run evaluates the full configured watchlist for one signal time
- all tickers in a run use the same config snapshot
- all tickers in a run use the same active data provider
- runs should continue per ticker when one ticker fails
- the default signal time is `09:45 ET`

Alternative signal times may be added later, but v1 evaluation should standardize on one time.

### 4.1.1 Repeated Runs On The Same Day

The system may be run multiple times in the same morning.

Rules:

- repeated runs on the same trade date are allowed
- each execution must create a distinct run record with a unique run id
- repeated runs must not silently overwrite prior raw runs
- repeated runs may exist for retries, diagnostics, provider instability, or intentional manual reruns
- the system should distinguish between raw runs and the official daily run used for evaluation

### 4.1.2 Canonical Daily Run

Even when multiple raw runs exist for the same date, the project should support selecting one official daily run.

The recommended model is:

- keep all raw runs
- assign at most one canonical run per trade date, signal time, provider, and effective config snapshot
- allow manual override when the automatically chosen canonical run is not the desired one

Canonical selection should be explicit and explainable, never implicit.

### 4.2 Config Source

The runtime should support one explicit config file per run.

Default config path:

- `~/.config/opx-directionality/config.toml`

Required example shape:

```toml
[settings]
tickers = ["TSLA", "NVDA", "UBER", "MSFT", "GOOGL", "ORCL", "PLTR"]
benchmark_primary = "QQQ"
benchmark_secondary = "SPY"
signal_time_et = "09:45"
bar_interval = "5m"
lookback_days_intraday = 20
lookback_days_daily = 10
engine_version = "0.1.0"
config_version = "2"
data_provider = "yfinance"
storage_type = "file"
logging_dir = "logs"
bullish_threshold = 3
bearish_threshold = -3
vwap_band_pct = 0.15
strong_move_pct = 0.75
relative_strength_pct = 0.30
volume_multiple_threshold = 1.5

[storage.file]
target = "output/runs"

[providers.yfinance]
interval = "5m"
```

The config loader is responsible for:

- watchlist selection through `settings.tickers`
- benchmark selection
- signal time
- bar interval
- intraday and daily lookback windows
- active data provider
- active data provider selection through `settings.data_provider`
- provider-specific configuration under `providers.<provider_name>`
- scoring thresholds and weights as flat settings keys
- engine version and config version
- storage backend selection such as `storage_type`
- backend-specific storage settings under `storage.<backend>`
- logging settings such as `logging_dir`

Rules:

- if config values are missing, documented code defaults may apply
- malformed config values should fail clearly or fall back in a documented way
- startup output should make the resolved runtime settings visible
- secrets must never live in tracked repo files
- repo examples may live under `config/`, but the default operational config lives under the user config directory
- application-wide runtime configuration should live under `[settings]`
- runtime settings under `[settings]` should be flattened rather than nested into `settings.storage` or `settings.logging`
- backend-specific config should move into backend-specific tables such as `[storage.file]`
- provider-specific settings must be namespaced so multiple providers can coexist in one config without key collisions

## 5. Current Product Scope

The project currently targets:

- selected ticker watchlists only
- stock-price-based features only
- explainable post-open bias generation
- deterministic feature engineering
- rule-based scoring
- persistence of run metadata and ticker outputs
- later realized-outcome evaluation from stored history
- visualization of multiple historical runs through an independent viewer script that produces a webpage report

The project does not currently aim to:

- scan a broad market universe
- consume tick-level data
- deliver streaming or constantly refreshed signals
- place or stage brokerage orders
- couple the core score to news or social feeds
- promote a trained model before the rule engine has sufficient logged history

## 6. Target Users And Use Case

Primary use case:

- morning options trading on a fixed watchlist
- user checks the signal after the open, typically around `9:45 ET`
- engine returns directional bias, confidence, regime, and a suggested options posture

Typical tickers:

- `NVDA`
- `TSLA`
- `UBER`
- `MSFT`
- `GOOGL`
- `ORCL`
- `PLTR`

## 7. Data Provider Strategy

### 7.1 Active Provider Model

At runtime there is exactly one active data provider.

Current provider:

- `yfinance`

Future provider candidates:

- `marketdata`
- `polygon`
- `alpaca`

Rules:

- data for a single run must not mix providers unless explicitly designed later
- all persisted runs must record the provider name
- provider-specific behavior must remain behind the data-access layer
- feature, scoring, reporting, and storage modules should consume provider-neutral normalized data

### 7.2 Provider Abstraction Requirements

The provider boundary should be explicit.

Provider rules:

- normalize provider responses into a shared internal market-bar format
- internal schema must be agnostic of the provider
- map vendor semantics carefully instead of forcing misleading fields
- leave unavailable data blank or mark the ticker unavailable rather than invent values
- keep raw provider payload capture optional for debugging
- document provider-specific warnings in the README and related docs
- provider-specific config should live under a namespaced table such as `[providers.yfinance]`

### 7.3 YFinance Provider

`yfinance` is the initial provider because it is fast to prototype, easy to integrate in Python, and sufficient for 5-minute-bar post-open signal generation on a selected watchlist.

Known limitations:

- unofficial and non-vendor-grade
- possible inconsistencies or interruptions
- limited intraday history depth
- possible delayed, missing, or revised intraday bars
- not a durable production-grade long-term data backbone

## 8. Normalized Internal Schema

All providers must normalize market bars into a shared internal schema before feature computation.

Normalized market-bar fields:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

Schema rules:

- internal field names must not encode the provider name
- normalized bars should preserve timezone clarity and session alignment
- provider-specific extra fields may exist internally for debugging, but the scoring path must depend only on normalized fields
- all internal fields should be documented centrally

Derived feature, signal, and run fields are documented in [`docs/FIELD_REFERENCE.md`](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md).

## 9. Output Contract

The persisted signal schema is a primary product contract.

Per ticker, the engine must return:

- `ticker`
- `signal_time`
- `status`
- `reason` when unavailable
- `bias`
- `confidence`
- `regime`
- `option_posture`
- `raw_score`
- `factor_summary`
- `factors`

Example output:

```json
{
  "ticker": "NVDA",
  "signal_time": "2026-03-26T09:45:00-04:00",
  "status": "ok",
  "bias": "bullish",
  "confidence": 72,
  "regime": "trend_continuation",
  "factors": {
    "gap_pct": 0.8,
    "first_15m_return": 1.1,
    "first_15m_return_minus_qqq": 0.6,
    "price_vs_vwap_pct": 0.4,
    "opening_volume_multiple": 1.8,
    "gap_hold_or_fade": "holding"
  },
  "option_posture": "bullish_premium_sale_favored"
}
```

Output rules:

- explainability matters as much as the label
- factor contributions must remain inspectable
- unavailable signals must be first-class outputs, not silent drops
- schema drift should be versioned and documented

## 10. Selected Ticker Workflow

The engine operates only on a defined watchlist.

Reason for the selected-ticker approach:

- simpler testing
- easier debugging
- better feature inspection
- less temptation to overbuild a scanner before core signal quality is understood

## 11. Feature Set For v1

### 11.1 Today / Post-Open Features

Computed from the open to `09:45 ET`:

- `gap_pct`
- `first_5m_return`
- `first_10m_return`
- `first_15m_return`
- `first_15m_range_pct`
- `first_15m_close_vs_open`
- `price_vs_vwap_pct`
- `opening_volume_multiple`
- `opening_range_break_status`
- `gap_hold_or_fade`
- `candle_body_to_range_ratio`
- `intraday_high_low_position`

### 11.2 Recent Daily Context Features

Computed from recent daily bars:

- `previous_day_return`
- `previous_day_close_location_in_range`
- `three_day_return`
- `five_day_return`
- `atr_normalized_recent_move`

### 11.3 Historical Intraday Baseline Features

Computed from recent intraday history:

- `average_first_15m_return`
- `average_first_15m_volume`
- `average_trend_persistence`

### 11.4 Relative Strength Features

Compared with benchmark ETFs:

- `first_15m_return_minus_qqq`
- `first_15m_return_minus_spy`
- `gap_pct_minus_qqq_gap`
- `gap_pct_minus_spy_gap`

Feature rules:

- definitions must remain deterministic
- formulas should be documented and stable
- new features should be additive and versioned
- the v1 feature set should avoid opaque feature engineering

## 12. Scoring And Explainability

The engine should use a rule-based scoring system in v1.

Scoring requirements:

- every directional output must be explainable
- rule contributions should be inspectable through `factor_summary`
- thresholds should live in config where practical
- scoring must map cleanly into bias, confidence, regime, and posture

Expected output categories:

- `bias`: bullish, bearish, or neutral
- `confidence`: integer confidence estimate
- `regime`: continuation, mean reversion, or choppy
- `option_posture`: high-level options stance

## 13. Storage Strategy

Storage must be agnostic of the underlying storage system.

Storage rules:

- storage should be abstracted behind a clear interface
- storage should be swappable without changing the engine pipeline
- storage backends must persist run metadata and per-ticker signals
- storage should support loading multiple historical runs for later evaluation
- storage payloads should stay provider-agnostic
- storage should preserve all raw runs, even when one canonical daily run is chosen
- storage should support recording canonical-selection metadata or a canonical run index

Supported backends in the current project:

- `file`
- `sqlite`

Possible future backends:

- object storage
- hosted SQL
- analytical warehouse

### 13.1 Canonical Run Persistence

The project should support a policy layer for deciding which run is the official daily run.

Canonical persistence requirements:

- canonical selection should be modeled separately from raw run storage
- raw run persistence should remain append-oriented
- canonical selection may be stored as an index, pointer, or status field rather than by deleting duplicate runs
- the chosen canonical run should record why it was selected

Suggested canonical metadata:

- `selection_status`: `canonical`, `partial_canonical`, `retry`, `diagnostic`, or similar
- `selection_reason`: such as `earliest_complete_post_signal`, `best_available_partial`, or `manual_override`
- `selected_at`: timestamp when the canonical decision was recorded

### 13.2 Canonical Selection Policy

Canonical run selection should follow an explicit policy.

Recommended decision order:

1. signal-time eligibility
2. data completeness
3. config snapshot match
4. provider consistency
5. earliest valid run after the configured signal time
6. manual override when needed

Policy details:

- a run is eligible only if it was executed after the configured signal time for that trade date
- only runs with the same effective config snapshot should compete for the same canonical slot
- only runs from the same provider should compete for the same canonical slot unless a later policy says otherwise
- if one or more runs are fully complete, choose the earliest valid fully complete run
- if no fully complete run exists, choose the run with the highest completeness score and mark it partial
- the system should preserve the reason a run was promoted or rejected

## 14. Logging And Run Capture

Each engine run must be captured under a logs directory.

Logging requirements:

- detailed per-run logs should be written under `logs/`
- an aggregate run log such as `logs/opx_runs.log` should append one summary entry per run
- logs should record run id, timestamp, provider, and ticker-level outcomes
- log paths should be recorded in persisted run metadata when practical

Run capture requirements:

- every run should have a unique run id
- every persisted run should record the config and engine versions
- every persisted run should record the active provider
- every run should record enough metadata to support canonical selection and later audit
- repeated runs for the same date should remain visible in logs and storage

## 15. Evaluation Strategy

The project should support later evaluation across multiple historical runs.

Evaluation goals:

- compare bias outputs with later realized outcomes
- inspect confidence calibration over time
- review regime labeling consistency
- study per-ticker score tendencies and failure rates
- support iterative refinement of features and rules

Evaluation rules:

- evaluation must use persisted history, not reconstructed memory
- reproducibility matters more than maximizing apparent win rate
- unavailable signals should remain in the record for diagnostic value
- evaluation should default to canonical daily runs unless the user explicitly requests all raw runs
- the system should preserve enough metadata to compare canonical versus non-canonical reruns when needed

### 15.1 Validation Layer

The project should include an explicit validation layer to determine whether data, features, ticker signals, and full runs are valid, partial, or invalid.

Validation must not be inferred only from whether the pipeline raised an exception.

Validation layers:

- data validation
- feature validation
- signal validation
- run-level validation

Data validation should verify:

- required normalized fields exist
- timestamps are ordered and timezone-valid
- enough intraday bars exist before the signal cutoff
- enough daily history exists for all configured features
- benchmark data is present

Feature validation should verify:

- no unexpected `NaN` or infinite feature values
- bounded fields remain within expected ranges
- categorical fields map to allowed values
- feature prerequisites were actually satisfied

Signal validation should verify:

- `status` is valid
- required output fields are populated for successful signals
- factor summaries are present for scored signals
- bias, regime, and posture values are valid enums

Run-level validation should verify:

- the run happened after the configured signal time
- all configured tickers were attempted
- all required benchmarks were available
- completion rate meets canonical-selection requirements
- provider and config match the intended canonical-selection policy

Validation outputs should be structured and persisted where practical.

Suggested validation states:

- `valid`
- `partial`
- `invalid`

Suggested validation reasons:

- `missing_intraday_bars`
- `missing_benchmark_data`
- `insufficient_daily_history`
- `feature_nan`
- `ran_before_signal_time`

### 15.2 Signal Cutoff Reproducibility

For canonical daily evaluation to be defensible, feature computation must be frozen to the configured signal cutoff.

Rules:

- rerunning later in the morning should not alter features that are defined only up to the configured signal time
- signal cutoff handling should be validated explicitly
- canonical selection should rely on signal-cutoff-stable feature computation

## 16. Viewer Requirements

The project should include a viewer feature as an additional independent Python script.

Viewer requirements:

- implemented as a separate script from the main CLI
- capable of loading multiple historical runs from the configured storage backend
- able to visualize data according to the evaluation strategy as a webpage report
- should support an `--open` option to open the generated report in the default browser
- should support basic summary statistics across runs
- should remain read-only with respect to stored run data

Viewer design direction:

- follow the institutional, ledger-inspired design system documented in the sibling OPX design spec
- prefer borders and structural hierarchy over shadows
- use compact, dense tables as the primary data surface
- include a functional header, tabs, and light/dark theme toggle

The viewer is intended to answer:

- how signal scores and confidence changed across runs
- how often each ticker was available or unavailable
- what directional tendencies are appearing over time

## 17. Documentation Requirements

Project documentation should keep all core requirements in one place under `docs/PROJECT_SPEC.md`.

Additional docs may support the project, but the spec remains the top-level source of truth.

Documentation requirements:

- `docs/PROJECT_SPEC.md` should contain the full product and technical game plan
- provider-specific warnings should appear in the README
- normalized fields should be documented in `docs/FIELD_REFERENCE.md`
- user-facing docs should align with the tracked spec

## 18. Non-Goals For v1

The following are explicitly out of scope for v1 unless later revised:

- automated order execution
- exact option contract selection
- streaming live recalculation all session
- discretionary sentiment or news integration in core scoring
- opaque machine-learning-based signal generation
- broad market scanning across thousands of symbols

## 19. Guiding Principles

The project should prioritize:

- deterministic behavior
- inspectable logic
- provider neutrality in internal schemas
- storage portability
- precise logging and history capture
- incremental extensibility without breaking contracts

The intent is to build a reliable research and decision-support engine first, then expand only after the logging, persistence, evaluation, and explainability foundation is strong.
