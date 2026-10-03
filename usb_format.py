"""Formatage d'une partition USB identifiée, sans repartitionner le disque."""
import base64
import json
import plistlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class FormatError(RuntimeError):
    pass


@dataclass(frozen=True)
class FormatTarget:
    volume: str
    device: str
    identity: str
    size: int
    label: str
    platform: str


def _run(args, timeout=30):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FormatError(f"Commande indisponible ou délai dépassé : {args[0]} ({exc})") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).decode('utf-8', errors='replace').strip()
        raise FormatError(detail or f"Échec de {args[0]}")
    return result.stdout


def _powershell(script, timeout=30):
    prefix = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    encoded = base64.b64encode((prefix + script).encode('utf-16le')).decode('ascii')
    return _run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], timeout)


def _linux_target(volume, expected_device=None):
    data = json.loads(_run(['lsblk', '--json', '--bytes', '--paths', '--output',
                           'NAME,TYPE,TRAN,RO,SIZE,SERIAL,UUID,LABEL,MOUNTPOINTS']))
    for disk in data.get('blockdevices', []):
        children = disk.get('children', [])
        for part in children:
            mounts = [m for m in part.get('mountpoints', []) if m]
            if (expected_device and part['name'] != expected_device) or (
                    not expected_device and volume not in mounts):
                continue
            # Only a plain USB disk with exactly one partition; no LVM/RAID/crypt.
            if (disk.get('type') != 'disk' or disk.get('tran') != 'usb'
                    or disk.get('ro') or part.get('ro') or len(children) != 1
                    or part.get('type') != 'part' or part.get('children')
                    or any(disk.get('mountpoints') or [])
                    or (expected_device and mounts)
                    or any(m != volume for m in mounts)
                    or volume in ('/', '/boot', '/boot/efi', '/home', '/usr', '/var')):
                raise FormatError("Formatage réservé aux clés USB simples, à une partition, hors système.")
            serial, uuid = disk.get('serial'), part.get('uuid')
            if not serial or not uuid or not re.fullmatch(r'/dev/sd[a-z]+[0-9]+', part['name']):
                raise FormatError("Impossible d'identifier cette partition USB de manière fiable.")
            return FormatTarget(volume, part['name'], f'{serial}:{uuid}',
                                int(part['size']), part.get('label') or 'Sans nom', 'linux')
    raise FormatError("Sélectionnez la racine d'une clé USB montée, comportant une seule partition.")


def _mac_target(volume):
    info = plistlib.loads(_run(['diskutil', 'info', '-plist', volume]))
    parent_id = info.get('ParentWholeDisk')
    if not parent_id:
        raise FormatError("Une partition USB physique est requise (volumes APFS virtuels non pris en charge).")
    parent = plistlib.loads(_run(['diskutil', 'info', '-plist', parent_id]))
    device = info.get('DeviceIdentifier', '')
    if (info.get('MountPoint') != volume or info.get('Whole') is not False
            or parent.get('Internal') is not False or parent.get('BusProtocol') != 'USB'
            or info.get('Writable') is not True or not re.fullmatch(r'disk\d+s\d+', device)
            or volume == '/' or not info.get('DiskUUID')):
        raise FormatError("Le volume doit être une partition USB externe, accessible en écriture et hors système.")
    layout = plistlib.loads(_run(['diskutil', 'list', '-plist', parent_id]))
    disks = layout.get('AllDisksAndPartitions', [])
    partitions = disks[0].get('Partitions', []) if len(disks) == 1 else []
    data_parts = [p for p in partitions if p.get('Content') != 'EFI']
    if len(data_parts) != 1 or data_parts[0].get('DeviceIdentifier') != device:
        raise FormatError("Les clés contenant plusieurs partitions de données ne sont pas prises en charge.")
    return FormatTarget(volume, '/dev/' + device, str(info['DiskUUID']),
                        int(info.get('TotalSize', 0)), info.get('VolumeName') or 'Sans nom', 'darwin')


def _windows_probe_script(letter):
    return f"""
    $p = Get-Partition -DriveLetter '{letter}'
    $d = $p | Get-Disk
    $v = $p | Get-Volume
    if ($d.BusType -ne 'USB' -or $d.IsBoot -or $d.IsSystem -or $d.IsReadOnly -or
        $p.IsBoot -or $p.IsSystem -or $p.IsReadOnly -or
        $d.NumberOfPartitions -ne 1 -or !$d.UniqueId -or !$v.UniqueId) {{
        throw 'Une cle USB a une partition, hors systeme et accessible en ecriture est requise.'
    }}
    if ($p.Size -gt 32GB) {{ throw 'Le formatage FAT32 integre sous Windows est limite a 32 Gio.' }}
    """


