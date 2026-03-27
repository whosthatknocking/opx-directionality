# User Guide

## Typical Workflow

1. Create `~/.config/opx-directionality/config.toml` from [`config/example.toml`](/Users/emt/Workspace/opx-directionality/config/example.toml).
2. Run `opx-directionality` after the open, typically around `09:45 ET`.
3. Review the console summary and persisted run artifacts.
4. If you rerun the engine in the same morning, the raw runs are preserved and canonical selection decides which run is the official daily snapshot.
5. Use [`scripts/view_runs.py`](/Users/emt/Workspace/opx-directionality/scripts/view_runs.py) or `opx-viewer` to generate a local HTML report for comparing score, confidence, validation, and canonical-selection trends.
6. Use `--open` if you want the generated report opened in the default browser immediately.

Place application-wide runtime config under `[settings]` using flat keys. Select the active provider with `data_provider = "..."`, put backend-specific storage config under `[storage.<backend>]`, and place provider-specific settings under `[providers.yfinance]`.

## Output Reading

- `bias` is the directional lean
- `confidence` is the agreement strength of the active rules
- `regime` distinguishes continuation, mean reversion, or chop
- `option_posture` is a posture suggestion, not a contract picker
- `factor_summary` records the explainable rule contributions
- `validation_state` shows whether the signal passed the current validation rules cleanly
- `selection_status` on the run tells you whether the run is canonical, partial canonical, retry, or diagnostic

## Provider Warnings

- `yfinance` may miss, delay, or revise intraday bars
- Intraday history depth is limited compared with vendor-grade feeds
- If data is unavailable, the engine marks that ticker unavailable instead of fabricating fields

## Related Docs

- Docs index: [`docs/README.md`](/Users/emt/Workspace/opx-directionality/docs/README.md)
- Product scope and architecture: [`docs/PROJECT_SPEC.md`](/Users/emt/Workspace/opx-directionality/docs/PROJECT_SPEC.md)
- Field definitions: [`docs/FIELD_REFERENCE.md`](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md)
