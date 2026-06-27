# Daily Report MVP Design

## 1. Purpose
The Daily Report is a research summary generated from existing tools. It helps organize screening, backtest, and report outputs into a coherent snapshot. It is purely an aggregate reporting mechanism and is **not investment advice**.

## 2. MVP Scope
The first version of the Daily Report MVP will include:
- **Date / Run Metadata:** When the report was generated and what parameters were used.
- **Stock Universe Source:** Which stock list was scanned.
- **Daily Screening Summary:** High-level metrics from the daily scan.
- **Watchlist Candidates for Further Review:** Filtered list of stocks meeting predefined research criteria.
- **Basic Technical Indicators Summary:** Inclusion of indicators already available from the existing scanner.
- **Backtest Summary Integration:** A summary of standard backtest performance for candidates if feasible.
- **Parameter Sweep Summary Integration:** A summary of parameter sweep highlights if feasible.
- **Walk Forward Summary Integration:** A summary of walk forward stability highlights if feasible.
- **Risk / Limitation Notes:** Clear disclaimers that this is research only.
- **Output Format:** Markdown report initially.

## 3. Out of Scope
The following are explicitly excluded from the MVP:
- Broker API integration
- Paper trading
- Auto trading
- Semi-auto trading
- Order execution
- AI/ML prediction or modeling
- Investment recommendation wording (e.g., "buy signals", "recommended stocks")
- Guaranteed profit wording
- Real-time alerting
- Portfolio optimization

## 4. Proposed Input Sources
The MVP will draw from:
- The existing stock list file (e.g., `stocks.txt`) or auto-stock-list.
- Existing scanner and daily watchlist outputs.
- Existing backtest engine results.
- Existing parameter sweep and walk-forward engine logic to supply summary metrics.

## 5. Proposed Output Format
- **Phase 1 Output:** Markdown report.
  - Default path: `output/daily_report.md`
- **Optional Phase 2 Output:** Excel export.
  - Default path: `output/daily_report.xlsx`
- **Console Summary:** Optional standard output summary of the run.

## 6. Suggested Report Sections
1. **Report Metadata:** Date, time, execution context.
2. **Market / Universe Summary:** Number of stocks scanned, data period.
3. **Screening Overview:** Pass/fail counts and error counts.
4. **Watchlist Candidates for Further Review:** Tabular data of candidate stocks.
5. **Backtest Highlights:** Summary metrics from standard strategy tests.
6. **Parameter Sweep Highlights:** Optimized parameters context.
7. **Walk Forward Highlights:** Robustness and stability context.
8. **Risk Notes:** Standard research-only warnings.
9. **Data Limitations:** Missing data or known issues.
10. **Next Research Actions:** Prompts for manual follow-up or deeper CLI research.

## 7. MVP Implementation Plan
- **Phase 5.1:** Daily Report MVP design / scope lock *(Current Phase)*
- **Phase 5.2:** Daily Report data model / builder
- **Phase 5.3:** Daily Report Markdown exporter
- **Phase 5.4:** Daily Report CLI
- **Phase 5.5:** Daily Report docs and smoke tests
- **Phase 5.6:** Optional Excel exporter

## 8. Acceptance Criteria
The MVP is considered complete when:
- It works purely from existing data/scanner outputs.
- It does not require broker or API keys.
- It does not make or imply investment recommendations.
- It produces deterministic Markdown output.
- It has test coverage for the builder, exporter, and CLI.
- It handles empty or partial data gracefully (e.g., no candidates found).