def _windows_target(volume):
    if not re.fullmatch(r'[A-Za-z]:\\', volume):
        raise FormatError("Sélectionnez la racine du lecteur USB (par exemple E:\\).")
    script = _windows_probe_script(volume[0]) + """
    @{ device = "$($d.Number):$($p.PartitionNumber)";
       identity = "$($d.UniqueId):$($v.UniqueId)";
       size = $p.Size; label = $v.FileSystemLabel } | ConvertTo-Json -Compress
    """
    info = json.loads(_powershell(script).decode('utf-8-sig'))
    return FormatTarget(volume, info['device'], info['identity'],
                        int(info['size']), info.get('label') or 'Sans nom', 'win32')


def inspect_target(volume):
    """Lecture seule. Refuse les dossiers, disques internes et identités ambiguës."""
    volume = str(Path(volume).resolve())
    if sys.platform.startswith('linux'):
        for tool in ('lsblk', 'udisksctl', 'gdbus', 'mkfs.vfat'):
            if not shutil.which(tool):
                raise FormatError(f"Outil manquant : {tool}. Installez udisks2, dosfstools et les outils GLib.")
        target = _linux_target(volume)
    elif sys.platform == 'darwin':
        target = _mac_target(volume)
    elif sys.platform == 'win32':
        target = _windows_target(volume)
    else:
        raise FormatError("Formatage non disponible sur ce système.")
    if target.size < 512 * 1024 * 1024:
        raise FormatError("Le formatage FAT32 intégré nécessite un volume d'au moins 512 Mio.")
    # Refuse volumes hosting the application, working directory or user profile.
    for protected in (Path.home(), Path.cwd(), Path(sys.executable), Path(__file__)):
        try:
            protected.resolve().relative_to(Path(volume))
        except ValueError:
            continue
        raise FormatError("Ce volume contient l'application, le dossier de travail ou le profil utilisateur.")
    return target


def format_fat32(target):
    """Appeler seulement après confirmation utilisateur; revalide la cible avant écriture."""
    if inspect_target(target.volume) != target:
        raise FormatError("La clé a changé depuis la confirmation. Relancez l'analyse.")
    if target.platform == 'linux':
        _run(['udisksctl', 'unmount', '--block-device', target.device])
        if _linux_target(target.volume, target.device) != target:
            raise FormatError("L'identité de la clé a changé après démontage. Formatage annulé.")
        object_path = '/org/freedesktop/UDisks2/block_devices/' + Path(target.device).name
        _run(['gdbus', 'call', '--system', '--interactive', '--timeout', '600', '--dest', 'org.freedesktop.UDisks2',
              '--object-path', object_path, '--method', 'org.freedesktop.UDisks2.Block.Format',
              'vfat', "{'label': <'PODCASTS'>, 'mkfs-args': <['-F', '32']>, 'update-partition-type': <true>}"],
             timeout=600)
        try:
            _run(['udisksctl', 'mount', '--block-device', target.device])
        except FormatError as exc:
            return f"Formatage terminé, mais remontage impossible : {exc}\nRebranchez la clé puis analysez-la."
    elif target.platform == 'darwin':
        _run(['diskutil', 'eraseVolume', 'FAT32', 'PODCASTS', target.device], timeout=600)
    else:
        # Check permissions and identity again in the same PowerShell invocation.
        identity = target.identity.replace("'", "''")
        script = _windows_probe_script(target.volume[0]) + f"""
        $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
            throw 'Relancez AutoPodcast en tant qu administrateur pour formater la cle.'
        }}
        if ("$($d.UniqueId):$($v.UniqueId)" -ne '{identity}' -or
            "$($d.Number):$($p.PartitionNumber)" -ne '{target.device}') {{
            throw 'La cle a change. Formatage annule.'
        }}
        $p | Format-Volume -FileSystem FAT32 -NewFileSystemLabel PODCASTS -Confirm:$false -Force
        """
        _powershell(script, timeout=600)
    return "Formatage FAT32 terminé. Actualisez, sélectionnez la clé PODCASTS puis relancez l'analyse."
