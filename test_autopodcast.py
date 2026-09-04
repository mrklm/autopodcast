import inspect
import unittest
from pathlib import Path
from unittest import mock

import autopodcast


class AutoPodcastRegressionTests(unittest.TestCase):
    def test_ffmpeg_convert_to_mp3_accepts_strip_metadata(self):
        signature = inspect.signature(autopodcast.ffmpeg_convert_to_mp3)

        self.assertIn("strip_metadata", signature.parameters)
        self.assertIs(signature.parameters["strip_metadata"].default, False)

    def test_find_ffmpeg_checks_common_macos_locations_without_shell_path(self):
        real_exists = Path("/usr/local/bin/ffmpeg").exists() or Path("/opt/homebrew/bin/ffmpeg").exists()
        if not real_exists:
            self.skipTest("no common macOS ffmpeg install found")

        with mock.patch("shutil.which", return_value=None):
            self.assertIsNotNone(autopodcast.find_ffmpeg())

    def test_destination_has_no_inbox_subdirectory(self):
        self.assertFalse(hasattr(autopodcast, "DEST_SUBDIR"))

    def test_pick_startup_theme_returns_existing_theme(self):
        self.assertIn(autopodcast.pick_startup_theme(), autopodcast.THEMES)


if __name__ == "__main__":
    unittest.main()
