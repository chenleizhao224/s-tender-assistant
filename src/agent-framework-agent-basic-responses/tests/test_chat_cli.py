import argparse
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from tender_assistant.cli.chat import chat


class ChatStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_shot_client_without_async_context_manager(self):
        # A plain object deliberately has no __aenter__/__aexit__.
        client = object()
        agent = MagicMock()
        agent.run = AsyncMock(return_value=SimpleNamespace(
            text="Saved estimate", messages=[SimpleNamespace(contents=[
                SimpleNamespace(type="function_call", name="get_estimate")])]))
        args = argparse.Namespace(response=[], message="Show estimate", trace_tools=True)
        with (
            patch.dict("os.environ", {"FOUNDRY_PROJECT_ENDPOINT": "https://example.invalid", "AZURE_AI_MODEL_DEPLOYMENT_NAME": "test"}),
            patch("dotenv.load_dotenv"),
            patch("tender_assistant.cli.chat.EstimateService"),
            patch("azure.identity.DefaultAzureCredential"),
            patch("agent_framework.foundry.FoundryChatClient", return_value=client) as factory,
            patch("tender_assistant.hosting.estimate_tools.create_chat_agent", return_value=agent) as create,
            redirect_stdout(io.StringIO()) as output,
        ):
            await chat(args)
        factory.assert_called_once()
        self.assertIs(create.call_args.args[0], client)
        agent.run.assert_awaited_once_with("Show estimate", session=agent.create_session.return_value)
        self.assertIn("Tool called: get_estimate", output.getvalue())
        self.assertIn("Saved estimate", output.getvalue())
