#!/usr/bin/env bash
# Repack a separately obtained second SquashFS image with a patched nwsoc.
set -euo pipefail

if [[ $# -ne 3 ]]; then
    printf 'Usage: %s ORIGINAL_SQUASHFS PATCHED_NWSOC OUTPUT_SQUASHFS\n' "$0" >&2
    exit 2
fi

input="$(realpath "$1")"
candidate="$(realpath "$2")"
output="$(realpath -m "$3")"
if [[ "$input" == "$output" ]]; then
    printf 'Input and output must differ.\n' >&2
    exit 2
fi
scratch="$(mktemp -d /tmp/et3850-repack.XXXXXX)"
unsquashfs -d "$scratch/root" "$input"
install -m 755 "$candidate" "$scratch/root/nwsoc"
mksquashfs "$scratch/root" "$output" -noappend -comp xz -b 131072 -no-xattrs -all-root -processors 2
unsquashfs -s "$output"
printf 'Scratch extraction: %s\n' "$scratch"
