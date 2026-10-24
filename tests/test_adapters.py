from pathlib import Path
import tempfile
import unittest

from manju.adapters import MockProvider, ProviderRegistry, WorkRequest, adapter_contract, load_config, registry, route_for
from manju.safeio import redact


class AdapterTests(unittest.TestCase):
    def test_every_layer_and_aggregate_conform(self):
        for name in registry().describe():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                self.assertEqual(len(adapter_contract(registry().get(name), directory)), 8)

    def test_third_party_fake_can_register_and_conform(self):
        class Fake(MockProvider):
            pass
        providers = ProviderRegistry()
        providers.register("fake", Fake())
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(len(adapter_contract(providers.get("fake"), directory)), 8)

    def test_capability_limits_and_unknown_provider_fail(self):
        with self.assertRaises(ValueError):
            registry().get("unknown")
        with self.assertRaises(ValueError):
            MockProvider.capabilities.require("video", {"duration_ms": 3600001})
        with self.assertRaises(ValueError):
            MockProvider.capabilities.require("video", {"resolution": "unsupported"})

    def test_per_shot_route_and_fallback_order(self):
        config = load_config()
        config["routes"]["shots"]["S001"] = {"video": [{"provider": "mock-aggregate", "model": "mock-video"}, {"provider": "mock", "model": "mock-video"}]}
        self.assertEqual(route_for(config, "video", "S001")[0]["provider"], "mock-aggregate")
        self.assertEqual(route_for(config, "video", "S002")[0]["provider"], "mock")

    def test_nested_redaction(self):
        self.assertEqual(redact({"headers": {"Authorization": "example"}})["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(redact("Bearer placeholder-value"), "[REDACTED]")

    def test_mock_never_claims_real_model(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            MockProvider().generate(WorkRequest("test", "video", "real-model", "0" * 64, {}), directory)
