# User Guide

## Typical Workflow

1. Create `~/.config/opx-directionality/config.toml` from [`config/example.toml`](/Users/emt/Workspace/opx-directionality/config/example.toml).
2. Run `opx-directionality` after the open, typically around `09:45 ET`.
3. Review the console summary and persisted run artifacts.
4. Use [`scripts/view_runs.py`](/Users/emt/Workspace/opx-directionality/scripts/view_runs.py) to compare multiple runs and inspect score and confidence trends.

## Output Reading

- `bias` is the directional lean
- `confidence` is the agreement strength of the active rules
- `regime` distinguishes continuation, mean reversion, or chop
- `option_posture` is a posture suggestion, not a contract picker
- `factor_summary` records the explainable rule contributions

## Provider Warnings

- `yfinance` may miss, delay, or revise intraday bars
- Intraday history depth is limited compared with vendor-grade feeds
- If data is unavailable, the engine marks that ticker unavailable instead of fabricating fields

## Related Docs

- Product scope and architecture: [`docs/PROJECT_SPEC.md`](/Users/emt/Workspace/opx-directionality/docs/PROJECT_SPEC.md)
- Field definitions: [`docs/FIELD_REFERENCE.md`](/Users/emt/Workspace/opx-directionality/docs/FIELD_REFERENCE.md)
