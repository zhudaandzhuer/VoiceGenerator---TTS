#!/usr/bin/env python3
"""Offline regression tests for the production voice-asset layer."""

from __future__ import annotations

import io
import json
import struct
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

import seed_asset_system as assets
import voice_studio_server as studio


def make_wav(seconds: float = 2.4, amplitude: int = 1800, rate: int = 16000) -> bytes:
    samples = []
    for index in range(int(seconds * rate)):
        value = amplitude if (index // 80) % 2 else -amplitude
        samples.append(value)
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return output.getvalue()


class SeedAssetSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.outputs = Path(self.temporary.name) / "outputs"
        self.seed_id = "seed_test_actor"
        self.seed_dir = self.outputs / "voice_seeds" / self.seed_id
        self.seed_dir.mkdir(parents=True)
        audio = make_wav()
        (self.seed_dir / "reference.wav").write_bytes(audio)
        (self.seed_dir / "seed.json").write_text(json.dumps({
            "schemaVersion": 1,
            "id": self.seed_id,
            "name": "測試女刑警",
            "kind": "audio_clone",
            "gender": "女性",
            "description": "成熟冷靜、可靠、適合懸疑低語的女性刑警聲線",
            "referenceFile": "reference.wav",
            "referenceMime": "audio/wav",
            "referenceBytes": len(audio),
            "referenceSha256": assets.hashlib.sha256(audio).hexdigest(),
            "model": "mimo-v2.5-tts-voiceclone",
            "createdAt": assets.utc_now(),
            "status": "ready",
        }, ensure_ascii=False), encoding="utf-8")
        assets.ensure_layout(self.outputs)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_passport_anchor_version_and_selection(self) -> None:
        passport = assets.ensure_passport(self.outputs, self.seed_id)
        self.assertEqual(len(passport["anchors"]), 1)
        second = make_wav(seconds=3.1, amplitude=1100)
        asset = assets.add_anchor(
            self.outputs, self.seed_id,
            {"label": "近景耳語", "mode": "whisper"},
            "audio/wav", second, ".wav",
        )
        self.assertEqual(len(asset["passport"]["anchors"]), 2)
        whisper = next(item for item in asset["passport"]["anchors"] if item["mode"] == "whisper")
        versioned = assets.create_version(self.outputs, self.seed_id, {
            "label": "懸疑戲版", "anchorId": whisper["id"], "notes": "改用近景耳語錨點",
        })
        self.assertEqual(versioned["activeVersion"]["anchorId"], whisper["id"])
        _, selected, selected_path = assets.resolve_anchor(self.outputs, self.seed_id, performance_tags=["whisper"])
        self.assertEqual(selected["id"], whisper["id"])
        self.assertTrue(selected_path.exists())

    def test_performance_certification_casting_voicepack_and_continuity(self) -> None:
        custom = assets.create_performance_seed(self.outputs, {
            "name": "測試克制戲", "description": "冷靜後崩開", "emotions": ["平靜", "悲傷"],
            "anchorModes": ["neutral"], "tags": ["懸疑"],
        })
        self.assertTrue(custom["id"].startswith("perf_"))
        report = assets.certify_seed(self.outputs, self.seed_id)
        self.assertEqual(report["seedId"], self.seed_id)
        self.assertEqual(sum(item["maxPoints"] for item in report["checks"]), 100)
        recommendations = assets.recommend_cast(self.outputs, {
            "role": "成熟女刑警", "gender": "女性", "traits": "冷靜可靠懸疑低語",
            "performanceIds": ["perf_thriller_whisper"],
        })
        self.assertEqual(recommendations[0]["seed"]["id"], self.seed_id)
        self.assertGreaterEqual(recommendations[0]["score"], 50)
        voicepack = assets.export_voicepack(self.outputs, self.seed_id)
        pack_path = self.outputs / "voicepacks" / Path(voicepack["url"]).name
        self.assertTrue(pack_path.exists())
        with zipfile.ZipFile(pack_path) as archive:
            self.assertIn("voicepack.json", archive.namelist())
            self.assertIn("passport.json", archive.namelist())
        project = assets.save_continuity_project(self.outputs, {
            "title": "測試連戲", "format": "短劇", "roles": {"A": {"seedId": self.seed_id}},
            "beats": [{"role": "A", "text": "我在聽。", "pauseAfter": 0.5}],
        })
        self.assertTrue((self.outputs / "continuity_projects" / project["id"] / "production_manifest.json").exists())

    def test_generation_combines_voice_and_performance_seed(self) -> None:
        generated = make_wav(seconds=2.8, amplitude=1400)
        temporary_outputs = self.outputs
        with patch.object(studio, "OUTPUTS", temporary_outputs), \
             patch.object(studio, "SEEDS", temporary_outputs / "voice_seeds"), \
             patch.object(studio, "GENERATIONS", temporary_outputs / "voice_generations"), \
             patch.object(studio, "api_key_and_base_url", return_value=("test", "https://example.invalid")), \
             patch.object(studio, "request_audio", return_value=generated), \
             patch.object(studio, "refresh_dashboard", return_value=None):
            result = studio.generate_from_seed({
                "seedId": self.seed_id,
                "performanceSeedId": "perf_thriller_whisper",
                "text": "門外那個人，不是我哥。",
            })
        self.assertEqual(result["performanceSeedId"], "perf_thriller_whisper")
        self.assertTrue(result["anchorId"].startswith("anchor_"))
        self.assertIn(result["qualityGate"]["status"], {"pass", "review"})
        self.assertIsNotNone(result["qualityGate"]["acousticSimilarity"])
        manifest = json.loads((temporary_outputs / "voice_generations" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["samples"][-1]["performanceSeedName"], "懸疑低語")
        self.assertEqual(manifest["samples"][-1]["delivery"], "低語耳語")


if __name__ == "__main__":
    unittest.main(verbosity=2)
