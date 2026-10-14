"""Render an English demo report from saved estimates, without model calls."""

import argparse
import json
import re
from decimal import Decimal
from html import escape
from pathlib import Path

from tender_assistant.pricing.summary import summarize
from tender_assistant.pricing.snapshot import content_hash, load_snapshot, recalculate
from tender_assistant.pricing.summary import sum_exact


def text(value):
    return escape(str(value))


def number(value):
    return "Unpriced" if value is None else format(Decimal(value), ",f")


def bullets(values):
    return "<ul>" + "".join(f"<li>{text(value)}</li>" for value in values) + "</ul>"


def unpriced_explanation(entry):
    recommendation = entry.get("recommendation") or {}
    reason = recommendation.get("reason") or entry.get("reason") or "No pricing reason was recorded. Review required."
    result = f'<p>{text(reason)}</p>'
    if entry.get("classification"):
        result += '<p><strong>Trade allocation:</strong> ' + text(entry["classification"]["reason"]) + '</p>'
    if recommendation.get("differences"):
        result += bullets(recommendation["differences"])
    result += '<p>Excluded from the subtotal; not zero cost. No candidates under a filter does not prove that the entire historical library has no suitable rate.</p>'
    return result


def expandable_reason(label, content):
    return f'<details class="pricing-reason"><summary>{text(label)}</summary><div>{content}</div></details>'


