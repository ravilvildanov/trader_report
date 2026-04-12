# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Freedom Calculator — tool for processing broker reports (Freedom Finance) and calculating financial results (FIFO) in RUB. Ships as a CLI (`main.py`) and a Streamlit web app (`streamlit_app.py`). User-facing text, column names, and log messages are in Russian — preserve Russian identifiers (e.g., `Тикер`, `Операция`, `Остаток`, `Валюта`) when editing data-processing code.

## Commands

```bash
# CLI — single period
python main.py <broker.xlsx> --out <output_dir>

# CLI — with prior-period report(s) for FIFO cost basis
python main.py <broker.xlsx> <previous.xlsx> --out <output_dir>

# Streamlit web UI
streamlit run streamlit_app.py
./run_app.sh   # creates ./venv, installs deps, launches on :8501

# Install
pip install -r requirements.txt              # local
pip install -r requirements_streamlit.txt    # Streamlit Cloud
```

Note: `main.py` hardcodes the rates file to `USD_01_01_2021_31_12_2024.xlsx`. The `TradeReportProcessor` constructor also takes a `rates_path`; Streamlit passes it explicitly. No test framework is configured — the README references `test_modular_structure.py` but it does not exist in the tree.

## Architecture

`TradeReportProcessor` (`src/trade_report_processor.py`) is the orchestrator. `process()` runs a fixed pipeline; each step mutates a `DataFrame` field on the processor, and `save_reports()` writes CSVs to the output dir.

Pipeline order (don't reorder without understanding downstream dependencies):

1. **`_load_data`** — `DataLoaderFactory` picks an xlsx/pdf loader (`data_loaders.py`); `SecuritiesLoader` reads the positions sheet. Trades are then filtered to a single currency (default `USD`) — anything else is dropped before downstream steps see it.
2. **`_load_and_normalize_previous_trades`** — `PreviousTradesManager` loads prior-period xlsx files; operations normalized via `TradeDataProcessor`.
3. **`_load_splits`** — `SplitsDetector` reads a sheet whose name starts with `SecInOut`.
4. **`_process_data`** — `TradeDataProcessor` normalizes Buy/Sell, merges with `CurrencyRatesLoader` rates by `Дата сделки`, computes RUB amounts → `trades_in_rub_df`.
5. **`_process_securities`** — `SecuritiesCalculator` computes positions from trades; `SecuritiesMerger` reconciles with broker-reported balances and flags `insufficient_tickers` (calculated < reported, meaning prior-period data is needed).
6. **`_calculate_finance_result`** — `FinanceResultCalculator` applies FIFO across previous + current trades to produce per-ticker realized P&L.
7. **`_check_balance_discrepancies`** — compares calculated end balance vs. broker `На конец`; populates `balance_discrepancies` (tolerance 0.01). Shown as warnings in Streamlit UI.
8. **`_check_splits_warnings`** — flags result tickers that appear in `SecInOut` (cost basis may be wrong if splits aren't modeled).

Key data contracts: trades need columns `Тикер`, `Операция`, `Количество`, `Цена`, `Валюта`, `Сумма`, `Комиссия`, `Дата сделки`, `Расчеты`. Rates file must cover the full date range of both current and previous trades.

Outputs: `details.csv` (all trades with RUB), `calculated_securities.csv` (reconciled positions), `finance_result.csv` (FIFO P&L). The PDF generator (`pdf_report_generator.py`, `font_manager.py` for Cyrillic) exists but its call site in `save_reports` is currently commented out.

## Conventions

- Russian column names are part of the data contract with broker Excel exports — keep them verbatim.
- `Decimal` is imported in the processor but most arithmetic happens in pandas `float`. When touching money math, check the specific module rather than assuming.
- The README describes some classes (`NegativeBalanceHandler`, `TradeSummaryCalculator`) that no longer exist — trust the code in `src/`, not the README, when they disagree.
