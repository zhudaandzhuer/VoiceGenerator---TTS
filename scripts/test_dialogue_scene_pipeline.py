#!/usr/bin/env python3
"""Offline regression tests for two-character scene production."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from dialogue_scene_templates import DIALOGUE_SCENES
import voice_studio_server as studio


def silent_wav(seconds: float = 0.1, rate: int = 8000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(b"\x00\x00" * int(seconds * rate))
    return output.getvalue()


class DialogueTemplateTests(unittest.TestCase):
    def test_catalogue_has_complete_unique_two_role_scenes(self) -> None:
        self.assertGreaterEqual(len(DIALOGUE_SCENES), 6)
        ids = [scene["id"] for scene in DIALOGUE_SCENES]
        self.assertEqual(len(ids), len(set(ids)))
        for scene in DIALOGUE_SCENES:
            with self.subTest(scene=scene["id"]):
                self.assertEqual(set(scene["roles"]), {"A", "B"})
                self.assertGreaterEqual(len(scene["turns"]), 4)
                for turn in scene["turns"]:
                    self.assertIn(turn["role"], {"A", "B"})
                    self.assertTrue(turn["text"].strip())
                    self.assertGreater(float(turn["pauseAfter"]), 0)

    def test_turn_context_keeps_only_dialogue_in_assistant_message(self) -> None:
        scene = DIALOGUE_SCENES[0]
        context, assistant_text = studio.dialogue_turn_context(scene, 1)
        self.assertEqual(assistant_text, scene["turns"][1]["taggedText"])
        self.assertIn(scene["roles"]["A"]["objective"], context)
        self.assertIn("不要補演對手台詞", context)
        self.assertNotIn(scene["roles"]["A"]["objective"], assistant_text)

    def test_wav_stitching_inserts_exact_pause(self) -> None:
        audio, duration = studio.stitch_wav_lines(
            [silent_wav(0.1), silent_wav(0.2)], [0.25, 0.0]
        )
        self.assertAlmostEqual(duration, 0.55, places=2)
        self.assertAlmostEqual(studio.wav_duration(audio), 0.55, places=2)

    def test_full_scene_writes_lines_master_and_manifest_without_network(self) -> None:
        fake_audio = silent_wav(0.08)

        def fake_seed(seed_id: str):
            return ({"id": seed_id, "name": seed_id, "referenceSha256": seed_id + "hash"}, "不指定", "data:audio/wav;base64,")

        def fake_take(*, seed_id: str, text: str, assistant_text: str, context: str):
            return fake_audio, {
                "record": {"id": seed_id, "name": seed_id, "referenceSha256": seed_id + "hash"},
                "gender": "不指定",
                "durationSeconds": 0.08,
                "originalDurationSeconds": 0.08,
                "durationLimited": False,
            }

        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "dialogue_scenes"
            with (
                patch.object(studio, "DIALOGUE_SCENES", output_root),
                patch.object(studio, "load_seed_reference", side_effect=fake_seed),
                patch.object(studio, "synthesize_locked_take", side_effect=fake_take),
                patch.object(studio, "refresh_dashboard"),
            ):
                result = studio.generate_dialogue_scene({
                    "sceneTemplateId": DIALOGUE_SCENES[0]["id"],
                    "roleSeeds": {"A": "seed_a", "B": "seed_b"},
                    "pauseScale": 1.0,
                })
            scene_dir = output_root / result["id"]
            manifest = json.loads((scene_dir / "scene.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "ready")
            self.assertEqual(len(manifest["lines"]), len(DIALOGUE_SCENES[0]["turns"]))
            self.assertTrue((scene_dir / "scene.wav").exists())
            self.assertTrue(all((scene_dir / line["file"]).exists() for line in manifest["lines"]))
            expected = sum(0.08 + turn["pauseAfter"] for turn in DIALOGUE_SCENES[0]["turns"])
            self.assertAlmostEqual(result["durationSeconds"], expected, places=2)

    def test_same_seed_for_both_roles_is_rejected(self) -> None:
        with patch.object(studio, "load_seed_reference", return_value=({"id": "same"}, "不指定", "data:")):
            with self.assertRaisesRegex(ValueError, "不同聲音種子"):
                studio.generate_dialogue_scene({
                    "sceneTemplateId": DIALOGUE_SCENES[0]["id"],
                    "roleSeeds": {"A": "same", "B": "same"},
                })


if __name__ == "__main__":
    unittest.main(verbosity=2)
