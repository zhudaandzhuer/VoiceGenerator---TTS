#!/usr/bin/env python3
"""Offline checks for speaker-embedding availability and comparison policy."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import speaker_embedding


class SpeakerEmbeddingTests(unittest.TestCase):
    def test_missing_model_degrades_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            speaker_embedding, "model_path", return_value=Path(directory) / "missing.onnx"
        ):
            status = speaker_embedding.runtime_status()
            result = speaker_embedding.compare(Path("missing-a.wav"), Path("missing-b.wav"))
        self.assertFalse(status["available"])
        self.assertFalse(result["available"])
        self.assertIn("error", result)

    def test_policy_boundaries(self) -> None:
        self.assertEqual(speaker_embedding.decision_for(0.8), "pass")
        self.assertEqual(speaker_embedding.decision_for(0.55), "pass")
        self.assertEqual(speaker_embedding.decision_for(0.4), "review")
        self.assertEqual(speaker_embedding.decision_for(0.1), "fail")

    def test_installed_model_metadata_is_pinned(self) -> None:
        status = speaker_embedding.runtime_status()
        if not status["available"]:
            self.skipTest("optional WeSpeaker model not installed")
        self.assertEqual(status["modelSha256"], speaker_embedding.MODEL_SHA256)
        self.assertEqual(status["provider"], "wespeaker-cnceleb-resnet34-onnx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
