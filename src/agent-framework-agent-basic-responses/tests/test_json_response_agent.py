import asyncio
import json
import unittest

from agent_framework import AgentResponse, AgentSession, Message

from tender_assistant.hosting.json_response_agent import JSON_COMMAND, JsonResponseAgent


class FakeChatAgent:
    id = "chat-agent"
    name = "chat"
    description = "test"
    context_providers = []

    def create_session(self, *, session_id=None):
        return AgentSession(session_id=session_id)

    def get_session(self, service_session_id, *, session_id=None):
        return AgentSession(service_session_id=service_session_id, session_id=session_id)

    def run(self, messages=None, *, stream=False, session=None, **kwargs):
        return ("delegated", messages, stream)


class JsonResponseAgentTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "schema_version": "1.0",
            "status": "completed_with_unpriced_items",
            "currency": "NZD",
            "indicative_value": {"amount": "25.00"},
            "audit": {"replayable": True},
        }
        self.agent = JsonResponseAgent(FakeChatAgent(), self.payload)

    def test_exact_command_returns_deterministic_json(self):
        response = asyncio.run(self.agent.run(JSON_COMMAND))
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(json.loads(response.text), self.payload)
        self.assertNotIn("\n", response.text)

    def test_message_input_is_supported(self):
        response = asyncio.run(self.agent.run([Message("user", [JSON_COMMAND])]))
        self.assertEqual(json.loads(response.text), self.payload)

    def test_streaming_returns_one_json_update(self):
        async def collect():
            return [update async for update in self.agent.run(JSON_COMMAND, stream=True)]

        updates = asyncio.run(collect())
        self.assertEqual(len(updates), 1)
        self.assertEqual(json.loads(updates[0].text), self.payload)

    def test_normal_chat_is_delegated(self):
        self.assertEqual(self.agent.run("Hello", stream=True), ("delegated", "Hello", True))


if __name__ == "__main__":
    unittest.main()
