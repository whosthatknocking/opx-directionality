# Field Reference

## Normalized Market Bar Fields

- `timestamp`: timezone-aware bar timestamp in Eastern Time after normalization
- `open`: bar open price
- `high`: bar high price
- `low`: bar low price
- `close`: bar close price
- `volume`: bar volume

## Run Fields

- `run_id`: unique identifier for one engine run
- `run_timestamp`: wall-clock timestamp when the run started
- `trade_date`: trade date associated with the configured signal timestamp
- `signal_time_et`: configured signal time in Eastern Time
- `provider_name`: provider used for the run
- `engine_version`: engine version string recorded with the run
- `config_version`: config contract version string
- `config_fingerprint`: stable fingerprint of the effective signal config
- `provider.settings`: active provider-specific config values for the selected provider, used indirectly through the config fingerprint and provider initialization
- `tickers`: ticker list evaluated in the run
- `signal_time_reached`: whether the run happened after the configured signal cutoff
- `completion_rate`: fraction of configured tickers that finished with `status=ok`
- `validation_state`: `valid`, `partial`, or `invalid`
- `validation_issues`: structured run-level validation issues
- `selection_status`: canonical-selection classification such as `canonical`, `partial_canonical`, `retry`, `candidate`, or `diagnostic`
- `selection_reason`: reason attached to the current selection status
- `log_path`: path to the detailed run log file

## Signal Fields

- `ticker`: evaluated symbol
- `signal_time`: timestamp used for the signal snapshot
- `status`: `ok` or `unavailable`
- `reason`: failure reason when status is unavailable
- `bias`: `bullish`, `bearish`, or `neutral`
- `confidence`: integer confidence score from 0 to 100
- `regime`: market-condition classification for the signal
- `option_posture`: high-level options posture suggestion
- `raw_score`: summed rule score before mapping
- `signal_price`: observed signal-time price used as the evaluation base
- `validation_state`: `valid`, `partial`, or `invalid`
- `validation_issues`: structured signal-level validation issues
- `realized_close`: same-day closing price used for realized-outcome evaluation
- `realized_return_pct`: close-of-day return versus `signal_price`
- `realized_outcome`: `positive`, `negative`, or `flat`
- `directional_hit`: whether the realized move agreed with a bullish or bearish signal
- `factor_summary`: list of rule contributions with `name`, `score`, and `rationale`
- `factors`: normalized feature dictionary used by the rule engine

## Regime Definitions

- `trend_continuation`: early price action, relative strength, and opening behavior indicate a directional move is more likely to persist than mean revert
- `choppy`: mixed or weak early signals indicate low directional conviction, range behavior, or a higher chance of false breaks
- `mean_reversion`: opening displacement or early momentum looks stretched relative to context, increasing the chance of reversal back toward the open, VWAP, or prior range
- `breakout_transition`: the tape is shifting from balance into expansion, but the move is not yet as established as a clean continuation regime
- `unclassified`: no regime label was assigned because the signal was unavailable, partial, or did not meet a clear classification rule

## Feature Fields

- `gap_pct`: opening gap versus the previous daily close
- `first_5m_return`: return from open to first 5-minute close
- `first_10m_return`: return from open to second 5-minute close
- `first_15m_return`: return from open to third 5-minute close
- `first_15m_range_pct`: first 15-minute high-low range as percent of open
- `first_15m_close_vs_open`: first 15-minute close relative to open
- `price_vs_vwap_pct`: latest price versus session VWAP
- `opening_volume_multiple`: first 15-minute volume versus historical first-15-minute average
- `opening_range_break_status`: `break_above`, `break_below`, or `inside_range`
- `gap_hold_or_fade`: whether the opening gap is holding or fading
- `candle_body_to_range_ratio`: body-to-range ratio of the opening 15-minute candle
- `intraday_high_low_position`: current close position within the session range
- `previous_day_return`: previous daily close versus prior daily close
- `previous_day_close_location_in_range`: prior close location within prior daily range
- `three_day_return`: close versus close three sessions earlier
- `five_day_return`: close versus close five sessions earlier
- `atr_normalized_recent_move`: recent move scaled by ATR
- `average_first_15m_return`: historical average first-15-minute return
- `average_first_15m_volume`: historical average first-15-minute volume
- `average_trend_persistence`: historical average move after the first 15 minutes
- `first_15m_return_minus_qqq`: ticker first-15-minute return minus QQQ
- `first_15m_return_minus_spy`: ticker first-15-minute return minus SPY
- `gap_pct_minus_qqq_gap`: ticker gap minus QQQ gap
- `gap_pct_minus_spy_gap`: ticker gap minus SPY gap
