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
- `signal_time_et`: configured signal time in Eastern Time
- `provider_name`: provider used for the run
- `engine_version`: engine version string recorded with the run
- `config_version`: config contract version string
- `tickers`: ticker list evaluated in the run
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
- `factor_summary`: list of rule contributions with `name`, `score`, and `rationale`
- `factors`: normalized feature dictionary used by the rule engine

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
