"""Create an offline, byte-length-preserving Wi-Fi power candidate."""
import argparse
import hashlib
from pathlib import Path

EXPECTED = '70728f452c5358c4ef04ec39354c4656c42fa6e662af675ce88d161f05949ac0'
OLD = b'/sbin/insmod /opt/nwsoc/driver/8723du.ko rtw_power_mgnt=1 rtw_enusbss=1'
NEW = b'/sbin/insmod /opt/nwsoc/driver/8723du.ko rtw_power_mgnt=0 rtw_enusbss=0'

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = args.input.read_bytes()
assert hashlib.sha256(source).hexdigest() == EXPECTED, 'Unexpected nwsoc binary'
assert len(OLD) == len(NEW) and source.count(OLD) == 1
patched = source.replace(OLD, NEW, 1)
args.output.write_bytes(patched)
print('Candidate SHA-256:', hashlib.sha256(patched).hexdigest())
