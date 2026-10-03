"""Render only the saved estimator briefing, without pricing or model calls."""
import argparse
import re
from html import escape
from pathlib import Path
from tender_summary import load_summary, BRIEF_SECTIONS

def render_brief(payload):
    if [s['title'] for s in payload['summary']['sections']] != list(BRIEF_SECTIONS):
        raise ValueError('An estimator-brief summary is required')
    citations = {}
    parts = []
    for section in payload['summary']['sections']:
        parts.append(f'<section><h2>{escape(section["title"])}</h2><ul>')
        for item in section['items']:
            links = []
            for sid in item['source_ids']:
                citations.setdefault(sid, len(citations) + 1)
                n = citations[sid]
                links.append(f'<a href="#source-{n}">[{n}]</a>')
            display_text = re.sub(r'\s*\[S\d{4}(?:,\s*S\d{4})*\]', '', item['text'])
            parts.append(f'<li>{escape(display_text)} <span class="refs">{" ".join(links)}</span></li>')
        parts.append('</ul></section>')
    sources = []
    for sid, n in citations.items():
        s = payload['sources'][sid]
        sources.append(f'<details id="source-{n}"><summary>[{n}] {escape(s["source_file"])} · {escape(s["locator"])}</summary><blockquote>{escape(s["text"])}</blockquote></details>')
    coverage = ''.join(f'<li>{escape(s["source_file"])}<ul>'+''.join(f'<li>{escape(w)}</li>' for w in s['warnings'])+'</ul></li>' for s in payload['coverage'])
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tender Intelligence — Estimator Brief</title>
<style>body{font:15px/1.6 system-ui,sans-serif;background:#eef3f3;color:#20313e;margin:0}main{max-width:940px;margin:28px auto;padding:36px;background:white}h1{font-size:30px}h2{font-size:19px;color:#006f68;margin-top:26px}li{margin:8px 0}.meta,.refs{font-size:12px;color:#576b75}a{color:#006f68}details{margin:10px 0;overflow-wrap:anywhere}blockquote{white-space:pre-wrap}button{padding:8px 14px}aside{padding:14px;background:#eef6f5}@media print{button{display:none}body{background:white}main{margin:0;padding:0}h2{break-after:avoid}}@media(max-width:600px){main{margin:0;padding:18px}}</style><main>
<div class="meta">SCHICK · PROTOTYPE · DRAFT FOR ESTIMATOR REVIEW</div><h1>Tender Intelligence — Estimator Brief</h1><button onclick="window.print()">Print / Save PDF</button>
<p>Hopuhopu Development — Civil Works</p><aside>Working notes to assist completion of the Tender Management Report. Not a completed report, final estimate, compliance certification or tender decision. Based on three supplied documents only; confirm current revisions and addenda. Broad earthworks quantities below originate in the preliminary scope description, not a reconciled priced schedule.</aside>
''' + ''.join(parts) + '<h2>Sources and review coverage</h2><p class="meta">References link to saved extracted text. Valid source IDs do not guarantee correct model interpretation. Drawings, geotechnical reports and the full tender package were not reviewed.</p><details><summary>Files reviewed and extraction limitations</summary><ul>'+coverage+'</ul></details>'+''.join(sources)+'</main></html>'

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('summary', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    html = render_brief(load_summary(args.summary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as f:
        f.write(html)
    print('Saved estimator brief:', args.output)