def render_report(batch, title, summary=None):
    narrative = ''
    if summary:
        from tender_assistant.text.summary import validate_summary
        validate_summary(summary['summary'], summary['sources'])
        if batch['source_sha256'] not in {s['source_sha256'] for s in summary['coverage']}:
            raise ValueError('Summary and pricing must use the same schedule version')
        for section in summary['summary']['sections']:
            narrative += f'<h2>{text(section["title"])}</h2>'
            for item in section['items']:
                display_text = re.sub(r'\s*\[S\d{4}(?:,\s*S\d{4})*\]', '', item['text'])
                narrative += f'<p>{text(display_text)}</p>'
                for sid in item['source_ids']:
                    source = summary['sources'][sid]
                    narrative += f'<details><summary class="meta">Source: {text(source["source_file"])} · {text(source["locator"])}</summary><blockquote>{text(source["text"])}</blockquote></details>'
        narrative += '<h2>Document coverage</h2><p>Partial-document summary. Drawings, geotechnical reports and the full tender package have not been reviewed. Source references are validated; model interpretation still requires review. Programme dates come from the supplied preliminary document and have not been checked against later notices. Narrative quantities describe broader project scope and are not substituted for the selected schedule quantities used below.</p>'
        for source in summary['coverage']:
            narrative += f'<details><summary>{text(source["source_file"])} · {text(source["status"])}</summary>{bullets(source["warnings"])}</details>'
    calculated = summarize(batch["entries"])
    for field in ("requested_rows", "priced_rows", "unpriced_rows", "failed_rows", "indicative_subtotal"):
        if calculated[field] != batch[field]:
            raise ValueError(f"Batch {field} does not match its entries.")
    table = []
    details = []
    proxy_notes = []
    trade_amounts = {}
    for entry in batch["entries"]:
        snapshot = None
        row = entry["excel_row"]
        if entry["state"] not in {"priced", "unpriced", "failed"}:
            raise ValueError("Unknown row state.")
        if entry["state"] != "priced" and entry["amount"] is not None:
            raise ValueError("Unpriced or failed row contains an amount.")
        if entry.get("snapshot_sha256"):
            snapshot = load_snapshot(entry["snapshot_file"])
            if content_hash(snapshot) != entry["snapshot_sha256"]:
                raise ValueError(f"Row {row}: selected snapshot has changed.")
            if snapshot["item"]["excel_row"] != row or snapshot["item"]["source_sha256"] != batch["source_sha256"]:
                raise ValueError(f"Row {row}: source mismatch.")
            if recalculate(snapshot) != entry["amount"]:
                raise ValueError(f"Row {row}: amount mismatch.")
            for field in ("recommendation", "selected_rate"):
                if snapshot[field] != entry[field]:
                    raise ValueError(f"Row {row}: {field} mismatch.")
            for field, source_field in (("quantity", "quantity_resolved"), ("unit", "unit"), ("description", "description")):
                if entry[field] != snapshot["item"][source_field]:
                    raise ValueError(f"Row {row}: {field} mismatch.")
        elif entry["state"] == "priced":
            raise ValueError("Priced rows require a versioned snapshot; regenerate this batch.")

        rate = entry.get("selected_rate") or {}
        recommendation = entry.get("recommendation") or {}
        basis = recommendation.get("match_basis") or entry["state"]
        if basis == 'comparable' and entry['amount'] is not None:
            proxy_notes.append(f'Row {row}: {entry.get("description", "")} — historical proxy: {rate.get("description", "")}. ' + ' '.join(recommendation.get('differences', [])[:2]))
        item = snapshot['item'] if snapshot else {}
        trade = snapshot['context'].get('trade_filter', 'Unclassified') if snapshot else entry.get('allocated_trade', 'Unclassified')
        if entry['amount'] is not None:
            trade_amounts.setdefault(trade, []).append(Decimal(entry['amount']))
        calculation = f'{number(entry.get("quantity"))} × {number(rate.get("rate"))}' if entry['amount'] is not None else 'Not calculated'
        unpriced = expandable_reason('Unpriced', unpriced_explanation(entry))
        table.append(
            f'<tr><td>{text(trade)}</td><td>{text(item.get("code", entry.get("code", "—")))}<br><a href="#row-{row}">Excel row {row}</a></td>'
            f'<td>{text(entry.get("description", "Unavailable"))}</td>'
            f'<td class="numeric">{number(entry["quantity"]) if entry.get("quantity") is not None else "Not specified"}</td>'
            f'<td>{text(entry.get("unit", "—"))}</td>'
            f'<td class="numeric">{number(rate["rate"]) if rate.get("rate") is not None else unpriced}</td>'
            f'<td class="numeric">{calculation}</td>'
            f'<td class="numeric">{number(entry["amount"]) if entry["amount"] is not None else unpriced}</td>'
            f'<td>{text(rate.get("project", "—"))}<br>{unpriced if basis == "unpriced" else text(basis.replace("_", " "))}</td></tr>'
        )
        detail = f'<section id="row-{row}"><h3>Row {row} · {text(entry.get("description", "Unavailable"))}</h3>'
        detail += f'<p>{text(recommendation.get("reason", entry.get("reason", "No recommendation recorded.")))}</p>'
        if entry.get('classification'):
            detail += '<p><strong>Trade allocation:</strong> ' + text(entry['classification']['reason']) + '</p>'
        if rate:
            detail += f'<p><strong>Historical basis:</strong> {text(rate["description"])} · {text(rate["project"])}</p>'
        detail += '<h4>Estimating assumptions</h4>' + bullets(recommendation.get("assumptions", []))
        detail += '<h4>Risks and differences</h4>' + bullets(recommendation.get("differences", []))
        detail += f'<p class="meta">Saved selection: {text(Path(entry["snapshot_file"]).name)}<br>Snapshot fingerprint: {text(entry.get("snapshot_sha256", "Not available"))}<br>Evidence supplied: {"Yes" if entry.get("evidence_sha256") else "Schedule row only"}</p>'
        if entry.get("library_changed_since_selection"):
            detail += '<p>Historical library changed since this selection; the saved rate was retained.</p>'
        details.append(detail + '</section>')

    trade_table = ''.join(f'<tr><td>{text(trade)}</td><td>{len(amounts)}</td><td class="numeric">{number(str(sum_exact(amounts)))}</td></tr>' for trade, amounts in sorted(trade_amounts.items()))
    breakdown = f'''<h2>Indicative calculation breakdown</h2><p>Item value = schedule quantity × selected historical unit rate. Trade allocation uses the saved estimating trade, not the historical project's name. Item codes are preserved as extracted from the schedule.</p><div class="table-wrap"><table><thead><tr><th>Allocated trade</th><th>Schedule item / source row</th><th>Description</th><th>Quantity</th><th>Unit</th><th>Unit rate</th><th>Calculation</th><th>Amount</th><th>Historical project / basis</th></tr></thead><tbody>{''.join(table)}</tbody><tfoot><tr><th colspan="7">Selected-item subtotal</th><th class="numeric">{number(batch['indicative_subtotal'])}</th><td>Pending review</td></tr></tfoot></table></div>
<h3>Allocation by trade</h3><table><thead><tr><th>Trade</th><th>Priced items</th><th>Indicative subtotal</th></tr></thead><tbody>{trade_table}</tbody></table><p class="meta">Only selected priced items are included. Other trades and unassessed items are not valued at zero. Source worksheet: Civil  SoP - Breakdown; schedule revision 0A for this demo.</p>'''

    coverage = ''
    if batch.get('classification_coverage'):
        from tender_assistant.schedules.trades import TRADES
        decisions = batch['classification_coverage']['decisions']
        coverage_rows = []
        for trade in (*TRADES, 'Requires review'):
            count = sum((d['trade'] or 'Requires review') == trade for d in decisions)
            selected = [e for e in batch['entries'] if e.get('allocated_trade') == trade]
            priced = sum(e['state'] == 'priced' for e in selected)
            amounts = trade_amounts.get(trade, [])
            reasons = ''.join(f'<h4>Excel row {e["excel_row"]} · {text(e.get("description", ""))}</h4>' + unpriced_explanation(e) for e in selected)
            if not selected:
                reasons = '<p>No items from this trade were selected for this demo. Historical rate matching has not been attempted for this selection.</p>'
            subtotal = number(str(sum_exact(amounts))) if amounts else expandable_reason('Not estimated', reasons)
            coverage_rows.append(f'<tr><td>{text(trade)}</td><td>{count}</td><td>{len(selected)}</td><td>{priced}</td><td class="numeric">{subtotal}</td></tr>')
        count = batch['classification_coverage']['work_item_count']
        coverage = f'<h2>Trade coverage</h2><p>All {count} work rows have been considered for draft trade classification. Valuation covers the representative selection below. Classification uses schedule context; detailed trade boundaries remain subject to review.</p><table><thead><tr><th>Trade</th><th>Classified rows</th><th>Selected for demo</th><th>Priced</th><th>Selected subtotal</th></tr></thead><tbody>' + ''.join(coverage_rows) + '</tbody></table>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{text(title)}</title><style>
