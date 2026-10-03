import inspect
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import autopodcast
from usb_format import FormatTarget, FormatError


class AutoPodcastRegressionTests(unittest.TestCase):
    def test_format_cancellation_never_starts_worker(self):
        app = mock.Mock()
        app._operation_busy.return_value = False
        app.tab_general.var_volume.get.return_value = '/media/test/CLE'
        target = FormatTarget('/media/test/CLE', '/dev/sdb1', 'id', 8 * 1024**3, 'CLE', 'linux')
        for answer in (None, '', 'formater', 'NON'):
            with self.subTest(answer=answer), \
                    mock.patch('autopodcast.inspect_target', return_value=target), \
                    mock.patch('autopodcast.simpledialog.askstring', return_value=answer), \
                    mock.patch('autopodcast.threading.Thread') as thread:
                autopodcast.AutoPodcastApp.on_format(app)
                thread.assert_not_called()

    def test_format_refused_while_preparation_is_running(self):
        app = mock.Mock()
        app._operation_busy.return_value = True
        with mock.patch('autopodcast.messagebox.showwarning'), \
                mock.patch('autopodcast.inspect_target') as inspect:
            autopodcast.AutoPodcastApp.on_format(app)
            inspect.assert_not_called()

    def test_unsafe_target_never_reaches_confirmation(self):
        app = mock.Mock()
        app._operation_busy.return_value = False
        app.tab_general.var_volume.get.return_value = '/'
        with mock.patch('autopodcast.inspect_target', side_effect=FormatError('system')), \
                mock.patch('autopodcast.messagebox.showerror'), \
                mock.patch('autopodcast.simpledialog.askstring') as confirm, \
                mock.patch('autopodcast.threading.Thread') as thread:
            autopodcast.AutoPodcastApp.on_format(app)
            confirm.assert_not_called()
            thread.assert_not_called()

    def test_filesystem_analysis_handles_non_fat_and_vfat(self):
        with TemporaryDirectory() as tmp:
            for fs, ok in [('VFAT', True), ('FAT16', True), ('FAT32', True),
                           ('EXT4', False), ('APFS', False), ('EXFAT', False), ('UNKNOWN', False)]:
                with self.subTest(fs=fs), mock.patch('autopodcast.get_fs_type', return_value=fs):
                    self.assertEqual(autopodcast.analyze_usb(tmp).verdict_ok, ok)

    def test_ffmpeg_convert_to_mp3_accepts_strip_metadata(self):
        signature = inspect.signature(autopodcast.ffmpeg_convert_to_mp3)

        self.assertIn("strip_metadata", signature.parameters)
        self.assertIs(signature.parameters["strip_metadata"].default, False)
        self.assertIn("normalize_audio", signature.parameters)
        self.assertIs(signature.parameters["normalize_audio"].default, False)

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

    def test_ffmpeg_command_includes_dynaudnorm_when_enabled(self):
        commands = []

        class FakeProcess:
            stderr = None

            def poll(self):
                return 0

        def fake_popen(cmd, **kwargs):
            commands.append(cmd)
            return FakeProcess()

        with TemporaryDirectory() as tmp, mock.patch("subprocess.Popen", side_effect=fake_popen):
            autopodcast.ffmpeg_convert_to_mp3(
                ffmpeg_path=Path("/usr/bin/ffmpeg"),
                src=Path(tmp) / "source.mp3",
                dst=Path(tmp) / "dest.mp3",
                bitrate="128k",
                stop_event=threading.Event(),
                proc_holder={"proc": None},
                normalize_audio=True,
            )

        self.assertIn("-af", commands[0])
        self.assertIn("dynaudnorm=f=150:g=15", commands[0])


if __name__ == "__main__":
    unittest.main()
