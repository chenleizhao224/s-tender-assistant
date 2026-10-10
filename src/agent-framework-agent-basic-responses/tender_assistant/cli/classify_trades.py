"""Preview, classify or replay schedule trades; model access requires --run."""
import argparse
import asyncio
import json
import os
from pathlib import Path

from tender_assistant.paths import SERVICE_ROOT
from tender_assistant.schedules.extraction import extract_schedule
from tender_assistant.schedules.preparation import prepare_schedule
from tender_assistant.schedules.trades import (
    INSTRUCTIONS, build_request, load_classification, save_classification, checked_evidence,
)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", type=Path)
    parser.add_argument("--rows", nargs="+", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path, help="Existing selected-excerpt package; not automatic document retrieval.")
    parser.add_argument("--source-root", type=Path, help="Tender folder used to verify evidence fingerprints.")
    parser.add_argument("--run", action="store_true", help="Call GPT-luna; default is a free local preview.")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        if args.schedule or args.rows or args.output or args.run or args.evidence or args.source_root:
            parser.error("Replay cannot be combined with other options.")
        payload = load_classification(args.replay)
        print(json.dumps(payload["result"], indent=2, ensure_ascii=False))
        return
    if not args.schedule:
        parser.error("--schedule is required.")
    if args.rows and len(args.rows) != len(set(args.rows)):
        parser.error("Duplicate rows are not allowed.")
    if bool(args.evidence) != bool(args.source_root):
        parser.error("Use --evidence and --source-root together.")
    evidence = checked_evidence(args.evidence, args.source_root) if args.evidence else None
    request = build_request(prepare_schedule(extract_schedule(args.schedule)), args.rows, evidence)
    print("Work items:", len(request["items"]))
    print("External evidence excerpts:", len(evidence or {}), "(only explicit excerpts, not a complete document review)")
    if not args.run:
        for target in request["items"]:
            print(target["item_id"], target["item"]["category"], target["item"]["description"])
        print("Preview only: no model called. Add --run --output NEW_PATH to classify.")
        return
    if not args.output or args.output.exists():
        parser.error("--run requires a new --output path.")
    prompt = json.dumps(request, ensure_ascii=False)
    if len(prompt) > 180000 or len(request["items"]) > 30:
        parser.error("Select at most 30 rows per model request; context limit is 180000 characters.")
    from dotenv import load_dotenv
    from azure.identity import DefaultAzureCredential
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from pydantic import BaseModel, ConfigDict
    class Decision(BaseModel):
        model_config = ConfigDict(extra="forbid")
        item_id: str
        status: str
        trade: str | None
        reason: str
        assumptions: list[str]
        source_ids: list[str]
    class Classification(BaseModel):
        model_config = ConfigDict(extra="forbid")
        decisions: list[Decision]
    load_dotenv(SERVICE_ROOT / ".env")
    model = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    with DefaultAzureCredential() as credential:
        async with Agent(client=FoundryChatClient(project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], model=model, credential=credential), instructions=INSTRUCTIONS, default_options={"store": False, "response_format": Classification}) as agent:
            response = await agent.run(prompt)
    save_classification(args.output, request, json.loads(response.text), model)
    print("Saved classification:", args.output)


if __name__ == "__main__":
    asyncio.run(main())
