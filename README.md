# opx-directionality

`opx-directionality` is a post-open directionality engine for a fixed watchlist. It is built as one workflow with connected parts: early-session data collection, directionality scoring, and end-of-day validation. The collection stage captures a consistent snapshot of the market shortly after the open, after the initial burst of opening volatility has started to settle, so each symbol can be evaluated from a comparable morning state. The directionality stage turns that snapshot into an explainable directional read that can be used as one input within a broader discretionary or systematic options-trading process. The validation stage closes the loop after the market close by comparing that fixed morning read against the realized outcome for the same day. Taken together, these parts make the engine useful not as a complete trading system or a stream of intraday updates, but as a stable, repeatable framework for generating, tracking, and improving a post-open directional signal over time.

At a high level, the working hypothesis is that the market often reveals a usable directional bias shortly after the open once the noisiest opening imbalance begins to clear. If price position, early range behavior, and related context align in a coherent way, that early structure may contain information about how the symbol is likely to behave through the rest of the session. The engine exists to capture that hypothesis in a repeatable form, so it can be tested, challenged, and refined against realized outcomes instead of remaining a purely discretionary impression.

## Features

- provider-neutral normalized market-data pipeline
- deterministic post-open feature computation at a fixed signal cutoff
- explainable rule-based scoring with signal validation metadata
- swappable `file` and `sqlite` persistence backends
- per-run logs plus aggregate run history under `logs/`
- canonical daily run selection across repeated same-day reruns
- browser-based viewer for reviewing stored runs, validation state, and signal drift

## Quick Start

1. Create and activate a local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install the project:

```bash
pip install -e .
```

3. Create `~/.config/opx-directionality/config.toml`:

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

4. Run the morning fetcher:

```bash
opx-directionality
```

5. Generate a browser-viewable report for stored runs:

```bash
opx-viewer --storage-kind file --storage-target output/runs
```

By default this writes `output/viewer/index.html`. Add `--open` to launch the report in the default browser.

After the market close, capture realized close-of-day outcomes for canonical runs:

```bash
opx-evaluate
```

## Commands

`opx-directionality` runs the morning fetch/score/persist pipeline.

`opx-viewer` generates the HTML report from stored runs.

`opx-evaluate` records realized close-of-day outcomes for canonical runs.

`PYTHONPATH=src python3 -m opx.fetcher` runs the fetcher directly from the repo without installing scripts.

`PYTHONPATH=src python3 -m opx.viewer` runs the viewer directly from the repo without installing scripts.

## Configuration

- Default config path: `~/.config/opx-directionality/config.toml`
- Example config: [`config/example.toml`](/Users/emt/Workspace/opx-directionality/config/example.toml)
- Python package path: `opx`
- Fetcher entry point: `opx-directionality` -> `opx.fetcher:main`
- Viewer entry point: `opx-viewer` -> `opx.viewer:main`

Runtime settings live under `[settings]`. Backend-specific storage options belong under `[storage.<backend>]`. Provider-specific options belong under `[providers.<provider_name>]`.

Example:

```toml
[settings]
tickers = ["TSLA", "NVDA", "UBER", "MSFT", "GOOGL", "ORCL", "PLTR"]
data_provider = "yfinance"

[providers.yfinance]
interval = "5m"
```

## Storage And Logging

Storage backends: `file` and `sqlite`.

File-store default target: `output/runs`.

Aggregate run log: `logs/opx_runs.log`.

Per-run logs: `logs/<run_id>.log`.

Repeated same-day runs are preserved as raw runs.

At most one run per trade date/provider/config group is promoted to `canonical` or `partial_canonical`.

## Provider Notes

Providers are abstracted behind a provider interface and must emit the same normalized internal market-bar schema before features are computed.

- `yfinance` is convenient for prototyping, but it is unofficial, can be interrupted, and may revise or omit intraday bars. Treat it as a research feed, not a production-grade market-data service.

## Documentation

Docs index: [docs/README.md](/Users/emt/Workspace/opx-directionality/docs/README.md).

User workflow: [docs/USER_GUIDE.md](/Users/emt/Workspace/opx-directionality/docs/USER_GUIDE.md).

Product contract: [docs/PROJECT_SPEC.md](/Users/emt/Workspace/opx-directionality/docs/PROJECT_SPEC.md).

Signal mechanics: [docs/SIGNAL_MECHANICS.md](/Users/emt/Workspace/opx-directionality/docs/SIGNAL_MECHANICS.md).

Field reference: [docs/FIELD_REFERENCE.md](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md).

Validation strategy: [docs/VALIDATION.md](/Users/emt/Workspace/opx-directionality/docs/VALIDATION.md).

## Development

Development workflow and local quality-check commands live in [docs/DEVELOPMENT.md](/Users/emt/Workspace/opx-directionality/docs/DEVELOPMENT.md).

## License

This project is licensed under the MIT License. See [LICENSE](/Users/emt/Workspace/opx-directionality/LICENSE).
