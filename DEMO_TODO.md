# Tender Assistant demo handoff

## Module layout update

Code now lives under `tender_assistant/` with separate `pricing`, `text`, `schedules`,
`documents`, `reporting` and `cli` packages; tests live in `tests/`. Older script
commands below are historical notes. Use the current command mapping in README.md:
`python -m tender_assistant.cli.batch_rates`, `python -m tender_assistant.text.summary`,
`python -m tender_assistant.reporting.demo`, etc., from the service folder.
The `.env`, outputs and Foundry `main.py` paths have not moved.

## Agreed scope

Manager feedback applies to the TEXT portion: a concise draft briefing to help an estimator complete the Tender Management Report, not a replacement report or populated spreadsheet. Use seven sections: tender summary, key information, initial risks/assumptions, QA/compliance, contract observations, high-level work by trade, and estimator questions. User clarification: the final demo MUST combine this briefing with Python-calculated indicative values, calculation breakdown, assumptions and risks in ONE report. Do not remove valuation from the deliverable. Success criterion: an estimator finds it useful and measures roughly 30–60 minutes of initial-review time saved; this benefit is a target, not yet demonstrated.

Generate with `tender_summary.py --profile estimator-brief` (the default); render separately with `estimator_brief.py SUMMARY.json --output REPORT.html`. Existing legacy summaries remain supported. Keep the three-document review limitation visible.

Prioritize an end-to-end demo with a reasonable architecture. Luna handles text and historical-rate recommendations; Python performs exact decimal calculations. Comparable rates may produce indicative amounts with explicit assumptions and risks. Do not block the demo on full commercial verification. All report content is English.

## Working flow

1. Extract schedule quantities and retain source locations and file fingerprints.
2. Recommend a historical rate ID; retrieve its price in Python.
3. Save a versioned snapshot of quantity, selected rate, rationale and risks.
4. Recalculate offline and explicitly select snapshot versions for batches.
5. Generate an English HTML demo report from a verified saved batch.
6. Generate a saved English document summary with source locators using `tender_summary.py`; combine it with the pricing report via `--summary`. Re-rendering does not call Luna.

## Current demonstration

Source folder: `src/agent-framework-agent-basic-responses`.
Selected rows: 104, 105, 106, 153, 154 of the Hopuhopu 0A schedule.
Row 106 uses `outputs/matches/row-106-context-v1.json`; other rows use v1.
Selected-row subtotal: 558732.0. Pending review; not the complete tender value.
The original row 106 snapshot remains available. Its changed rate reflects a new model selection with additional evidence, not an arithmetic change.

```sh
python batch_rate_matching.py --rows 104 105 106 153 154 --trade Earthworks --offline --snapshot 106=outputs/matches/row-106-context-v1.json
python demo_report.py outputs/batches/BATCH_FILE.json --output outputs/reports/tender-demo.html
```

Replace BATCH_FILE with the output printed by the batch command. Report generation refuses to overwrite existing files; choose a new filename for a new report.

## Deferred work

- Multi-trade demo first: defer detailed trade boundary corrections, Dayworks and
  provisional-sum separation, percentage bases, lump-sum rules and unit aliases.
  Display representative selected-item amounts and unpriced coverage clearly;
  do not imply that the demo subtotal is a complete tender quotation.

- CA-1201 drawing and geotechnical review; historical rate suitability and inclusions.
- Currency, GST and monetary display-rounding policy confirmation.
- Extend the three-document demo summary to the full tender package; check citation meaning, not only valid source IDs.
- Expand rate matching across the schedule; decide handling for percentages, lump sums, unit aliases and extra-over rates.
- OCR and visual extraction, remaining Word parts/revisions, ZIP contents and superseded-document handling.
- Verify model citation accuracy and alternative-rate selection policy; lexicographic ID tie-break is provisional.
- Classification and schedule-preparation tests were explicitly deferred by the user.
- Add durable batch override/report checks and improve source/input validation before production use.
- TP forecast/sequencing, durations, material/subcontract cost evidence, UI and cloud deployment.
- Review Git changes and commit code and dependency lockfile; keep tender inputs, rate library, secrets and generated outputs out of Git.

## Quota context

Codex allowance is constrained; company Azure Luna capacity is available. Prefer complete useful implementation steps and reuse saved results when no fresh model judgment is needed.

## Final deployment target

Deploy the custom code as a Hosted Agent in the company's existing Microsoft Foundry project `dev-ai-agent-core`, for internal staff. The earlier portal-created prompt agent does not yet run this code. First connect the summary and pricing pipeline to the hosted entry point, replace local-only file paths with controlled storage inputs, and configure company identity/access and persistent result storage. Do not provision or publish infrastructure as part of the local demo step.

## Summary demo commands

```sh
python tender_summary.py outputs/evidence/row-106-context-v2.json --output outputs/summaries/demo-v1.json
python demo_report.py outputs/batches/BATCH_FILE.json --summary outputs/summaries/demo-v1.json --output outputs/reports/tender-demo-v2.html
```

The first command calls Luna and reads all extracted segments in the three-document package, not just the earlier row-106 keyword matches. Saved source excerpts allow review without another model call. The second command is offline. Existing output files are never overwritten.
