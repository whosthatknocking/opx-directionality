# opx-directionality

`opx-directionality` is a post-open directionality engine for a fixed watchlist. It runs once after the open, normalizes provider data into one internal schema, scores each ticker with a deterministic rule engine, persists each run, and supports later multi-run review.

## Package And Config

- Python package path: `opx`
- fetcher entry point: `opx-directionality` -> `opx.fetcher:main`
- viewer entry point: `opx-viewer` -> `opx.viewer:main`
- Default config path: `~/.config/opx-directionality/config.toml`
- Example config: [`config/example.toml`](/Users/emt/Workspace/opx-directionality/config/example.toml)

Example config:

```toml
tickers = ["TSLA", "NVDA", "UBER", "MSFT", "GOOGL", "ORCL", "PLTR"]
```

## Provider Notes

Providers are abstracted behind a provider interface and must emit the same normalized internal market-bar schema before features are computed.

Current provider warning:

- `yfinance` is convenient for prototyping, but it is unofficial, can be interrupted, and may revise or omit intraday bars. Treat it as a research feed, not a production-grade market-data service.

Provider-specific behavior must stay inside the provider implementation. Downstream feature, scoring, and storage code uses provider-agnostic normalized fields documented in [`docs/FIELD_REFERENCE.md`](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md).

## Storage And Logging

- Storage is swappable via config: `file` or `sqlite`
- Every run is logged under `logs/`
- `logs/opx_runs.log` captures one summary line per run
- Detailed per-run logs are written as `logs/<run_id>.log`

## Viewer

Use [`scripts/view_runs.py`](/Users/emt/Workspace/opx-directionality/scripts/view_runs.py) to load multiple stored runs and visualize signal quality over time.

Installed entry point:

- `opx-viewer`

Example:

```bash
opx-viewer --storage-kind file --storage-target output/runs
```

## License

This project is licensed under the MIT License. See [LICENSE](/Users/emt/Workspace/opx-directionality/LICENSE).

## Development

- Install dev dependencies with `pip install -e ".[dev]"`
- Run lint with `pylint $(git ls-files '*.py')`
- Run tests with `pytest -q`
