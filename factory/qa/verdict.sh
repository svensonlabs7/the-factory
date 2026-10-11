#!/usr/bin/env bash
# Passes only when the review's last verdict line is PASS. ux-laws says VIOLATIONS where the others say BLOCK.
grep -E '^\**(PASS|BLOCK|VIOLATIONS)\**( |$)' "$1" | tail -n 1 | grep -qE '^\**PASS'
