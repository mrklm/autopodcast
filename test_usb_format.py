import copy
import base64
import json
import plistlib
import shutil
import unittest
from unittest import mock

import usb_format


class UsbFormatTests(unittest.TestCase):
    def setUp(self):
        self.volume = '/media/test/CLE'
        self.part = dict(name='/dev/sdb1', type='part', ro=False, size=8 * 1024**3,
                         uuid='1234', label='CLE', mountpoints=[self.volume])
        self.disk = dict(name='/dev/sdb', type='disk', tran='usb', ro=False,
                         serial='USB123', mountpoints=[None], children=[self.part])

    def probe(self, disk=None, volume=None):
        with mock.patch.object(usb_format, '_run', return_value=json.dumps(
                {'blockdevices': [disk or self.disk]}).encode()):
            return usb_format._linux_target(volume or self.volume)

    def test_linux_accepts_identified_usb_partition(self):
        target = self.probe()
        self.assertEqual(target.device, '/dev/sdb1')
        self.assertEqual(target.identity, 'USB123:1234')

    def test_linux_rejects_internal_readonly_multiple_and_anonymous_devices(self):
        for change in ('internal', 'readonly', 'multiple', 'serial', 'uuid', 'layered', 'system'):
            with self.subTest(change=change):
                disk = copy.deepcopy(self.disk)
                part = disk['children'][0]
                if change == 'internal': disk['tran'] = 'sata'
                if change == 'readonly': part['ro'] = True
                if change == 'multiple': disk['children'].append(dict(part))
                if change == 'serial': disk['serial'] = None
                if change == 'uuid': part['uuid'] = None
                if change == 'layered': part['children'] = [{'type': 'crypt'}]
                if change == 'system': part['mountpoints'].append('/')
                with self.assertRaises(usb_format.FormatError):
                    self.probe(disk)

    def test_linux_rejects_subdirectory_and_system_root(self):
        with self.assertRaises(usb_format.FormatError):
            self.probe(volume=self.volume + '/podcasts')
        self.part['mountpoints'] = ['/']
        with self.assertRaises(usb_format.FormatError):
            self.probe(volume='/')

    def test_device_change_prevents_all_writes(self):
        target = self.probe()
        changed = usb_format.FormatTarget(target.volume, target.device, 'OTHER', target.size, target.label, 'linux')
        with mock.patch.object(usb_format, 'inspect_target', return_value=changed), \
                mock.patch.object(usb_format, '_run') as run:
            with self.assertRaises(usb_format.FormatError):
                usb_format.format_fat32(target)
            run.assert_not_called()

    def test_device_change_after_unmount_prevents_format(self):
        target = self.probe()
        with mock.patch.object(usb_format, 'inspect_target', return_value=target), \
                mock.patch.object(usb_format, '_linux_target', side_effect=usb_format.FormatError('changed')), \
                mock.patch.object(usb_format, '_run', return_value=b'') as run:
            with self.assertRaises(usb_format.FormatError):
                usb_format.format_fat32(target)
            self.assertEqual(run.call_args_list, [mock.call(['udisksctl', 'unmount', '--block-device', '/dev/sdb1'])])

    def test_linux_format_uses_partition_and_forces_fat32(self):
        target = self.probe()
        with mock.patch.object(usb_format, 'inspect_target', return_value=target), \
                mock.patch.object(usb_format, '_linux_target', return_value=target), \
                mock.patch.object(usb_format, '_run', return_value=b'') as run:
            usb_format.format_fat32(target)
        commands = [c.args[0] for c in run.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertIn('/org/freedesktop/UDisks2/block_devices/sdb1', commands[1])
        self.assertIn("'mkfs-args': <['-F', '32']>", commands[1][-1])
        self.assertEqual(commands[2], ['udisksctl', 'mount', '--block-device', '/dev/sdb1'])

    def test_linux_refuses_still_mounted_partition_after_unmount(self):
        with mock.patch.object(usb_format, '_run', return_value=json.dumps({'blockdevices': [self.disk]}).encode()):
            with self.assertRaises(usb_format.FormatError):
                usb_format._linux_target(self.volume, '/dev/sdb1')

    def test_mac_rejects_internal_disk(self):
        info = dict(ParentWholeDisk='disk2', DeviceIdentifier='disk2s1', MountPoint='/Volumes/CLE',
                    Whole=False, Writable=True, DiskUUID='uuid')
        parent = dict(Internal=True, BusProtocol='USB')
        with mock.patch.object(usb_format, '_run', side_effect=[plistlib.dumps(info), plistlib.dumps(parent)]):
            with self.assertRaises(usb_format.FormatError):
                usb_format._mac_target('/Volumes/CLE')

    def test_mac_formats_only_confirmed_partition(self):
        target = usb_format.FormatTarget('/Volumes/CLE', '/dev/disk2s1', 'uuid', 8*1024**3, 'CLE', 'darwin')
        with mock.patch.object(usb_format, 'inspect_target', return_value=target), \
                mock.patch.object(usb_format, '_run', return_value=b'') as run:
            usb_format.format_fat32(target)
        run.assert_called_once_with(['diskutil', 'eraseVolume', 'FAT32', 'PODCASTS', '/dev/disk2s1'], timeout=600)

    def test_windows_rejects_non_root_path_without_command(self):
        with mock.patch.object(usb_format, '_powershell') as run:
            for path in ('C:\\Windows', 'E:\\podcasts', "E'; bad"):
                with self.assertRaises(usb_format.FormatError):
                    usb_format._windows_target(path)
            run.assert_not_called()

    def test_mac_accepts_one_data_partition_with_efi(self):
        info = dict(ParentWholeDisk='disk2', DeviceIdentifier='disk2s2', MountPoint='/Volumes/CLE',
                    Whole=False, Writable=True, DiskUUID='uuid', TotalSize=8*1024**3, VolumeName='CLE')
        parent = dict(Internal=False, BusProtocol='USB')
        layout = {'AllDisksAndPartitions': [{'Partitions': [
            {'DeviceIdentifier': 'disk2s1', 'Content': 'EFI'},
            {'DeviceIdentifier': 'disk2s2', 'Content': 'Microsoft Basic Data'}]}]}
        with mock.patch.object(usb_format, '_run', side_effect=[plistlib.dumps(x) for x in (info, parent, layout)]):
            self.assertEqual(usb_format._mac_target('/Volumes/CLE').device, '/dev/disk2s2')
        layout['AllDisksAndPartitions'][0]['Partitions'].append({'DeviceIdentifier': 'disk2s3', 'Content': 'Apple_HFS'})
        with mock.patch.object(usb_format, '_run', side_effect=[plistlib.dumps(x) for x in (info, parent, layout)]):
            with self.assertRaises(usb_format.FormatError):
                usb_format._mac_target('/Volumes/CLE')

    def test_windows_probe_propagates_rejection(self):
        with mock.patch.object(usb_format, '_powershell', side_effect=usb_format.FormatError('not USB')):
            with self.assertRaises(usb_format.FormatError):
                usb_format._windows_target('E:\\')

    def test_windows_format_runs_only_for_unchanged_target(self):
        target = usb_format.FormatTarget('E:\\', '2:1', 'disk:volume', 8*1024**3, 'CLE', 'win32')
        with mock.patch.object(usb_format, 'inspect_target', return_value=target), \
                mock.patch.object(usb_format, '_powershell', return_value=b'') as run:
            usb_format.format_fat32(target)
        script = run.call_args.args[0]
        self.assertIn("Get-Partition -DriveLetter 'E'", script)
        self.assertIn("-ne 'disk:volume'", script)
        self.assertIn('$p | Format-Volume -FileSystem FAT32', script)

    @unittest.skipUnless(shutil.which('powershell.exe'), 'PowerShell Windows indisponible')
    def test_windows_generated_script_parses_without_executing_it(self):
        target = usb_format.FormatTarget('E:\\', '2:1', 'disk:volume', 8*1024**3, 'CLE', 'win32')
        with mock.patch.object(usb_format, 'inspect_target', return_value=target), \
                mock.patch.object(usb_format, '_powershell', return_value=b'') as run:
            usb_format.format_fat32(target)
        encoded = base64.b64encode(run.call_args.args[0].encode('utf-8')).decode('ascii')
        # Parse only: never invoke the generated script block or access a disk.
        usb_format._powershell(
            "$source=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded + "')); "
            "$null=[scriptblock]::Create($source)")


if __name__ == '__main__':
    unittest.main()
