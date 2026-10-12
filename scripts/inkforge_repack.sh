#!/usr/bin/env bash
set -euo pipefail

# Invoked by inkforge.py inside WSL. All paths are explicit; no firmware is bundled.
if [[ $# -ne 5 ]]; then
    echo 'usage: inkforge_repack.sh SQUASH0 SQUASH1 PASSWORD OUT0 OUT1' >&2
    exit 2
fi
input0="$1"
input1="$2"
password="$3"
output0="$4"
output1="$5"
scratch="$(mktemp -d /tmp/inkforge.XXXXXXXX)"
trap 'rm -rf -- "$scratch"' EXIT
unsquashfs -d "$scratch/root0" "$input0" >/dev/null
unsquashfs -d "$scratch/root1" "$input1" >/dev/null

python3 - "$scratch/root0" "$scratch/root1" "$password" <<'PY'
from pathlib import Path
import hashlib
import subprocess
import sys

root0, root1, secret_path = map(Path, sys.argv[1:])
secret = secret_path.read_bytes().strip()
if len(secret) < 24 or b'\n' in secret or b'\r' in secret:
    raise SystemExit('password file must hold one random line of at least 24 bytes')
hash_run = subprocess.run(['openssl', 'passwd', '-1', '-stdin'],
                          input=secret + b'\n', capture_output=True, check=True)
shadow_hash = hash_run.stdout.decode('ascii').strip()
if not shadow_hash.startswith('$1$') or '\r' in shadow_hash:
    raise SystemExit('unexpected crypt hash')
for name, prefix in [('passwd', 'root::0:0:'), ('shadow', 'root::')]:
    path = root0 / 'etc' / name
    lines = path.read_text().splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise SystemExit(f'unexpected root entry in {name}')
    i = matches[0]
    lines[i] = 'root:' + shadow_hash + lines[i][len('root:'):]
    path.write_text(''.join(lines))
    if '\r' in path.read_text():
        raise SystemExit(f'carriage return in {name}')

nwsoc = root1 / 'nwsoc'
original = nwsoc.read_bytes()
expected = '70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0'
if hashlib.sha256(original).hexdigest() != expected:
    raise SystemExit('nwsoc does not match pinned XB22Q5 build')
old = b'rtw_power_mgnt=1 rtw_enusbss=1'
new = b'rtw_power_mgnt=0 rtw_enusbss=0'
counts = {'8723du.ko': 0, '8821cu.ko': 0}
items = original.split(b'\0')
for index, item in enumerate(items):
    if item.startswith(b'/sbin/insmod ') and old in item:
        drivers = [name for name in counts if name.encode() in item]
        if len(drivers) != 1 or item.count(old) != 1:
            raise SystemExit('unexpected Wi-Fi loader command')
        counts[drivers[0]] += 1
        items[index] = item.replace(old, new)
if counts != {'8723du.ko': 1, '8821cu.ko': 4}:
    raise SystemExit(f'unexpected Wi-Fi command counts: {counts}')
patched = b'\0'.join(items)
if len(patched) != len(original):
    raise SystemExit('Wi-Fi patch changed executable length')
nwsoc.write_bytes(patched)

suspend = root1 / 'wlan_enable_suspend.sh'
script = suspend.read_bytes()
if hashlib.sha256(script).hexdigest() != 'dd63b11cade9a72a570e9fe28d680456b5dfed51530a34d25f28acd55e93322a':
    raise SystemExit('suspend script does not match pinned XB22Q5 build')
for before, after in [
    (b'echo auto > /sys/bus/usb/devices/$dev_port/power/control', b'echo on > /sys/bus/usb/devices/$dev_port/power/control'),
    (b'echo 0 > /proc/net/rtl8821cu/wlan0/auto_suspend_block', b'echo 1 > /proc/net/rtl8821cu/wlan0/auto_suspend_block'),
    (b'echo 0 > /proc/net/rtl8723du/wlan0/auto_suspend_block', b'echo 1 > /proc/net/rtl8723du/wlan0/auto_suspend_block'),
]:
    if script.count(before) != 1:
        raise SystemExit('unexpected suspend command count')
    script = script.replace(before, after, 1)
suspend.write_bytes(script)

watcher = root1 / 'watch_telnetd_trigger.sh'
watcher.write_text('''#!/bin/sh
hostname ET3850MOD
ps | grep '[t]elnetd -p 2323' >/dev/null || telnetd -p 2323 -l /opt/nwsoc/mod_login.sh
''')
watcher.chmod(0o755)
launcher = root1 / 'mod_login.sh'
launcher.write_text('''#!/bin/sh
/bin/stty -echo
printf 'ET3850MOD Password: '
IFS= read -r p
/bin/stty echo
printf '\\r\\n'
h="$(printf %s "$p" | /usr/bin/md5sum)"
unset p
[ "${h%% *}" = "''' + hashlib.md5(secret).hexdigest() + '''" ] || { echo 'Login incorrect'; exit 1; }
exec /bin/sh -l
''')
launcher.chmod(0o755)
gdb = root1 / 'watch_gdbserver_trigger.sh'
gdb.write_text('\n'.join(line for line in gdb.read_text().splitlines()
                         if line.strip() and (line.startswith('#!') or not line.lstrip().startswith('#'))) + '\n')
lost = root1 / 'lost+found'
if lost.is_dir() and not any(lost.iterdir()):
    lost.rmdir()
print('patched_nwsoc_sha256', hashlib.sha256(patched).hexdigest())
print('root_login_hash_present', True)
print('password_gated_port', 2323)
PY

mksquashfs "$scratch/root0" "$output0" -noappend -comp xz -b 131072 -no-xattrs -processors 2 >/dev/null
mksquashfs "$scratch/root1" "$output1" -noappend -comp xz -b 131072 -no-xattrs -processors 2 >/dev/null
unsquashfs -cat "$output1" mod_login.sh 2>/dev/null | grep -q 'ET3850MOD Password:'
unsquashfs -cat "$output1" watch_telnetd_trigger.sh 2>/dev/null | grep -q 'telnetd -p 2323'
echo 'repacked_filesystems_verified true'
