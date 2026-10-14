# Local estimate tools

The first tool-enabled slice is **read-only**. It reads existing API exports;
it does not analyse uploads, rematch historical rates, approve estimates or
overwrite snapshots. No new infrastructure is required for offline tests.

## Code boundaries

- `tender_assistant/services/estimates.py`: SDK-independent loading, queries and
  export orchestration. `export_estimate()` retains the existing API contract and
  exclusive-create behaviour. It is not exposed as an agent tool.
- `tender_assistant/cli/export_api_response.py`: argument parsing and presentation;
  delegates export work to the service. Existing arguments are unchanged.
- `tender_assistant/cli/query_estimate.py`: deterministic offline queries.
- `tender_assistant/hosting/estimate_tools.py`: typed tool adapters and shared
  agent factory. The framework executes model-requested functions.
- `tender_assistant/cli/chat.py`: local conversational entry point.
- `main.py`: hosted server uses the same agent factory. The exact
  `GET_INDICATIVE_VALUE_JSON` command remains supported without model selection.

Tools available to the model:

| Tool | Result |
| --- | --- |
| `list_tenders()` | Configured tender IDs, names and revisions |
| `get_estimate(tender_id)` | Saved subtotal, trade subtotals, scope and warnings |
| `get_item_details(tender_id, row)` | Priced evidence or unpriced reasons for an Excel row |
| `list_unpriced_items(tender_id)` | All unpriced items in the saved selection, with reasons; excludes unprocessed source rows |

Run the following commands from `src/agent-framework-agent-basic-responses`.

## 1. Offline: no Azure and no model tokens

```bash
.venv/bin/python -m tender_assistant.cli.query_estimate
.venv/bin/python -m tender_assistant.cli.query_estimate --tender-id hopuhopu-2027-rev-0a
.venv/bin/python -m tender_assistant.cli.query_estimate --tender-id hopuhopu-2027-rev-0a --row 16
.venv/bin/python -m unittest discover -s tests -v
```

Use repeated `--response /path/to/export.json` arguments to explicitly load
multiple exports. Duplicate tender IDs fail at startup rather than silently
choosing a revision. Query outputs are copies of a startup snapshot; restart
after changing exported files. Missing rows mean absent from the saved selection,
not zero cost or proof that the tender has no such row.

## 2. Local conversation: calls the configured Azure model

Configure `FOUNDRY_PROJECT_ENDPOINT` and `AZURE_AI_MODEL_DEPLOYMENT_NAME`
(or the existing `FOUNDRY_MODEL_NAME` fallback) in the service `.env` or process
environment. Existing process variables take precedence. Authenticate locally
using your authorised Azure identity. Never commit `.env` or tokens.

```bash
.venv/bin/python -m tender_assistant.cli.chat --trace-tools --message "List the saved tenders, then give the indicative value for Hopuhopu."
.venv/bin/python -m tender_assistant.cli.chat --trace-tools
```

The second command retains conversation context until `exit` or `quit`.
Ask: `Why is Excel row 16 unpriced for Hopuhopu?`
`--trace-tools` prints function names only, not full evidence payloads.
The chat command supports repeated `--response` paths. Without them it uses
`TENDER_API_RESPONSE_PATH` or the existing Hopuhopu export default. The hosted
entry point currently loads that one configured export.

Expected answers preserve currency, exact amount, selected-items-only scope
and pending review. No historical matching should run. Tool results sent to the
model include saved business information; use only an approved model endpoint.

## Verification and limits

Tests cover offline CLI, unchanged export contract/no overwrite, unknown IDs,
invalid rows, unchanged files, evidence preservation, real SDK tool invocation
and a scripted model tool-call/result round trip. The scripted client makes no
network calls and does not prove real model routing or answer quality.

Exports are trusted local application artifacts with basic envelope validation,
not a new cryptographic re-audit of the original source files. Build exports via
the existing validated batch export path. The service does not recalculate prices.
Configured files form a local allowlist; **this is not per-user authorization**.
Before shared hosting, add caller/project permissions, managed storage and real
model/streaming integration checks. Model text remains subject to review.
