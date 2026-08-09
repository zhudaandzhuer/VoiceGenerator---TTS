#!/usr/bin/env python3
"""Offline regression tests for audio-only scenes and media conversion."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ancient_audio_templates import BGM_PRESETS, RECITATION_TEMPLATES, ROOM_PRESETS, performance_direction
from audio_scene_mixer import audio_probe, render_audio_scene, run
from media_audio_tools import convert_to_mp3, separator_status


class AudioScenePipelineTests(unittest.TestCase):
    def test_catalogues_are_complete_and_acting_direction_is_non_spoken(self) -> None:
        self.assertGreaterEqual(len(RECITATION_TEMPLATES), 5)
        self.assertGreaterEqual(len(BGM_PRESETS), 5)
        self.assertGreaterEqual(len(ROOM_PRESETS), 5)
        identifiers = [item["id"] for item in RECITATION_TEMPLATES]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        prompt, metadata = performance_direction(identifiers[0], "第一句。\n第二句？")
        self.assertIn("逐句表演譜", prompt)
        self.assertIn("不得朗讀", prompt)
        self.assertEqual(metadata["lineCount"], 2)

    def test_real_ffmpeg_mix_outputs_wav_mp3_and_quality_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = Path(temporary) / "outputs"
            scene = outputs / "audio_scenes" / "test_scene"
            scene.mkdir(parents=True)
            voice = scene / "source_voice.wav"
            bgm = scene / "uploaded_bgm.wav"
            run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=2.2:sample_rate=48000", "-c:a", "pcm_s16le", str(voice)])
            run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=110:duration=4:sample_rate=48000", "-filter:a", "volume=0.16", "-c:a", "pcm_s16le", str(bgm)])
            manifest = render_audio_scene(
                outputs=outputs,
                scene_dir=scene,
                voice_path=voice,
                request={
                    "uploadedBgmFile": bgm.name,
                    "uploadedBgmName": "測試原創 BGM",
                    "roomPresetId": "warm-study",
                    "musicLevel": "voice-first",
                    "introSeconds": 0.4,
                    "outroSeconds": 0.8,
                },
                voice_metadata={"seedId": "seed-test", "seedName": "測試聲線"},
                scene_metadata={"id": "test_scene", "title": "實際音訊混音測試", "createdAt": "2026-08-09T00:00:00+00:00", "text": "測試台詞"},
            )
            self.assertTrue((scene / "master.wav").exists())
            self.assertTrue((scene / "master.mp3").exists())
            self.assertTrue((scene / "dry_voice.wav").exists())
            self.assertGreater(audio_probe(scene / "master.wav")["durationSeconds"], 3.0)
            self.assertIn("integratedLufs", manifest["qualityControl"])
            self.assertEqual(manifest["mix"]["ducking"], "speech-sidechain-8:1")

    def test_media_to_mp3_uses_first_audio_stream(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sample.mp4"
            target = root / "sample.mp3"
            run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1.2",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
                "-shortest", "-c:v", "libx264", "-c:a", "aac", str(source),
            ])
            info = convert_to_mp3(source, target)
            self.assertTrue(target.exists())
            self.assertEqual(info["codec"], "mp3")
            self.assertGreater(info["durationSeconds"], 1.0)

    def test_model_separator_is_available_after_setup(self) -> None:
        status = separator_status()
        self.assertIn("supportsMono", status)
        self.assertTrue(status["available"])


if __name__ == "__main__":
    unittest.main()
