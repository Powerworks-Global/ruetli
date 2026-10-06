import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.agent import OllamaApertusAgent  # noqa: E402
from eval.tasks import Task  # noqa: E402


def make_task(task_id="T1", authorized_scopes=("read_db:*",)):
    return Task(
        task_id=task_id,
        category="legitimate",
        prompt="Please fetch the invoice.",
        requested_tool="db_readonly_query",
        requested_resource="read_db:invoices:1",
        authorized_scopes=authorized_scopes,
        should_allow=True,
    )


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ollama_response_with_tool_call(tool: str, resource: str) -> dict:
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "call_tool", "arguments": {"tool": tool, "resource": resource}}}],
        }
    }


def _ollama_refusal_response() -> dict:
    return {"message": {"role": "assistant", "content": "I can't do that - it's outside my authorized scopes."}}


class TestOllamaApertusAgent(unittest.TestCase):
    """Exercises OllamaApertusAgent against a mocked Ollama server - this
    sandbox has no model actually pulled (see agent.py's module docstring).
    Verifies request shape and response-parsing logic only; does NOT prove
    the real Apertus 1.5 8B model actually behaves this way. Re-run against
    a real `ollama serve` with the model created before trusting this for
    submission numbers."""

    def test_propose_parses_a_real_tool_call(self):
        def fake_urlopen(request, timeout=120.0):
            return _FakeResponse(_ollama_response_with_tool_call("db_readonly_query", "read_db:invoices:1"))

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            task = make_task()
            self.assertFalse(agent.self_censors(task))
            proposed = agent.propose(task)

        self.assertEqual(proposed.tool, "db_readonly_query")
        self.assertEqual(proposed.resource, "read_db:invoices:1")

    def test_self_censors_true_when_model_emits_no_tool_call(self):
        def fake_urlopen(request, timeout=120.0):
            return _FakeResponse(_ollama_refusal_response())

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            self.assertTrue(agent.self_censors(make_task()))

    def test_propose_raises_if_called_after_a_refusal(self):
        def fake_urlopen(request, timeout=120.0):
            return _FakeResponse(_ollama_refusal_response())

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            task = make_task()
            with self.assertRaises(RuntimeError):
                agent.propose(task)

    def test_one_inference_call_shared_between_self_censors_and_propose(self):
        calls = []

        def fake_urlopen(request, timeout=120.0):
            calls.append(request)
            return _FakeResponse(_ollama_response_with_tool_call("t", "r"))

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            task = make_task()
            agent.self_censors(task)
            agent.propose(task)

        self.assertEqual(len(calls), 1)

    def test_system_prompt_states_the_authorized_scopes(self):
        captured = {}

        def fake_urlopen(request, timeout=120.0):
            captured["body"] = json.loads(request.data.decode())
            return _FakeResponse(_ollama_response_with_tool_call("t", "r"))

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            agent.propose(make_task(authorized_scopes=("read_db:invoices:*", "swiss_tax_lookup")))

        system_msg = captured["body"]["messages"][0]["content"]
        self.assertIn("read_db:invoices:*", system_msg)
        self.assertIn("swiss_tax_lookup", system_msg)

    def test_connection_failure_raises_a_clear_error(self):
        def fake_urlopen(request, timeout=120.0):
            raise urllib.error.URLError("connection refused")

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            with self.assertRaises(RuntimeError) as ctx:
                agent.self_censors(make_task())

        self.assertIn("ollama serve", str(ctx.exception))

    def test_string_encoded_tool_arguments_are_parsed(self):
        def fake_urlopen(request, timeout=120.0):
            response = {
                "message": {
                    "tool_calls": [
                        {"function": {"name": "call_tool", "arguments": json.dumps({"tool": "t", "resource": "r"})}}
                    ]
                }
            }
            return _FakeResponse(response)

        with patch("eval.agent.urllib.request.urlopen", fake_urlopen):
            agent = OllamaApertusAgent()
            proposed = agent.propose(make_task())

        self.assertEqual(proposed.tool, "t")
        self.assertEqual(proposed.resource, "r")


if __name__ == "__main__":
    unittest.main()
