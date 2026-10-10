"""Route one exact machine command to a deterministic saved JSON response."""

import json
from pathlib import Path

from agent_framework import AgentResponse, AgentResponseUpdate, Content, Message


JSON_COMMAND = "GET_INDICATIVE_VALUE_JSON"


def load_api_response(path):
    with Path(path).open(encoding="utf-8") as stream:
        response = json.load(stream)
    required = {"schema_version", "status", "currency", "indicative_value", "audit"}
    missing = required - response.keys()
    if missing:
        raise ValueError(f"API response is missing required fields: {sorted(missing)}")
    return response


def _last_text(messages):
    if isinstance(messages, str):
        return messages.strip()
    if messages is None:
        return ""
    if not isinstance(messages, (list, tuple)):
        messages = [messages]
    for message in reversed(messages):
        value = getattr(message, "text", None)
        if value:
            return value.strip()
        if isinstance(message, str):
            return message.strip()
    return ""


class JsonResponseAgent:
    """Preserve normal chat while exposing a deterministic JSON command."""

    def __init__(self, chat_agent, api_response):
        self._chat_agent = chat_agent
        self._payload = json.dumps(api_response, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        self.id = chat_agent.id
        self.name = chat_agent.name
        self.description = chat_agent.description
        self.context_providers = chat_agent.context_providers
        self.require_per_service_call_history_persistence = getattr(
            chat_agent, "require_per_service_call_history_persistence", False
        )

    def create_session(self, *, session_id=None):
        return self._chat_agent.create_session(session_id=session_id)

    def get_session(self, service_session_id, *, session_id=None):
        return self._chat_agent.get_session(service_session_id, session_id=session_id)

    def run(self, messages=None, *, stream=False, session=None, **kwargs):
        if _last_text(messages) != JSON_COMMAND:
            return self._chat_agent.run(messages, stream=stream, session=session, **kwargs)
        if stream:
            async def updates():
                yield AgentResponseUpdate(
                    contents=[Content.from_text(text=self._payload)],
                    role="assistant",
                    agent_id=self.id,
                    finish_reason="stop",
                )

            return updates()

        async def response():
            return AgentResponse(
                messages=Message("assistant", [self._payload]),
                agent_id=self.id,
                finish_reason="stop",
            )

        return response()
