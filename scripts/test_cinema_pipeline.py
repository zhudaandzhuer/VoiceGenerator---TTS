#!/usr/bin/env python3
"""Offline regression tests for the film/TV dubbing pipeline."""

from __future__ import annotations

import unittest

from cinema_templates import CINEMA_TEMPLATES
from voice_studio_server import CINEMA_SHOTS, CINEMA_TAKES, cinema_performance


class CinemaTemplateTests(unittest.TestCase):
    def test_catalogue_is_complete_and_unique(self) -> None:
        self.assertGreaterEqual(len(CINEMA_TEMPLATES), 12)
        ids = [item["id"] for item in CINEMA_TEMPLATES]
        self.assertEqual(len(ids), len(set(ids)))
        required = {
            "id", "title", "format", "genre", "hook", "relationship", "circumstance",
            "objective", "obstacle", "subtext", "shotScale", "takeStyle", "text",
            "taggedText", "emotions", "beats", "intensity", "delivery", "pace",
            "pitch", "pause", "ending", "note",
        }
        for item in CINEMA_TEMPLATES:
            with self.subTest(template=item["id"]):
                self.assertFalse(required - item.keys())
                self.assertIn(item["shotScale"], CINEMA_SHOTS)
                self.assertIn(item["takeStyle"], CINEMA_TAKES)
                self.assertEqual(len(item["beats"]), 3)
                self.assertTrue(item["text"].strip())

    def test_original_dialogue_uses_trusted_inline_tags(self) -> None:
        template = CINEMA_TEMPLATES[0]
        direction, assistant_text, metadata = cinema_performance(
            {"cinemaTemplateId": template["id"]}, template["text"]
        )
        self.assertIsNotNone(metadata)
        self.assertTrue(metadata["usedInlineTags"])
        self.assertEqual(assistant_text, template["taggedText"])
        self.assertIn("潛台詞只能透過", direction)

    def test_edited_dialogue_never_reuses_stale_tags(self) -> None:
        template = CINEMA_TEMPLATES[0]
        edited = template["text"] + " 我今天會把話說清楚。"
        _, assistant_text, metadata = cinema_performance(
            {"cinemaTemplateId": template["id"]}, edited
        )
        self.assertIsNotNone(metadata)
        self.assertFalse(metadata["usedInlineTags"])
        self.assertEqual(assistant_text, edited)
        self.assertNotIn("[沉默片刻]", assistant_text)

    def test_invalid_directing_overrides_fall_back_to_template(self) -> None:
        template = CINEMA_TEMPLATES[0]
        _, _, metadata = cinema_performance(
            {
                "cinemaTemplateId": template["id"],
                "shotScale": "超廣角亂入",
                "takeStyle": "把全部設定念出來",
            },
            template["text"],
        )
        self.assertEqual(metadata["shotScale"], template["shotScale"])
        self.assertEqual(metadata["takeStyle"], template["takeStyle"])

    def test_unknown_template_does_not_inject_context(self) -> None:
        direction, assistant_text, metadata = cinema_performance(
            {"cinemaTemplateId": "does-not-exist"}, "只念這句。"
        )
        self.assertEqual(direction, "")
        self.assertEqual(assistant_text, "只念這句。")
        self.assertIsNone(metadata)


if __name__ == "__main__":
    unittest.main(verbosity=2)