body{{font:16px/1.55 system-ui,sans-serif;color:#20313e;background:#f2f5f6;margin:0}}
main{{max-width:1180px;margin:32px auto;background:white;padding:44px;border-radius:12px}}
h1{{font-size:32px;margin:8px 0}}h2{{margin-top:36px}}h3{{font-size:19px}}h4{{margin-bottom:6px}}
.eyebrow,.meta{{color:#62717b;font-size:13px}}.meta{{overflow-wrap:anywhere}}
.amount{{font-size:38px;font-weight:700;color:#006f68;margin:10px 0}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{padding:12px 10px;border-bottom:1px solid #dce3e7;text-align:left;vertical-align:top}}
th{{background:#edf4f3}}.numeric{{text-align:right;white-space:nowrap}}a{{color:#006f68}}
.pricing-reason summary{{cursor:pointer;color:#006f68;text-decoration:underline;text-underline-offset:3px}}
.pricing-reason summary:focus-visible{{outline:2px solid #006f68;outline-offset:3px}}
.pricing-reason div{{white-space:normal;text-align:left;min-width:220px;max-width:520px;font-size:13px;background:#f2f7f6;padding:12px;margin-top:8px;overflow-wrap:anywhere}}
section{{border-top:1px solid #dce3e7;padding:20px 0}}li{{margin:5px 0}}
@media(max-width:700px){{main{{margin:0;padding:20px}}h1{{font-size:26px}}}}
@media print{{body{{background:white}}main{{margin:0;padding:0}}section{{break-inside:avoid}}button{{display:none}}}}
</style></head><body><main>
<div class="eyebrow">SCHICK · TENDER ASSISTANT DEMO · PENDING REVIEW</div>
<h1>{text(title)}</h1>
<button onclick="window.print()">Print / Save PDF</button>
<p>Hopuhopu Development Te Matatini 2027 — draft tender briefing and indicative valuation.</p>
<p>This report assists the estimator in completing the Tender Management Report. It combines a concise document briefing with Python-calculated indicative values; it is not a completed Tender Management Report, final quotation or bid decision.</p>
<h2>Indicative value — selected work items</h2>
<div class="amount">{number(batch["indicative_subtotal"])}</div>
<p><strong>Indicative subtotal for selected rows only.</strong> Amounts use the supplied historical rate basis; no tax, escalation or contingency adjustment has been applied by this report.</p>
<p>{batch["priced_rows"]} priced rows · {batch["unpriced_rows"]} unpriced rows · {batch["failed_rows"]} failed rows. This is not the full tender value.</p>
{'<h3>Key proxy assumptions affecting the subtotal</h3>' + bullets(proxy_notes) if proxy_notes else ''}
<p class="meta">Model explanations are draft interpretation. Similar project names do not establish that a historical job is the same contract. Refer to the source descriptions and review notes.</p>
{coverage}
{breakdown}
{narrative}
<h2>Scope summary</h2>
<p>This pricing batch covers only the work descriptions listed below. Historical rates were recommended by GPT-luna; quantities, multiplication and the subtotal are calculated in Python. Item-level matching notes reuse saved recommendations.</p>
<p>Demo assumptions: Dayworks and provisional quantities, where selected, retain the schedule quantities for illustration. Separate commercial treatment, percentage bases, lump-sum rules and unit aliases are deferred. The subtotal is a demo selection, not a forecast of actual expenditure.</p>
<p>Rates remain indicative. Known differences and assumptions accompany each item; unpriced items are excluded from the subtotal and are not treated as zero.</p>
<h2>Matching rationale and risk notes</h2>{''.join(details)}
<h2>Source and calculation record</h2>
<p class="meta">Batch created: {text(batch["created_at"])}<br>Schedule fingerprint: {text(batch["source_sha256"])}<br>Rows: {text(', '.join(map(str, batch["requested_rows"])))}</p>
<p>Values are displayed without monetary rounding. Regeneration uses saved matching decisions and makes no model calls.</p>
<h2>Follow-up items</h2>
<ul><li>Confirm drawing and geotechnical requirements where needed for formal pricing.</li><li>Review historical rate inclusions, transport, disposal, material and testing assumptions.</li><li>Extend coverage to remaining tender items and the full document package.</li></ul>
</main></body></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="Tender Intelligence Demo")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    with args.batch.open(encoding="utf-8") as stream:
        batch = json.load(stream)
    from tender_assistant.text.summary import load_summary
    summary = load_summary(args.summary) if args.summary else None
    html = render_report(batch, args.title, summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(html)
    print("Report saved:", args.output.resolve())


if __name__ == "__main__":
    main()
