# Copyright (c) Microsoft. All rights reserved.

import os
from pathlib import Path

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from tender_assistant.hosting import JsonResponseAgent
from tender_assistant.hosting.json_response_agent import load_api_response

# Load environment variables from .env file
load_dotenv()


def main():
    model_name = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL_NAME")
    if not model_name:
        raise RuntimeError(
            "Model deployment name is not configured. Set "
            "AZURE_AI_MODEL_DEPLOYMENT_NAME or FOUNDRY_MODEL_NAME."
        )

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=model_name,
        credential=DefaultAzureCredential(),
    )

    chat_agent = Agent(
        client=client,
        name="tender-assistant",
        description="Draft tender intelligence and indicative-value assistant.",
        instructions=(
            "You are the Schick Tender Assistant. Explain tender findings, assumptions, "
            "risks and indicative values clearly. Never describe an indicative subtotal "
            "as the full tender value. Keep answers concise and preserve estimator review."
        ),
        # History will be managed by the hosting infrastructure, thus there
        # is no need to store history by the service. Learn more at:
        # https://developers.openai.com/api/reference/resources/responses/methods/create
        default_options={"store": False},
    )

    response_path = Path(
        os.getenv(
            "TENDER_API_RESPONSE_PATH",
            Path(__file__).parent / "outputs" / "api" / "hopuhopu-2027-rev-0a.json",
        )
    )
    agent = JsonResponseAgent(chat_agent, load_api_response(response_path))

    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
