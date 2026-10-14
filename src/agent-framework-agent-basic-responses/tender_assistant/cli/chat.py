"""Local conversational entry point. Tools run locally; model calls use Azure."""
import argparse
import asyncio
import os
from pathlib import Path

from tender_assistant.paths import SERVICE_ROOT
from tender_assistant.services.estimates import EstimateService


async def chat(args):
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential
    from dotenv import load_dotenv
    from tender_assistant.hosting.estimate_tools import create_chat_agent

    load_dotenv(SERVICE_ROOT / ".env")
    model = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL_NAME")
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    if not model or not endpoint:
        raise RuntimeError("Configure FOUNDRY_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME.")
    paths = args.response or [Path(os.getenv("TENDER_API_RESPONSE_PATH", SERVICE_ROOT / "outputs/api/hopuhopu-2027-rev-0a.json"))]
    service = EstimateService(paths)
    with DefaultAzureCredential() as credential:
        # FoundryChatClient is not an asynchronous context manager.
        client = FoundryChatClient(project_endpoint=endpoint, model=model, credential=credential)
        agent = create_chat_agent(client, service)
        session = agent.create_session()
        while True:
            message = args.message or input("You (exit to quit): ").strip()
            if message.lower() in {"exit", "quit"}:
                break
            if not message:
                continue
            response = await agent.run(message, session=session)
            if args.trace_tools:
                for item in response.messages:
                    for content in item.contents:
                        if content.type == "function_call":
                            print(f"Tool called: {content.name}")
            print(response.text)
            if args.message:
                break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", type=Path, action="append")
    parser.add_argument("--message", help="Run one question instead of an interactive conversation.")
    parser.add_argument("--trace-tools", action="store_true", help="Print tool names, not full tool payloads.")
    args = parser.parse_args()
    try:
        asyncio.run(chat(args))
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
