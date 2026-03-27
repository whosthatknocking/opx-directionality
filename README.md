# opx-directionality

`opx-directionality` is a post-open directionality engine for a fixed watchlist. It runs once after the open, normalizes provider data into one internal schema, scores each ticker with a deterministic rule engine, persists each run, and supports later multi-run review.

## Current Status

Implemented in the current milestone set:

- provider-neutral normalized market-data pipeline
- swappable `file` and `sqlite` storage backends
- per-run logging plus aggregate run log
- cutoff-stable feature computation at the configured signal time
- structured validation metadata on signals and runs
- canonical daily run selection across repeated same-day runs
- viewer support for validation and canonical-run metadata

## Quick Start

1. Install the project:

```bash
pip install -e .
```

2. Create `~/.config/opx-directionality/config.toml`:

```toml
[settings]
tickers = ["TSLA", "NVDA", "UBER"]
data_provider = "yfinance"
storage_type = "file"
logging_dir = "logs"

[storage.file]
target = "output/runs"

[providers.yfinance]
interval = "5m"
```

3. Run the morning fetcher:

```bash
opx-directionality
```

4. Generate a browser-viewable report for stored runs:

```bash
opx-viewer --storage-kind file --storage-target output/runs
```

This writes an HTML report to `output/viewer/index.html`.
Add `--open` to launch it in the default browser.

## Local Setup

Typical local setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run:

```bash
opx-directionality
```

If you do not want to install the console script, you can run directly from the repo:

```bash
PYTHONPATH=src python3 -m opx.fetcher
```

## Package And Config

- Python package path: `opx`
- fetcher entry point: `opx-directionality` -> `opx.fetcher:main`
- viewer entry point: `opx-viewer` -> `opx.viewer:main`
- Default config path: `~/.config/opx-directionality/config.toml`
- Example config: [`config/example.toml`](/Users/emt/Workspace/opx-directionality/config/example.toml)

Example config:

```toml
[settings]
tickers = ["TSLA", "NVDA", "UBER", "MSFT", "GOOGL", "ORCL", "PLTR"]
data_provider = "yfinance"

[providers.yfinance]
interval = "5m"
```

## Provider Notes

Providers are abstracted behind a provider interface and must emit the same normalized internal market-bar schema before features are computed.

Application-wide runtime config should live under `[settings]` using flat keys such as `storage_type`, `logging_dir`, and `bullish_threshold`. Backend-specific storage settings belong under namespaced tables like `[storage.file]`.

Provider-specific config should live under `providers.<provider_name>`. Current implemented example:

```toml
[providers.yfinance]
interval = "5m"
```

Current provider warning:

- `yfinance` is convenient for prototyping, but it is unofficial, can be interrupted, and may revise or omit intraday bars. Treat it as a research feed, not a production-grade market-data service.

Provider-specific behavior must stay inside the provider implementation. Downstream feature, scoring, and storage code uses provider-agnostic normalized fields documented in [`docs/FIELD_REFERENCE.md`](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md).

## Storage And Logging

- Storage is swappable via config: `file` or `sqlite`
- Every run is logged under `logs/`
- `logs/opx_runs.log` captures one summary line per run
- Detailed per-run logs are written as `logs/<run_id>.log`
- Repeated same-day runs are preserved as raw runs
- One run per trade date/provider/config group may be marked `canonical` or `partial_canonical`

## Viewer

Use [`scripts/view_runs.py`](/Users/emt/Workspace/opx-directionality/scripts/view_runs.py) to load multiple stored runs and generate a local HTML report.

Installed entry point:

- `opx-viewer`

Example:

```bash
opx-viewer --storage-kind file --storage-target output/runs
```

By default, the report is written to `output/viewer/index.html`.
Use `--open` to open it automatically in the default browser.

## License

This project is licensed under the MIT License. See [LICENSE](/Users/emt/Workspace/opx-directionality/LICENSE).

## Development

- Install dev dependencies with `pip install -e ".[dev]"`
- Run lint with `pylint $(git ls-files '*.py')`
- Run tests with `pytest -q`
- Signal-quality validation methodology: [docs/VALIDATION.md](/Users/emt/Workspace/opx-directionality/docs/VALIDATION.md)
