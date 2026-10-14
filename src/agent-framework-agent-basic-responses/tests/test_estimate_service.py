import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tender_assistant.api import build_tender_response
from tender_assistant.services.estimates import EstimateService, export_estimate
from tests.test_api_response import sample_batch


class EstimateServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "response.json"
        self.payload = build_tender_response(sample_batch(), tender_id="demo-0a",
            tender_name="Demo", schedule_revision="0A", verify_snapshots=False)
        self.path.write_text(json.dumps(self.payload), encoding="utf-8")
        self.service = EstimateService([self.path])

    def test_summary_preserves_amount_scope_and_warnings(self):
        result = self.service.get_estimate("demo-0a")
        self.assertEqual(result["indicative_value"]["amount"], "25.00")
        self.assertFalse(result["indicative_value"]["is_full_tender_value"])
        self.assertEqual(result["indicative_value"]["review_status"], "pending_review")
        self.assertEqual(result["warnings"], self.payload["warnings"])
        self.assertNotIn("audit", result)  # No internal audit/file details in summary.

    def test_priced_and_unpriced_evidence(self):
        priced = self.service.get_item_details("demo-0a", 10)
        self.assertEqual(priced["item"]["historical_rate"], "10.00")
        self.assertEqual(priced["item"]["assumptions"], ["Comparable ground conditions."])
        unpriced = self.service.get_item_details("demo-0a", 11)
        self.assertTrue(unpriced["item"]["not_zero_cost"])
        self.assertEqual(unpriced["item"]["reason_code"], "PRICING_RULE_NOT_IMPLEMENTED")

    def test_unknown_ids_are_not_paths_and_missing_rows_are_not_zero(self):
        for value in ("unknown", "../../etc/passwd", str(self.path)):
            self.assertEqual(self.service.get_estimate(value)["status"], "not_found")
        self.assertEqual(self.service.get_item_details("demo-0a", 999)["status"], "not_found")
        for row in (0, -1, True, "10"):
            self.assertEqual(self.service.get_item_details("demo-0a", row)["status"], "invalid_argument")

    def test_copies_do_not_change_saved_results(self):
        before = self.path.read_bytes()
        self.service.get_estimate("demo-0a")["indicative_value"]["amount"] = "0"
        self.service.list_tenders()["tenders"][0]["name"] = "changed"
        self.assertEqual(self.service.get_estimate("demo-0a")["indicative_value"]["amount"], "25.00")
        self.assertEqual(self.path.read_bytes(), before)

    def test_bad_exports_fail_at_startup(self):
        with self.assertRaises(ValueError):
            EstimateService([self.path, self.path])
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaises(ValueError):
            EstimateService([self.path])

    def test_export_service_preserves_contract_and_no_overwrite(self):
        batch_path = self.path.with_name("batch.json")
        output = self.path.with_name("export.json")
        batch_path.write_text(json.dumps(sample_batch()), encoding="utf-8")
        metadata = dict(tender_id="demo-0a", tender_name="Demo", schedule_revision="0A", verify_snapshots=False)
        self.assertEqual(export_estimate(batch_path, output, **metadata), self.payload)
        with self.assertRaises(FileExistsError):
            export_estimate(batch_path, output, **metadata)

    def test_cli_works_without_sdk_or_azure(self):
        result = subprocess.run([sys.executable, "-S", "-m", "tender_assistant.cli.query_estimate",
            "--response", str(self.path), "--tender-id", "demo-0a"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["indicative_value"]["amount"], "25.00")

    def test_sdk_tools_invoke_real_service(self):
        from tender_assistant.hosting.estimate_tools import create_estimate_tools
        tools = {tool.name: tool for tool in create_estimate_tools(self.service)}
        self.assertEqual(set(tools), {"list_tenders", "get_estimate", "get_item_details", "list_unpriced_items"})
        result = asyncio.run(tools["get_estimate"].invoke(arguments={"tender_id": "demo-0a"}, skip_parsing=True))
        self.assertEqual(result, self.service.get_estimate("demo-0a"))
        item = asyncio.run(tools["get_item_details"].invoke(arguments={"tender_id": "demo-0a", "row": 11}, skip_parsing=True))
        self.assertTrue(item["item"]["not_zero_cost"])
        listed = asyncio.run(tools["list_tenders"].invoke(arguments={}, skip_parsing=True))
        self.assertEqual(listed["tenders"][0]["id"], "demo-0a")

    def test_unpriced_tool_preserves_evidence_and_saved_scope(self):
        from tender_assistant.hosting.estimate_tools import create_estimate_tools
        tools = {tool.name: tool for tool in create_estimate_tools(self.service)}
        before = self.path.read_bytes()
        result = asyncio.run(tools["list_unpriced_items"].invoke(
            arguments={"tender_id": "demo-0a"}, skip_parsing=True))
        self.assertEqual(result["items"], self.payload["unpriced_items"])
        self.assertEqual(result["count"], len(self.payload["unpriced_items"]))
        self.assertEqual(result["scope"], "saved_selection_only")
        self.assertEqual(result["review_status"], "pending_review")
        result["items"].clear()
        self.assertEqual(self.service.list_unpriced_items("demo-0a")["items"], self.payload["unpriced_items"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_unpriced_unknown_and_empty_results(self):
        self.assertEqual(self.service.list_unpriced_items("unknown")["status"], "not_found")
        self.payload["unpriced_items"] = []
        self.path.write_text(json.dumps(self.payload), encoding="utf-8")
        result = EstimateService([self.path]).list_unpriced_items("demo-0a")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["items"], [])
        self.assertIn("does not prove", result["warnings"][-1])

    def test_framework_executes_model_requested_tool_and_returns_result(self):
        from agent_framework import BaseChatClient, ChatResponse, Content, Message
        from agent_framework._tools import FunctionInvocationLayer
        from tender_assistant.hosting.estimate_tools import create_chat_agent

        class ScriptedClient(FunctionInvocationLayer, BaseChatClient):
            async def _inner_get_response(self, *, messages, stream, options, **kwargs):
                results = [c for m in messages for c in m.contents if c.type == "function_result"]
                if results:
                    self.tool_result = results[-1].result
                    return ChatResponse(messages=[Message("assistant", ["Saved estimate retrieved."])])
                return ChatResponse(messages=[Message("assistant", [Content.from_function_call(
                    "call-1", "get_estimate", arguments={"tender_id": "demo-0a"})])])

        client = ScriptedClient()
        response = asyncio.run(create_chat_agent(client, self.service).run("What is the estimate?"))
        self.assertEqual(response.text, "Saved estimate retrieved.")
        self.assertIn("25.00", str(client.tool_result))


if __name__ == "__main__":
    unittest.main()
