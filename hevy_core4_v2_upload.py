#!/usr/bin/env python3
"""
Update Alex's existing Core-4 V2/V2.1 routines to Core-4 V2.2 in Hevy.

V2.2 design: flexible training slots
-----------------------------------
Each routine contains:
- PRIMARY exercises: preferred progression movement for that slot.
- ALT exercises: approved substitutes that REPLACE the primary when equipment is busy.
- OPTIONAL exercises: true add-on work only when recovery/time allow.

Important workout behavior:
- Complete only ONE exercise from each PRIMARY/ALT slot.
- Leave unused alternatives untouched in the workout.
- Once an ALT is completed, do not return later and complete the PRIMARY too.
- Every machine/variation has its own load history; loads are never interchangeable.
- On unfamiliar equipment, calibrate the first work set around 2-3 RIR before committing.

Safety/design choices:
- API key is read from HEVY_API_KEY or prompted securely; never hard-code it.
- Default mode is DRY RUN. Use --apply to write to Hevy.
- Exercise templates are fetched from your own Hevy account and matched by aliases.
- Ambiguous exercise matches are shown for manual selection before anything is written.
- Existing exact V2.2 titles are updated on reruns.
- Existing V2 or V2.1 titles are migrated IN PLACE to V2.2 by routine ID.
- Duplicate or conflicting version titles stop the entire preflight before writes.
- A local JSON snapshot of affected routines is saved before uploading.
- --preview shows all prescriptions and notes offline, without a key or requests.
- Older/non-Core-4 routines are left untouched.
- Program validation checks note lengths and Hevy's 150-set routine ceiling.

Usage:
    pip install requests
    python hevy_core4_v22_flexible_slots.py --preview
    python hevy_core4_v22_flexible_slots.py
    python hevy_core4_v22_flexible_slots.py --apply
    python hevy_core4_v22_flexible_slots.py --apply --yes

Optional environment variable:
    Windows PowerShell:
      $env:HEVY_API_KEY="YOUR_KEY"
    macOS/Linux:
      export HEVY_API_KEY="YOUR_KEY"
"""

from __future__ import annotations

import argparse
import difflib
import getpass
import os
import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # Offline --preview works without third-party packages.

BASE_URL = "https://api.hevyapp.com/v1"

# Keep the existing folder so the migrated routines stay grouped with the program.
# Hevy's current PUT routine schema does not expose folder_id, so this script does
# not attempt to move an already-existing routine to a new folder.
FOLDER_TITLE = "Alex Core-4 V2"

LB_PER_KG = 2.2046226218
HEVY_ROUTINE_SET_LIMIT = 150
EXERCISE_NOTE_MIN = 300
EXERCISE_NOTE_MAX = 600

ROLE_PRIMARY = "PRIMARY"
ROLE_ALT = "ALT"
ROLE_OPTIONAL = "OPTIONAL"
VALID_ROLES = {ROLE_PRIMARY, ROLE_ALT, ROLE_OPTIONAL}


def lb_to_kg(lb: float | None) -> float | None:
    if lb is None:
        return None
    return round(lb / LB_PER_KG, 4)


def normal_set(rep_min: int, rep_max: int, weight_lb: float | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "normal",
        "rep_range": {"start": rep_min, "end": rep_max},
    }
    if weight_lb is not None:
        payload["weight_kg"] = lb_to_kg(weight_lb)
    return payload


def role_prefix(slot: str, role: str, replaces: str | None = None) -> str:
    if role == ROLE_PRIMARY:
        return f"{slot} | PRIMARY. "
    if role == ROLE_ALT:
        replace_text = f" Replaces {replaces}." if replaces else " Replaces the PRIMARY for this slot."
        return f"{slot} | ALT.{replace_text} Choose ONE movement for this slot; never do both by default. "
    if role == ROLE_OPTIONAL:
        return f"{slot} | OPTIONAL. This is true add-on work, not required Core-4 volume. "
    raise ValueError(f"Invalid role: {role}")


def exercise(
    aliases: list[str],
    sets: int,
    rep_min: int,
    rep_max: int,
    weight_lb: float | None,
    rest_seconds: int,
    slot: str,
    role: str,
    coaching: str,
    replaces: str | None = None,
) -> dict[str, Any]:
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid exercise role: {role}")
    notes = role_prefix(slot, role, replaces) + coaching
    return {
        "aliases": aliases,
        "sets_count": sets,
        "rep_min": rep_min,
        "rep_max": rep_max,
        "weight_lb": weight_lb,
        "rest_seconds": rest_seconds,
        "slot": slot,
        "role": role,
        "notes": notes,
    }


PROGRAM_NOTES = 'V2.2: follow Upper A > Lower A > Upper B > Lower B as a rolling sequence; resume where you left off after missed days. Aim for four main sessions when feasible; optional Recovery + Arms must not displace one. PRIMARY/ALT: complete one exercise per slot and remove/leave unperformed alternatives unlogged. Optional slots are not required; do not perform every preloaded entry. Warm up with easy ramp sets. Compounds about 2 RIR; isolation 1-2; optional arms 2-3. Earn the top rep range twice with stable form before the smallest load increase. Loads are station-specific starting points from logs through Sep 30, not mandatory targets. No doubling unilateral loads. After poor sleep or a long gap, calibrate effort and reduce load/sets if needed. Stop movements that provoke back/radiating symptoms.'

LEGACY_TITLES = {'Upper A - Chest + Lats Strength V2.2': ['Upper A - Chest + Lats Strength '
                                          'V2.1',
                                          'Upper A - Chest + Lats Strength V2'],
 'Lower A - Quads + Glutes V2.2': ['Lower A - Quads + Glutes V2.1',
                                   'Lower A - Quads + Glutes V2'],
 'Upper B - Shoulders + V-Taper V2.2': ['Upper B - Shoulders + V-Taper V2.1',
                                        'Upper B - Shoulders + V-Taper V2'],
 'Lower B - Posterior + Stability V2.2': ['Lower B - Posterior + Stability '
                                          'V2.1',
                                          'Lower B - Posterior + Stability V2'],
 'Recovery + Arms V2.2': ['Recovery + Arms V2.1', 'Recovery + Arms V2']}

# Refreshed from workouts-5-sept.xlsx through September 30, 2026.
ROUTINES: list[dict[str, Any]] = [{'title': 'Upper A - Chest + Lats Strength V2.2',
  'notes': '17 planned sets. Keep incline at three work sets. Side/rear delts are planned work, performed before '
           'optional extras. No extra arms required. V2.2: follow Upper A > Lower A > Upper B > Lower B as a '
           'rolling sequence; resume where you left off after missed days. Aim for four main sessions when '
           'feasible; optional Recovery + Arms must not displace one. PRIMARY/ALT: complete one exercise per slot '
           'and remove/leave unperformed alternatives unlogged. Optional slots are not required; do not perform '
           'every preloaded entry. Warm up with easy ramp sets. Compounds about 2 RIR; isolation 1-2; optional '
           'arms 2-3. Earn the top rep range twice with stable form before the smallest load increase. Loads are '
           'station-specific starting points from logs through Sep 30, not mandatory targets. No doubling '
           'unilateral loads. After poor sleep or a long gap, calibrate effort and reduce load/sets if needed. '
           'Stop movements that provoke back/radiating symptoms.',
  'exercises': [{'aliases': ['Incline Bench Press (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 6,
                 'rep_max': 8,
                 'weight_lb': 52.5,
                 'rest_seconds': 180,
                 'slot': 'SLOT 1 - INCLINE ANCHOR',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 1 - INCLINE ANCHOR | PRIMARY. Setup: keep the same 30-degree bench, feet planted '
                          'and shoulder blades stable. Cues: lower under control; press without bouncing or rib '
                          'flare. Effort: stop with 1-2 clean reps left. Sep 22 was 8/8/8/7 with late RPE 10/9.5; '
                          'v2.2 uses THREE sets, not four. Hold 52.5 per hand; earn 3x8 twice without failure '
                          'before 55. Rest longer if performance drops; use 50 if target reserve is unavailable.'},
                {'aliases': ['Iso-Lateral Low Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 120,
                 'slot': 'SLOT 2 - ROW',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 2 - ROW | PRIMARY. Setup: chest supported, same seat and neutral handles. Cues: '
                          'reach smoothly, pull elbow toward lower ribs, keep torso square and avoid shrugging. '
                          'Start weaker side and match reps. Sep 22: 55 for 12/10/10. Hold 55 on the same '
                          'per-side logging convention and build 3x12 with 1-2 reps left before adding the '
                          'smallest plate. Never copy this number onto another row machine.'},
                {'aliases': ['Seated Row (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': 'SLOT 2 - ROW',
                 'role': 'ALT',
                 'notes': 'SLOT 2 - ROW | ALT. Replaces this slot; choose ONE. Setup: record seat/handle settings '
                          'and maintain chest support. Cues: allow controlled shoulder-blade reach, then pull '
                          'without leaning backward or lifting the chest off the pad. Sep 28: 115 for 12/12/10, '
                          'so retain 115 on that machine. Build 3x12 with 1-2 reps left on two exposures before '
                          'the next increment. Another machine requires calibration; a row alternative replaces '
                          'this slot.'},
                {'aliases': ['Seated Cable Row - V Grip (Cable)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 35,
                 'rest_seconds': 120,
                 'slot': 'SLOT 2 - ROW',
                 'role': 'ALT',
                 'notes': 'SLOT 2 - ROW | ALT. Replaces this slot; choose ONE. Setup: use the same dual-pulley '
                          'station and V-grip as Sep 14; record how the two stacks are configured. Cues: keep '
                          'torso quiet, reach without rounding the low back, pull toward lower ribs. Sep 14: '
                          'logged 35 for 3x12 at RPE 7.5-8.5. Keep that logging convention; calibrate if '
                          'equipment differs. Leave 1-2 reps in reserve and replace the row slot rather than '
                          'adding another row.'},
                {'aliases': ['Dumbbell Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 40,
                 'rest_seconds': 120,
                 'slot': 'SLOT 2 - ROW',
                 'role': 'ALT',
                 'notes': 'SLOT 2 - ROW | ALT. Replaces this slot; choose ONE. Setup: support one hand and, if '
                          'comfortable, one knee on a bench; keep hips and ribs square. Cues: let the shoulder '
                          'reach, then draw elbow toward hip without rotating or shrugging. Sep 5: 40 for 3x10 at '
                          'RPE 7-8. Start weaker side and match reps, keeping about 2 in reserve. Build 3x12 '
                          'before increasing. Prefer a supported machine if this setup irritates your low back.'},
                {'aliases': ['Iso-Lateral Chest Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 45,
                 'rest_seconds': 150,
                 'slot': 'SLOT 3 - CHEST PRESS',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 3 - CHEST PRESS | PRIMARY. Setup: use the same incline machine and seat as your '
                          'logged lift; 45 is per side under your existing convention. Cues: stable shoulder '
                          'blades, smooth comfortable depth, no shrugging or rib flare. Sep 17: 3x12 at RPE 7-8. '
                          'Repeat at 1-2 reps in reserve, then use the smallest increment. This slot can use '
                          'barbell or flat DB bench instead; never complete all three options.'},
                {'aliases': ['Bench Press (Barbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 180,
                 'slot': 'SLOT 3 - CHEST PRESS',
                 'role': 'ALT',
                 'notes': 'SLOT 3 - CHEST PRESS | ALT. Replaces this slot; choose ONE. Setup: flat bench, secure '
                          'rack/safeties or a spotter, stable feet and shoulder blades. Cues: lower smoothly, '
                          'consistent touch point, no bounce or excessive arch. Sep 22: 115 for 10/9/7. Hold 115 '
                          'total including bar; stop with 1-2 clean reps left and reduce load if you cannot reach '
                          'the range. Earn all sets at 12 twice before adding 5 lb. Replaces the chest-press '
                          'slot, not incline pressing.'},
                {'aliases': ['Bench Press (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 40,
                 'rest_seconds': 150,
                 'slot': 'SLOT 3 - CHEST PRESS',
                 'role': 'ALT',
                 'notes': 'SLOT 3 - CHEST PRESS | ALT. Replaces this slot; choose ONE. Setup: flat bench, feet '
                          'planted, shoulder blades stable; load is per hand. Cues: lower to a comfortable depth '
                          'with forearms stacked, then press evenly without clashing bells. Sep 5: 40 for 3x10 at '
                          'RPE 7-8; use this recent baseline rather than old heavier peaks. Build clean 3x12 at '
                          '1-2 reps in reserve twice before increasing. This is a chest-press substitute, not '
                          'extra chest volume.'},
                {'aliases': ['Lat Pulldown (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': 'SLOT 4 - PULLDOWN',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 4 - PULLDOWN | PRIMARY. Setup: fix thigh pad and grip; use the same selectorized '
                          'machine. Cues: slight stable lean, elbows toward ribs, controlled overhead stretch '
                          'without torso heave. Sep 17: 115 for 10/9/8. Hold 115 and build 3x10 twice with 1-2 '
                          'reps left. Increase only if range and posture stay unchanged. Cable and plate-loaded '
                          'pulldowns have separate load histories and replace this slot.'},
                {'aliases': ['Lat Pulldown (Cable)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 70,
                 'rest_seconds': 120,
                 'slot': 'SLOT 4 - PULLDOWN',
                 'role': 'ALT',
                 'notes': 'SLOT 4 - PULLDOWN | ALT. Replaces this slot; choose ONE. Setup: use the same cable '
                          'station, attachment and seat as the September sessions. Cues: keep ribs controlled and '
                          'pull elbows down without swinging; return to a comfortable full stretch. Sep 22: 70 '
                          'for 12/12/10. Build 3x12 at 1-2 reps in reserve before increasing. The 70-lb stack '
                          'number is station-specific and must not be compared with the 115-lb machine or 60-lb '
                          'iso pulldown.'},
                {'aliases': ['Single Arm Lateral Raise (Cable)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': 'SLOT 5 - SIDE DELT',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 5 - SIDE DELT | PRIMARY. Setup: hold the frame, stand consistently and start with '
                          'the weaker side. Cues: lead with elbow slightly forward of torso, raise without '
                          'shrugging or leaning, lower slowly. Sep 28: 12.5 for 3x16, last RPE 9. Keep 12.5 and '
                          'build toward 18-20 clean reps with 1-2 left before the smallest increase. Match sides '
                          'and stop when momentum changes. Delt work precedes optional arms.'},
                {'aliases': ['Seated Lateral Raise (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': 'SLOT 5 - SIDE DELT',
                 'role': 'ALT',
                 'notes': 'SLOT 5 - SIDE DELT | ALT. Replaces this slot; choose ONE. Setup: sit upright with feet '
                          'planted and dumbbells slightly forward. Cues: elbows lead, soft bend, controlled '
                          'lowering, no torso rocking or shrugging. Sep 3 used 12.5x20 then 15x12 twice, with '
                          'later RPE 9. Start 12.5 per hand for strict sets, then consider 15 only after the top '
                          'range is repeatable with 1-2 reps left. Keep seated and standing versions separate.'},
                {'aliases': ['Rear Delt Reverse Fly (Cable)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 7.5,
                 'rest_seconds': 75,
                 'slot': 'SLOT 6 - REAR DELT',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 6 - REAR DELT | PRIMARY. Setup: cable handles around shoulder height, ribs '
                          'stacked and a small fixed elbow bend. Cues: spread arms in a wide arc without turning '
                          'the movement into a row or shrug. Sep 14: 7.5 for 3x20; Sep 28: 10 for only 2x12. '
                          'Start 7.5 to restore repeatable volume, then earn 10 with the same range and 1-2 reps '
                          'left. This is planned rear-delt work, not a last-minute bonus.'},
                {'aliases': ['Rear Delt Reverse Fly (Machine)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': None,
                 'rest_seconds': 75,
                 'slot': 'SLOT 6 - REAR DELT',
                 'role': 'ALT',
                 'notes': 'SLOT 6 - REAR DELT | ALT. Replaces this slot; choose ONE. Setup: chest against pad, '
                          'handles at a comfortable shoulder-level height. Cues: open arms wide with soft elbows; '
                          'do not pull into a row, shrug or lift the chest. Calibrate for 12-20 reps with 2 reps '
                          'left; the old 70-75 lb entries were only 10-12 reps and are not a guaranteed starting '
                          'load. Match the cable slot set count and progress this machine independently. Replaces '
                          'cable rear delts.'}]},
 {'title': 'Lower A - Quads + Glutes V2.2',
  'notes': '12 planned sets plus at most one two-set optional accessory. Leg press OR hack squat, not both. Keep '
           'lower sessions separated by rest/upper work when possible. V2.2: follow Upper A > Lower A > Upper B > '
           'Lower B as a rolling sequence; resume where you left off after missed days. Aim for four main '
           'sessions when feasible; optional Recovery + Arms must not displace one. PRIMARY/ALT: complete one '
           'exercise per slot and remove/leave unperformed alternatives unlogged. Optional slots are not '
           'required; do not perform every preloaded entry. Warm up with easy ramp sets. Compounds about 2 RIR; '
           'isolation 1-2; optional arms 2-3. Earn the top rep range twice with stable form before the smallest '
           'load increase. Loads are station-specific starting points from logs through Sep 30, not mandatory '
           'targets. No doubling unilateral loads. After poor sleep or a long gap, calibrate effort and reduce '
           'load/sets if needed. Stop movements that provoke back/radiating symptoms.',
  'exercises': [{'aliases': ['Leg Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 250,
                 'rest_seconds': 180,
                 'slot': 'SLOT 1 - QUAD COMPOUND',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 1 - QUAD COMPOUND | PRIMARY. Setup: same seat and foot placement; keep pelvis and '
                          'back against pad. Cues: lower under control until just before pelvic tuck, drive '
                          'through the whole foot, avoid bouncing or forceful lockout. Sep 24: 250 for 12/10/10 '
                          'at RPE 8-8.5. Hold 250 and build 3x12 twice with about 2 reps left before increasing. '
                          'After poor recovery use 230 if needed. Hack squat is the substitute for this slot.'},
                {'aliases': ['Hack Squat (Machine)'],
                 'sets_count': 3,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': 215,
                 'rest_seconds': 180,
                 'slot': 'SLOT 1 - QUAD COMPOUND',
                 'role': 'ALT',
                 'notes': 'SLOT 1 - QUAD COMPOUND | ALT. Replaces this slot; choose ONE. Setup: stable feet and '
                          'back against pad; record foot placement and the same machine. Cues: controlled descent '
                          'only as deep as pelvis/back position permits, knees tracking with toes. Sep 1: 215 for '
                          '3x8 at RPE 8.5. Start at or below 215 after a gap, aiming for 2 reps left; build 3x10 '
                          'before adding. Do not chase the older 250-lb peak. Replaces leg press, not additional '
                          'quad-compound sets.'},
                {'aliases': ['Single Leg Extensions'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 45,
                 'rest_seconds': 90,
                 'slot': 'SLOT 2 - QUAD ISOLATION',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 2 - QUAD ISOLATION | PRIMARY. Setup: align knee with machine pivot and place shin '
                          'pad above ankle. Cues: extend smoothly, brief squeeze, controlled return, no hip lift. '
                          'Start weaker side and match reps. Sep 24: 45 for 3x15 at RPE 7-8.5. Repeat with 1-2 '
                          'reps left, then add the smallest increment and rebuild reps. Keep each-side logging '
                          'consistent; do not double the load to represent both legs.'},
                {'aliases': ['Seated Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 120,
                 'rest_seconds': 90,
                 'slot': 'SLOT 3 - LEG CURL',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 3 - LEG CURL | PRIMARY. Setup: align knee/pivot, secure thigh pad and keep hips '
                          'seated. Cues: curl through comfortable range without lifting hips, pause briefly, '
                          'control the return. Sep 24: 120 for 12/10/10. Hold 120 and build 3x12 twice with 1-2 '
                          'reps left before increasing. Following RDLs, calibrate effort and reduce load if '
                          'necessary. Seated, lying and standing curls are independent progression tracks.'},
                {'aliases': ['Lying Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 70,
                 'rest_seconds': 90,
                 'slot': 'SLOT 3 - LEG CURL',
                 'role': 'ALT',
                 'notes': 'SLOT 3 - LEG CURL | ALT. Replaces this slot; choose ONE. Setup: knees aligned with '
                          'pivot, pad above heels, pelvis against the bench. Cues: curl without lifting hips or '
                          'arching the low back; control the return. Sep 29: 70 for 3x12 at RPE 8-8.5. Repeat '
                          'cleanly with 1-2 reps left before a small increase. If performed after hinges, adjust '
                          'to fatigue rather than forcing the number. This replaces the selected leg-curl slot.'},
                {'aliases': ['Calf Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 110,
                 'rest_seconds': 90,
                 'slot': 'SLOT 4 - CALVES',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 4 - CALVES | PRIMARY. Setup: secure pelvis and feet on the same leg-press/calf '
                          'station, with knees softly extended. Cues: move through the ankle, control the stretch '
                          'and pause at the top; no bouncing or knee pumping. Sep 24: 110 for 3x15 with final RPE '
                          '9.5. Hold 110 and improve reserve before increasing. Keep 1-2 reps left and stop if '
                          'foot placement slips. This replaces other calf options.'},
                {'aliases': ['Standing Calf Raise (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': 'SLOT 4 - CALVES',
                 'role': 'ALT',
                 'notes': 'SLOT 4 - CALVES | ALT. Replaces this slot; choose ONE. Setup: shoulders under pads, '
                          'stable forefoot support and softly extended knees. Cues: lower into a controlled '
                          'comfortable stretch, pause, rise fully without bouncing. Sep 29: 55 for 3x15 but the '
                          'final set reached RPE 9.5. Hold 55, allow adequate rest and keep 1-2 reps left before '
                          'increasing. Machine numbers do not transfer to calf press or extension; consistent '
                          'ankle range defines progression.'},
                {'aliases': ['Calf Extension (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 70,
                 'rest_seconds': 90,
                 'slot': 'SLOT 4 - CALVES',
                 'role': 'ALT',
                 'notes': 'SLOT 4 - CALVES | ALT. Replaces this slot; choose ONE. Setup: align the machine for '
                          'stable forefoot contact and keep the knee position fixed. Cues: controlled stretch and '
                          'full comfortable contraction, no bouncing or shortening late reps. Sep 1 at 80 ended '
                          'at RPE 10, so retain the conservative 70-lb calibration rather than forcing 80. Aim '
                          'for 1-2 reps left across three sets. Increase only after repeatable top-range reps; '
                          'other calf stations are separate tracks.'},
                {'aliases': ['Hip Abduction (Machine)'],
                 'sets_count': 2,
                 'rep_min': 15,
                 'rep_max': 20,
                 'weight_lb': 80,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - HIP/CORE',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - HIP/CORE | OPTIONAL. Choose at most one optional accessory today. Setup: '
                          'sit securely with pelvis stable and a comfortable hip angle. Cues: open through the '
                          'hips without bouncing, pause briefly, return under control. Sep 10: 80 for 17/15 at '
                          'RPE 8.5. Hold 80 and build both sets to 20 with 1-2 reps left before increasing. Use '
                          'only as the chosen optional lower-day accessory when time and recovery allow; do not '
                          'stack every optional entry.'},
                {'aliases': ['Cable Core Pallof Press'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - HIP/CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - HIP/CORE | ALT. Replaces this slot; choose ONE. Setup: cable at chest '
                          'height, feet planted and ribs over pelvis. Cues: press hands away while resisting '
                          'rotation; breathe without leaning toward the stack. Sep 10 used 17.5 for 20 reps at '
                          'RPE 7.5; v2.2 uses fewer, slower reps with a 1-2 second extension pause. Work both '
                          'sides, stop before posture changes, and track this new tempo separately. Optional core '
                          'never replaces main lifts.'},
                {'aliases': ['Dead Bug'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - HIP/CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - HIP/CORE | ALT. Replaces this slot; choose ONE. Setup: lie on back, '
                          'hips/knees bent and ribs controlled; begin with body weight. Cues: slowly reach '
                          'opposite arm/leg only as far as you can keep the trunk still; exhale on the reach. '
                          'Recent logs used 10 reps but varied added load, so standardize to 6-10 per side now. '
                          'Stop before back position changes. Progress reach/control before weight; this is a '
                          'core alternative, not extra arm-day volume.'},
                {'aliases': ['Bird Dog'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - HIP/CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - HIP/CORE | ALT. Replaces this slot; choose ONE. Setup: hands under '
                          'shoulders and knees under hips on a stable floor. Cues: reach opposite arm/leg long '
                          'rather than high, keep pelvis level and pause briefly without arching. Sep 23 logged '
                          '2x10; v2.2 uses 6-10 controlled reps per side without BOSU or added load. Stop for '
                          'symptoms or loss of trunk control. Progress hold quality before reps and choose one '
                          'core movement.'}]},
 {'title': 'Upper B - Shoulders + V-Taper V2.2',
  'notes': '16 planned sets plus at most two optional fly sets. Restore a second incline-press exposure and make '
           'rear delts planned. Shoulder press is two sets. Keep the lighter incline prescription separate from '
           'Upper A. V2.2: follow Upper A > Lower A > Upper B > Lower B as a rolling sequence; resume where you '
           'left off after missed days. Aim for four main sessions when feasible; optional Recovery + Arms must '
           'not displace one. PRIMARY/ALT: complete one exercise per slot and remove/leave unperformed '
           'alternatives unlogged. Optional slots are not required; do not perform every preloaded entry. Warm up '
           'with easy ramp sets. Compounds about 2 RIR; isolation 1-2; optional arms 2-3. Earn the top rep range '
           'twice with stable form before the smallest load increase. Loads are station-specific starting points '
           'from logs through Sep 30, not mandatory targets. No doubling unilateral loads. After poor sleep or a '
           'long gap, calibrate effort and reduce load/sets if needed. Stop movements that provoke back/radiating '
           'symptoms.',
  'exercises': [{'aliases': ['Iso Pulldown'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 60,
                 'rest_seconds': 120,
                 'slot': 'SLOT 1 - PULLDOWN',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 1 - PULLDOWN | PRIMARY. Setup: same plate-loaded iso machine and thigh pad, with '
                          'consistent one-arm/per-side logging. Cues: allow a comfortable overhead stretch, drive '
                          'elbow toward hip and keep torso square. Sep 28: 60 for 3x12 at RPE 7.5-8. Repeat or '
                          'use the smallest next plate only with unchanged range and 1-2 reps left. Do not '
                          'transfer this load to the selectorized single-arm or cable station.'},
                {'aliases': ['Single Arm Lat Pulldown'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': None,
                 'rest_seconds': 120,
                 'slot': 'SLOT 1 - PULLDOWN',
                 'role': 'ALT',
                 'notes': 'SLOT 1 - PULLDOWN | ALT. Replaces this slot; choose ONE. Setup: identify the '
                          'selectorized single-arm station and record pulley/handle settings; your June note '
                          'indicated a possible 2:1 pulley ratio. Cues: torso square, full comfortable reach, '
                          'elbow toward hip without twisting. Recalibrate with 2-3 reps left because this '
                          'variation has not been logged since August. Do not copy the iso-machine load or treat '
                          'old 100-120 stack entries as equivalent resistance.'},
                {'aliases': ['Seated Overhead Press (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': 35,
                 'rest_seconds': 150,
                 'slot': 'SLOT 2 - SHOULDER PRESS',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 2 - SHOULDER PRESS | PRIMARY. Setup: supported bench about 60-75 degrees and a '
                          'comfortable grip. Cues: brace, keep ribs down and press evenly without leaning back. '
                          'Sep 14: 35 for 10/10/9 with late RPE 9.5. V2.2 uses two sets at 1-2 reps in reserve to '
                          'leave room for chest and delts. Hold 35 or reduce if needed; earn two clean 10s twice '
                          'before increasing. Machine shoulder press replaces this slot.'},
                {'aliases': ['Seated Shoulder Press (Machine)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 150,
                 'slot': 'SLOT 2 - SHOULDER PRESS',
                 'role': 'ALT',
                 'notes': 'SLOT 2 - SHOULDER PRESS | ALT. Replaces this slot; choose ONE. Setup: match the Sep 28 '
                          'machine and seat height, handles around a comfortable shoulder level. Cues: back '
                          'supported, ribs controlled, press smoothly without shrugging or forceful lockout. Sep '
                          '28: 55 for 3x12 at RPE 7.5-8.5; v2.2 uses two sets in this slot. Keep 1-2 reps left '
                          'and repeat before increasing. The 55-lb machine number is unrelated to 35-lb '
                          'dumbbells.'},
                {'aliases': ['Seated Row (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': 'SLOT 3 - ROW',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 3 - ROW | PRIMARY. Setup: record seat/handle settings and maintain chest support. '
                          'Cues: allow controlled shoulder-blade reach, then pull without leaning backward or '
                          'lifting the chest off the pad. Sep 28: 115 for 12/12/10, so retain 115 on that '
                          'machine. Build 3x12 with 1-2 reps left on two exposures before the next increment. '
                          'Another machine requires calibration; a row alternative replaces this slot.'},
                {'aliases': ['Chest Supported T Bar Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 60,
                 'rest_seconds': 120,
                 'slot': 'SLOT 3 - ROW',
                 'role': 'ALT',
                 'notes': 'SLOT 3 - ROW | ALT. Replaces this slot; choose ONE. Setup: choose an actual '
                          'chest-supported T-bar station, chest on pad and feet braced. Cues: controlled reach, '
                          'pull without lifting torso or jerking from the bottom. Aug 27: 60 for 10/10/8; the '
                          'older export contained a corrected 70-rep typo and is not a PR. Recalibrate at about 2 '
                          'reps left after the gap. Only this exact supported variation shares this starting '
                          'load.'},
                {'aliases': ['Seated Cable Row - V Grip (Cable)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 35,
                 'rest_seconds': 120,
                 'slot': 'SLOT 3 - ROW',
                 'role': 'ALT',
                 'notes': 'SLOT 3 - ROW | ALT. Replaces this slot; choose ONE. Setup: use the same dual-pulley '
                          'station and V-grip as Sep 14; record how the two stacks are configured. Cues: keep '
                          'torso quiet, reach without rounding the low back, pull toward lower ribs. Sep 14: '
                          'logged 35 for 3x12 at RPE 7.5-8.5. Keep that logging convention; calibrate if '
                          'equipment differs. Leave 1-2 reps in reserve and replace the row slot rather than '
                          'adding another row.'},
                {'aliases': ['Dumbbell Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 40,
                 'rest_seconds': 120,
                 'slot': 'SLOT 3 - ROW',
                 'role': 'ALT',
                 'notes': 'SLOT 3 - ROW | ALT. Replaces this slot; choose ONE. Setup: support one hand and, if '
                          'comfortable, one knee on a bench; keep hips and ribs square. Cues: let the shoulder '
                          'reach, then draw elbow toward hip without rotating or shrugging. Sep 5: 40 for 3x10 at '
                          'RPE 7-8. Start weaker side and match reps, keeping about 2 in reserve. Build 3x12 '
                          'before increasing. Prefer a supported machine if this setup irritates your low back.'},
                {'aliases': ['Incline Bench Press (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 47.5,
                 'rest_seconds': 180,
                 'slot': 'SLOT 4 - LIGHT INCLINE',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 4 - LIGHT INCLINE | PRIMARY. Setup: same 30-degree bench and per-hand logging as '
                          'Upper A. Cues: feet planted, stable shoulder blades, controlled comfortable depth and '
                          'no rib flare. Start 47.5 per hand for TWO sets of 8-12 with 2-3 reps left; this is a '
                          'conservative re-entry prescription, not a September PR. Reduce if prior shoulder '
                          'pressing limits reserve. Earn 2x12 twice before 50. This lighter exposure complements '
                          'Upper A without repeating its near-failure fourth set.'},
                {'aliases': ['Single Arm Lateral Raise (Cable)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': 'SLOT 5 - SIDE DELT',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 5 - SIDE DELT | PRIMARY. Setup: hold the frame, stand consistently and start with '
                          'the weaker side. Cues: lead with elbow slightly forward of torso, raise without '
                          'shrugging or leaning, lower slowly. Sep 28: 12.5 for 3x16, last RPE 9. Keep 12.5 and '
                          'build toward 18-20 clean reps with 1-2 left before the smallest increase. Match sides '
                          'and stop when momentum changes. Delt work precedes optional arms.'},
                {'aliases': ['Seated Lateral Raise (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': 'SLOT 5 - SIDE DELT',
                 'role': 'ALT',
                 'notes': 'SLOT 5 - SIDE DELT | ALT. Replaces this slot; choose ONE. Setup: sit upright with feet '
                          'planted and dumbbells slightly forward. Cues: elbows lead, soft bend, controlled '
                          'lowering, no torso rocking or shrugging. Sep 3 used 12.5x20 then 15x12 twice, with '
                          'later RPE 9. Start 12.5 per hand for strict sets, then consider 15 only after the top '
                          'range is repeatable with 1-2 reps left. Keep seated and standing versions separate.'},
                {'aliases': ['Rear Delt Reverse Fly (Cable)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 7.5,
                 'rest_seconds': 75,
                 'slot': 'SLOT 6 - REAR DELT',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 6 - REAR DELT | PRIMARY. Setup: cable handles around shoulder height, ribs '
                          'stacked and a small fixed elbow bend. Cues: spread arms in a wide arc without turning '
                          'the movement into a row or shrug. Sep 14: 7.5 for 3x20; Sep 28: 10 for only 2x12. '
                          'Start 7.5 to restore repeatable volume, then earn 10 with the same range and 1-2 reps '
                          'left. This is planned rear-delt work, not a last-minute bonus.'},
                {'aliases': ['Rear Delt Reverse Fly (Machine)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': None,
                 'rest_seconds': 75,
                 'slot': 'SLOT 6 - REAR DELT',
                 'role': 'ALT',
                 'notes': 'SLOT 6 - REAR DELT | ALT. Replaces this slot; choose ONE. Setup: chest against pad, '
                          'handles at a comfortable shoulder-level height. Cues: open arms wide with soft elbows; '
                          'do not pull into a row, shrug or lift the chest. Calibrate for 12-20 reps with 2 reps '
                          'left; the old 70-75 lb entries were only 10-12 reps and are not a guaranteed starting '
                          'load. Match the cable slot set count and progress this machine independently. Replaces '
                          'cable rear delts.'},
                {'aliases': ['Low Cable Fly Crossovers'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - CHEST FLY',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - CHEST FLY | OPTIONAL. Choose at most one optional accessory today. Setup: '
                          'use the same low pulleys, soft elbow bend and balanced stance. Cues: bring hands up '
                          'and inward through a comfortable arc; no shoulder roll, deep forced stretch or torso '
                          'swing. Last logged Aug 31 at 12.5 for 15/15, then a lighter set. Recalibrate at 2 reps '
                          'left. This is an optional two-set chest accessory after planned delts, not a '
                          'replacement for the incline press anchor.'},
                {'aliases': ['Decline Chest Fly (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 27.5,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - CHEST FLY',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CHEST FLY | ALT. Replaces this slot; choose ONE. Setup: modest decline with '
                          'secure feet and a small fixed elbow bend. Cues: open only into a comfortable chest '
                          'stretch, then bring arms together without turning the rep into a press. Sep 28: 27.5 '
                          'for 3x12 at RPE 7.5-8. Use two sets in the optional fly slot, with 1-2 reps left. '
                          'Build toward 15 before increasing; this is a general chest alternative, not equivalent '
                          'upper-chest emphasis.'},
                {'aliases': ['Chest Fly (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 25,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - CHEST FLY',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CHEST FLY | ALT. Replaces this slot; choose ONE. Setup: flat bench, stable '
                          'feet and soft elbows; weight is per hand. Cues: lower to a comfortable chest stretch, '
                          'keep shoulder blades stable and bring arms together without bouncing or forcing depth. '
                          'Sep 30: 25 for 2x15 at RPE 7.5. Retain that recent controlled baseline instead of '
                          'September 17 heavier 8-rep work. Use only the two optional fly sets and leave 1-2 reps '
                          'in reserve.'},
                {'aliases': ['Chest Fly (Machine)'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 85,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - CHEST FLY',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CHEST FLY | ALT. Replaces this slot; choose ONE. Setup: seat for a '
                          'comfortable chest-height arm path, with torso and shoulders stable. Cues: controlled '
                          'stretch and squeeze; avoid slamming the stack or rolling shoulders forward. Sep 3: 85 '
                          'for 15/15/12 at RPE 7.5-8.5. Use two sets as the optional fly choice and retain 1-2 '
                          'reps in reserve. Repeat top-range reps before increasing, and track independently of '
                          'dumbbell or cable fly loads.'}]},
 {'title': 'Lower B - Posterior + Stability V2.2',
  'notes': '15 planned sets plus at most two optional core sets. Hip thrust and RDL stay controlled; calves are '
           'planned. No extra heavy hinge or back-extension finisher. V2.2: follow Upper A > Lower A > Upper B > '
           'Lower B as a rolling sequence; resume where you left off after missed days. Aim for four main '
           'sessions when feasible; optional Recovery + Arms must not displace one. PRIMARY/ALT: complete one '
           'exercise per slot and remove/leave unperformed alternatives unlogged. Optional slots are not '
           'required; do not perform every preloaded entry. Warm up with easy ramp sets. Compounds about 2 RIR; '
           'isolation 1-2; optional arms 2-3. Earn the top rep range twice with stable form before the smallest '
           'load increase. Loads are station-specific starting points from logs through Sep 30, not mandatory '
           'targets. No doubling unilateral loads. After poor sleep or a long gap, calibrate effort and reduce '
           'load/sets if needed. Stop movements that provoke back/radiating symptoms.',
  'exercises': [{'aliases': ['Hip Thrust (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 140,
                 'rest_seconds': 180,
                 'slot': 'SLOT 1 - HIP THRUST',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 1 - HIP THRUST | PRIMARY. Setup: pad across hips, feet positioned for a stable '
                          'top position and ribs controlled. Cues: drive through the feet, finish with glutes and '
                          'a brief pause, not lumbar hyperextension. Sep 29: 140 for 3x10 at RPE 7.5-8. '
                          'Consolidate that result, then add the smallest increment if the same range and 2 reps '
                          'in reserve remain. Machine load is independent of barbell thrusts; reduce after poor '
                          'recovery.'},
                {'aliases': ['Romanian Deadlift (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 50,
                 'rest_seconds': 180,
                 'slot': 'SLOT 2 - HINGE',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 2 - HINGE | PRIMARY. Setup: feet hip-width, soft knees, dumbbells close to '
                          'thighs; load is per hand. Cues: send hips back, stop at your controlled hamstring '
                          'stretch before spinal position changes, then stand through hips. Sep 29: 50 for 3x8 at '
                          'RPE 8. Build toward 3x10 with 2 reps left before increasing. No straps required; if '
                          'grip or back limits the set, reduce load. Stop for radiating symptoms, numbness or '
                          'back pain.'},
                {'aliases': ['Reverse Lunge (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 35,
                 'rest_seconds': 120,
                 'slot': 'SLOT 3 - LUNGE',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 3 - LUNGE | PRIMARY. Setup: hold dumbbells steadily; use light support if needed '
                          'for balance. Cues: step back into a stable stance, controlled depth, front knee tracks '
                          'with toes, push through front foot without twisting. Sep 29: 35 per hand for 3x8 at '
                          'RPE 8-8.5. Build to 3x10 per leg with about 2 reps left. Match weaker-side reps and '
                          'lower load if balance, grip or back position breaks down.'},
                {'aliases': ['Lying Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 70,
                 'rest_seconds': 90,
                 'slot': 'SLOT 4 - LEG CURL',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 4 - LEG CURL | PRIMARY. Setup: knees aligned with pivot, pad above heels, pelvis '
                          'against the bench. Cues: curl without lifting hips or arching the low back; control '
                          'the return. Sep 29: 70 for 3x12 at RPE 8-8.5. Repeat cleanly with 1-2 reps left before '
                          'a small increase. If performed after hinges, adjust to fatigue rather than forcing the '
                          'number. This replaces the selected leg-curl slot.'},
                {'aliases': ['Standing Leg Curls'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': 'SLOT 4 - LEG CURL',
                 'role': 'ALT',
                 'notes': 'SLOT 4 - LEG CURL | ALT. Replaces this slot; choose ONE. Setup: use the same machine, '
                          'align knee with pivot and support torso. Cues: keep pelvis still and curl without hip '
                          'swing or lumbar extension. Start weaker leg and match clean reps. Sep 15: 55 for '
                          '12/12/10. Hold 55 and build 3x12 with 1-2 reps left before the smallest increase. '
                          'Seated or lying curls replace these sets; do not add all variations in one session.'},
                {'aliases': ['Seated Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 120,
                 'rest_seconds': 90,
                 'slot': 'SLOT 4 - LEG CURL',
                 'role': 'ALT',
                 'notes': 'SLOT 4 - LEG CURL | ALT. Replaces this slot; choose ONE. Setup: align knee/pivot, '
                          'secure thigh pad and keep hips seated. Cues: curl through comfortable range without '
                          'lifting hips, pause briefly, control the return. Sep 24: 120 for 12/10/10. Hold 120 '
                          'and build 3x12 twice with 1-2 reps left before increasing. Following RDLs, calibrate '
                          'effort and reduce load if necessary. Seated, lying and standing curls are independent '
                          'progression tracks.'},
                {'aliases': ['Standing Calf Raise (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': 'SLOT 5 - CALVES',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 5 - CALVES | PRIMARY. Setup: shoulders under pads, stable forefoot support and '
                          'softly extended knees. Cues: lower into a controlled comfortable stretch, pause, rise '
                          'fully without bouncing. Sep 29: 55 for 3x15 but the final set reached RPE 9.5. Hold '
                          '55, allow adequate rest and keep 1-2 reps left before increasing. Machine numbers do '
                          'not transfer to calf press or extension; consistent ankle range defines progression.'},
                {'aliases': ['Calf Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 110,
                 'rest_seconds': 90,
                 'slot': 'SLOT 5 - CALVES',
                 'role': 'ALT',
                 'notes': 'SLOT 5 - CALVES | ALT. Replaces this slot; choose ONE. Setup: secure pelvis and feet '
                          'on the same leg-press/calf station, with knees softly extended. Cues: move through the '
                          'ankle, control the stretch and pause at the top; no bouncing or knee pumping. Sep 24: '
                          '110 for 3x15 with final RPE 9.5. Hold 110 and improve reserve before increasing. Keep '
                          '1-2 reps left and stop if foot placement slips. This replaces other calf options.'},
                {'aliases': ['Calf Extension (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 70,
                 'rest_seconds': 90,
                 'slot': 'SLOT 5 - CALVES',
                 'role': 'ALT',
                 'notes': 'SLOT 5 - CALVES | ALT. Replaces this slot; choose ONE. Setup: align the machine for '
                          'stable forefoot contact and keep the knee position fixed. Cues: controlled stretch and '
                          'full comfortable contraction, no bouncing or shortening late reps. Sep 1 at 80 ended '
                          'at RPE 10, so retain the conservative 70-lb calibration rather than forcing 80. Aim '
                          'for 1-2 reps left across three sets. Increase only after repeatable top-range reps; '
                          'other calf stations are separate tracks.'},
                {'aliases': ['Cable Core Pallof Press'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - CORE | OPTIONAL. Choose at most one optional accessory today. Setup: cable '
                          'at chest height, feet planted and ribs over pelvis. Cues: press hands away while '
                          'resisting rotation; breathe without leaning toward the stack. Sep 10 used 17.5 for 20 '
                          'reps at RPE 7.5; v2.2 uses fewer, slower reps with a 1-2 second extension pause. Work '
                          'both sides, stop before posture changes, and track this new tempo separately. Optional '
                          'core never replaces main lifts.'},
                {'aliases': ['Dead Bug'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: lie on back, hips/knees '
                          'bent and ribs controlled; begin with body weight. Cues: slowly reach opposite arm/leg '
                          'only as far as you can keep the trunk still; exhale on the reach. Recent logs used 10 '
                          'reps but varied added load, so standardize to 6-10 per side now. Stop before back '
                          'position changes. Progress reach/control before weight; this is a core alternative, '
                          'not extra arm-day volume.'},
                {'aliases': ['Bird Dog'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: hands under shoulders '
                          'and knees under hips on a stable floor. Cues: reach opposite arm/leg long rather than '
                          'high, keep pelvis level and pause briefly without arching. Sep 23 logged 2x10; v2.2 '
                          'uses 6-10 controlled reps per side without BOSU or added load. Stop for symptoms or '
                          'loss of trunk control. Progress hold quality before reps and choose one core '
                          'movement.'},
                {'aliases': ['Reverse Crunch'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: lie on back with bent '
                          'knees and arms supporting balance. Cues: gently curl pelvis off the floor without '
                          'throwing legs or arching on the descent. Sep 23 reached 25 reps, but v2.2 uses 10-15 '
                          'slower repetitions with a brief pelvic curl pause. Stop before momentum replaces '
                          'control. Progress controlled range first; no ankle weights needed. Choose this instead '
                          'of other core options.'}]},
 {'title': 'Recovery + Arms V2.2',
  'notes': 'OPTIONAL FIFTH SESSION, not a rest day or replacement for a main session. Two primary arm slots = six '
           'sets; add at most ONE two-set optional accessory from EITHER optional slot (eight total). Easy '
           'walking/mobility can follow. Keep 2-3 RIR; skip this session when recovery or time is limited. V2.2: '
           'follow Upper A > Lower A > Upper B > Lower B as a rolling sequence; resume where you left off after '
           'missed days. Aim for four main sessions when feasible; optional Recovery + Arms must not displace '
           'one. PRIMARY/ALT: complete one exercise per slot and remove/leave unperformed alternatives unlogged. '
           'Optional slots are not required; do not perform every preloaded entry. Warm up with easy ramp sets. '
           'Compounds about 2 RIR; isolation 1-2; optional arms 2-3. Earn the top rep range twice with stable '
           'form before the smallest load increase. Loads are station-specific starting points from logs through '
           'Sep 30, not mandatory targets. No doubling unilateral loads. After poor sleep or a long gap, '
           'calibrate effort and reduce load/sets if needed. Stop movements that provoke back/radiating symptoms.',
  'exercises': [{'aliases': ['Hammer Curl (Cable)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 35,
                 'rest_seconds': 75,
                 'slot': 'SLOT 1 - BICEPS',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 1 - BICEPS | PRIMARY. Setup: use the same rope and pulley, neutral wrists, elbows '
                          'close to sides. Cues: curl without leaning back or lifting shoulders, lower fully '
                          'under control. Sep 30: 35 for 3x10 at RPE 7.5-8. Hold 35 and build reps before another '
                          'increase. Keep 2-3 reps left on this optional arm day; choose this OR preacher curls, '
                          'not both automatically. Main upper/lower sessions take priority.'},
                {'aliases': ['Preacher Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 65,
                 'rest_seconds': 75,
                 'slot': 'SLOT 1 - BICEPS',
                 'role': 'ALT',
                 'notes': 'SLOT 1 - BICEPS | ALT. Replaces this slot; choose ONE. Setup: align elbow with pivot '
                          'and keep upper arms on the pad. Cues: curl smoothly, control the return and avoid '
                          'forcing the elbow into a hard lockout. Sep 2: 65 for 8/8/10 at RPE 7.5-8.5. Use this '
                          'same machine only; calibrate after the gap and keep 2-3 reps left on the optional arm '
                          'day. Build 3x12 before increasing. Replaces cable hammer curls rather than adding '
                          'three more sets.'},
                {'aliases': ['Triceps Rope Pushdown'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 45,
                 'rest_seconds': 75,
                 'slot': 'SLOT 2 - TRICEPS',
                 'role': 'PRIMARY',
                 'notes': 'SLOT 2 - TRICEPS | PRIMARY. Setup: rope on the same station, elbows near sides and '
                          'wrists neutral. Cues: extend through elbows without shoulder rocking or leaning over '
                          'the stack; control the return. Sep 30: 45 for 3x15 at RPE 7.5-8.5. Repeat with 2-3 '
                          'reps left on the optional arm day before a small increase. This is the main triceps '
                          'slot; other extensions replace these sets, not add to them.'},
                {'aliases': ['Triceps Extension (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 75,
                 'rest_seconds': 75,
                 'slot': 'SLOT 2 - TRICEPS',
                 'role': 'ALT',
                 'notes': 'SLOT 2 - TRICEPS | ALT. Replaces this slot; choose ONE. Setup: seat and pad aligned so '
                          'elbows stay supported and shoulders comfortable. Cues: extend smoothly without forcing '
                          'lockout or leaning through the torso. Sep 16: 75 for 15/12/12 at RPE 8. Hold 75 on '
                          'that machine and build 3x15 with 2-3 reps left. This replaces rope pushdowns in the '
                          'optional arm session. Machine and cable weights are independent.'},
                {'aliases': ['Seated Incline Curl (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 20,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - ARM FINISHER',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - ARM FINISHER | OPTIONAL. Choose at most one optional accessory today. '
                          'Setup: supported incline bench, arms hanging naturally without forcing shoulder '
                          'extension. Cues: keep upper arms still, curl without swinging and lower slowly. Sep '
                          '30: 20 per hand for 2x15 at RPE 7.5-8. Repeat before the smallest load increase, '
                          'keeping 2-3 reps left. This is a two-set optional arm finisher; choose it OR another '
                          'optional arm finisher, not every option.'},
                {'aliases': ['Overhead Triceps Extension (Cable)'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 35,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - ARM FINISHER',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - ARM FINISHER | ALT. Replaces this slot; choose ONE. Setup: stable stance '
                          'with cable behind/above as comfortable, elbows pointed forward/up and ribs controlled. '
                          'Cues: move through elbows without arching or flaring them wide. Sep 2: 35 for '
                          '15/15/10; keep the same station and recalibrate after the gap. Use two optional sets '
                          'with 2-3 reps left, building clean 15s before increasing. Choose one optional arm '
                          'finisher only.'},
                {'aliases': ['Single Arm Tricep Extension (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 20,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - ARM FINISHER',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - ARM FINISHER | ALT. Replaces this slot; choose ONE. Setup: seated or stable '
                          'standing overhead position, one dumbbell and ribs controlled. Cues: bend and extend '
                          'the elbow without forcing shoulder range or arching the back. Sep 30: 20 for 2x15 at '
                          'RPE 7.5-8. Start weaker arm and match reps. Retain 2-3 reps in reserve and repeat '
                          'cleanly before increasing. This replaces another optional arm finisher; it does not '
                          'require extra sets.'},
                {'aliases': ['Reverse Grip Single Triceps Extension'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 75,
                 'slot': 'OPTIONAL - ARM FINISHER',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - ARM FINISHER | ALT. Replaces this slot; choose ONE. Setup: use your same '
                          'single cable handle with a comfortable underhand grip, elbow beside torso and wrist '
                          'straight. Cues: extend through the elbow without shoulder swing or wrist bending; stop '
                          'if grip irritates wrist/elbow. Sep 9: 17.5 for 2x15 at RPE 8-9. Use two optional sets '
                          'at 2-3 reps in reserve, reducing load if necessary. Track this custom exercise '
                          'separately from rope pushdowns.'},
                {'aliases': ['Dead Bug'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - CORE | OPTIONAL. Choose at most one optional accessory today. Setup: lie on '
                          'back, hips/knees bent and ribs controlled; begin with body weight. Cues: slowly reach '
                          'opposite arm/leg only as far as you can keep the trunk still; exhale on the reach. '
                          'Recent logs used 10 reps but varied added load, so standardize to 6-10 per side now. '
                          'Stop before back position changes. Progress reach/control before weight; this is a '
                          'core alternative, not extra arm-day volume.'},
                {'aliases': ['Bird Dog'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: hands under shoulders '
                          'and knees under hips on a stable floor. Cues: reach opposite arm/leg long rather than '
                          'high, keep pelvis level and pause briefly without arching. Sep 23 logged 2x10; v2.2 '
                          'uses 6-10 controlled reps per side without BOSU or added load. Stop for symptoms or '
                          'loss of trunk control. Progress hold quality before reps and choose one core '
                          'movement.'},
                {'aliases': ['Reverse Crunch'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: lie on back with bent '
                          'knees and arms supporting balance. Cues: gently curl pelvis off the floor without '
                          'throwing legs or arching on the descent. Sep 23 reached 25 reps, but v2.2 uses 10-15 '
                          'slower repetitions with a brief pelvic curl pause. Stop before momentum replaces '
                          'control. Progress controlled range first; no ankle weights needed. Choose this instead '
                          'of other core options.'},
                {'aliases': ['Cable Core Pallof Press'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: cable at chest height, '
                          'feet planted and ribs over pelvis. Cues: press hands away while resisting rotation; '
                          'breathe without leaning toward the stack. Sep 10 used 17.5 for 20 reps at RPE 7.5; '
                          'v2.2 uses fewer, slower reps with a 1-2 second extension pause. Work both sides, stop '
                          'before posture changes, and track this new tempo separately. Optional core never '
                          'replaces main lifts.'},
                {'aliases': ['Russian Twist (Weighted)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: feet supported, tall '
                          'comfortable torso and initially no external weight. Cues: use a small controlled '
                          'rotation without swinging, rounding or forcing the low back. September used 22 lb, but '
                          'that is not a required starting load given your back history. Count each side '
                          'consistently, stop for symptoms, and prefer Pallof press if rotation is uncomfortable. '
                          'Optional core choice, not a mandatory progression lift.'},
                {'aliases': ['Kettlebell Around the World'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 22,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. Replaces this slot; choose ONE. Setup: stand tall with soft '
                          'knees and securely pass the kettlebell around the waist, not overhead. Cues: brace '
                          'gently, keep hips/trunk quiet and pass slowly without jerking or leaning. Sep 23: 22 '
                          'for 8/10 at RPE 6; retain only as a light optional coordination/core choice. Count '
                          'complete circles consistently in each direction. Do not chase failure or load; stop if '
                          'your back or grip feels uncomfortable.'}]}]


def normalize(text: str) -> str:
    text = text.lower()
    replacements = {
        "dumbbell": "db",
        "dumbbells": "db",
        "machine": "",
        "cable": "cable",
        "single-arm": "single arm",
        "single-leg": "single leg",
        "iso-lateral": "iso lateral",
        "t-bar": "t bar",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def title_of(template: dict[str, Any]) -> str:
    return str(template.get("title") or template.get("name") or "")


def fetch_all(session: requests.Session, endpoint: str, key: str, page_size: int) -> list[dict[str, Any]]:
    page = 1
    all_items: list[dict[str, Any]] = []
    while True:
        response = session.get(
            f"{BASE_URL}/{endpoint}",
            headers={"api-key": key},
            params={"page": page, "pageSize": page_size},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        items_key = {
            "exercise_templates": "exercise_templates",
            "routine_folders": "routine_folders",
            "routines": "routines",
        }[endpoint]
        all_items.extend(data.get(items_key, []))
        page_count = int(data.get("page_count", 1))
        if page >= page_count:
            return all_items
        page += 1


def api_error(response: requests.Response) -> str:
    try:
        return str(response.json())
    except Exception:
        return response.text


def score_title(candidate: str, aliases: list[str]) -> float:
    c = normalize(candidate)
    best = 0.0
    c_tokens = set(c.split())
    for alias in aliases:
        a = normalize(alias)
        if c == a:
            return 1.0
        ratio = difflib.SequenceMatcher(None, c, a).ratio()
        a_tokens = set(a.split())
        overlap = len(c_tokens & a_tokens) / max(1, len(c_tokens | a_tokens))
        contains_bonus = 0.08 if (a in c or c in a) else 0.0
        best = max(best, 0.72 * ratio + 0.28 * overlap + contains_bonus)
    return min(best, 1.0)


def resolve_template(
    templates: list[dict[str, Any]], aliases: list[str], auto_match: bool
) -> dict[str, Any]:
    # Do not strip equipment names for automatic matching. Machine/cable,
    # decline/flat and supported/unsupported variations have separate histories.
    exact = [t for t in templates if title_of(t).strip().casefold() == aliases[0].strip().casefold()]
    if len(exact) == 1:
        return exact[0]
    if auto_match:
        raise ValueError(f"No unique exact match for {aliases[0]!r}. Rerun without --auto-match to select manually.")

    ranked = sorted(
        ((score_title(title_of(t), aliases), t) for t in templates),
        key=lambda x: x[0],
        reverse=True,
    )
    top = ranked[:8]

    print("\nExercise match needs confirmation:")
    print(f"  Wanted: {aliases[0]}")
    for i, (score, template) in enumerate(top, start=1):
        print(f"  {i}. {title_of(template)}  [id={template.get('id')}]  score={score:.2f}")
    print("  Or paste an exercise_template_id directly. Type q to abort.")

    while True:
        choice = input("Select match: ").strip()
        if choice.lower() == "q":
            raise KeyboardInterrupt
        if choice.isdigit() and 1 <= int(choice) <= len(top):
            return top[int(choice) - 1][1]
        for template in templates:
            if str(template.get("id")) == choice:
                return template
        print("Invalid selection.")


def validate_program() -> None:
    problems: list[str] = []
    if len({r['title'] for r in ROUTINES}) != len(ROUTINES):
        problems.append('Duplicate planned routine title.')

    for routine in ROUTINES:
        total_sets = sum(int(ex["sets_count"]) for ex in routine["exercises"])
        if total_sets > HEVY_ROUTINE_SET_LIMIT:
            problems.append(
                f"{routine['title']}: {total_sets} routine sets exceeds Hevy's {HEVY_ROUTINE_SET_LIMIT}-set ceiling."
            )

        for ex in routine["exercises"]:
            if ex['sets_count'] < 1 or not (1 <= ex['rep_min'] <= ex['rep_max']):
                problems.append(f"Invalid sets/reps: {ex['aliases'][0]}")
            if ex['weight_lb'] is not None and ex['weight_lb'] < 0:
                problems.append(f"Invalid weight: {ex['aliases'][0]}")
            if ex['role'] not in VALID_ROLES:
                problems.append(f"Invalid role: {ex['aliases'][0]}")
            length = len(ex["notes"])
            if not (EXERCISE_NOTE_MIN <= length <= EXERCISE_NOTE_MAX):
                problems.append(
                    f"{routine['title']} / {ex['aliases'][0]}: note is {length} chars; expected {EXERCISE_NOTE_MIN}-{EXERCISE_NOTE_MAX}."
                )
        for slot in {e['slot'] for e in routine['exercises']}:
            entries = [e for e in routine['exercises'] if e['slot'] == slot]
            if sum(e['role'] != ROLE_ALT for e in entries) != 1:
                problems.append(f"{routine['title']} / {slot}: must have exactly one PRIMARY or OPTIONAL anchor.")
            if len({e['sets_count'] for e in entries}) != 1:
                problems.append(f"{routine['title']} / {slot}: alternative set counts differ.")

    if problems:
        print("\nPROGRAM VALIDATION FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        raise ValueError("Fix V2.2 program validation errors before uploading.")


def build_payloads(templates: list[dict[str, Any]], auto_match: bool) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    match_cache: dict[tuple[str, ...], dict[str, Any]] = {}

    for routine in ROUTINES:
        payload_exercises = []
        display_exercises = []
        used_ids: set[str] = set()
        for ex in routine["exercises"]:
            cache_key = tuple(ex["aliases"])
            if cache_key not in match_cache:
                match_cache[cache_key] = resolve_template(templates, ex["aliases"], auto_match)
            template = match_cache[cache_key]
            template_id = str(template.get('id', ''))
            if not template_id or template_id in used_ids:
                raise ValueError(f"Missing/duplicate template ID in {routine['title']}: {ex['aliases'][0]}. Check the selected variations.")
            used_ids.add(template_id)

            sets = [
                normal_set(ex["rep_min"], ex["rep_max"], ex["weight_lb"])
                for _ in range(ex["sets_count"])
            ]
            payload_exercises.append(
                {
                    "exercise_template_id": template["id"],
                    "rest_seconds": ex["rest_seconds"],
                    "notes": ex["notes"],
                    "sets": sets,
                }
            )
            weight_text = "BODYWEIGHT / CALIBRATE: see notes" if ex["weight_lb"] is None else f"{ex['weight_lb']:g} lb"
            display_exercises.append(
                f"[{ex['role']}] {ex['slot']} | {title_of(template)} — "
                f"{ex['sets_count']} x {ex['rep_min']}-{ex['rep_max']} @ {weight_text}; rest {ex['rest_seconds']}s"
            )

        built.append(
            {
                "title": routine["title"],
                "notes": routine["notes"],
                "exercises": payload_exercises,
                "display_exercises": display_exercises,
                "routine_set_count": sum(ex["sets_count"] for ex in routine["exercises"]),
            }
        )
    return built


def get_or_create_folder(
    session: requests.Session, key: str, apply_changes: bool
) -> int | None:
    folders = fetch_all(session, "routine_folders", key, 10)
    for folder in folders:
        if str(folder.get("title", "")).strip().lower() == FOLDER_TITLE.lower():
            return int(folder["id"])

    if not apply_changes:
        return None

    response = session.post(
        f"{BASE_URL}/routine_folders",
        headers={"api-key": key, "Content-Type": "application/json"},
        json={"routine_folder": {"title": FOLDER_TITLE}},
        timeout=30,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Could not create routine folder: {response.status_code} {api_error(response)}")
    data = response.json()
    folder = data.get("routine_folder", data) if isinstance(data, dict) else data
    return int(folder["id"])


def find_existing_routine(
    by_title: dict[str, dict[str, Any]],
    v22_title: str,
) -> tuple[dict[str, Any] | None, str | None]:
    titles = [v22_title, *LEGACY_TITLES.get(v22_title, [])]
    matches = [(by_title[t], t) for t in titles if t in by_title]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple versions match {v22_title}: {[t for _, t in matches]}. Rename/archive the unwanted version and rerun; nothing is chosen automatically.")
    if matches:
        return matches[0]
    return None, None


def preflight_existing(existing: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    relevant = {t for r in ROUTINES for t in [r['title'], *LEGACY_TITLES[r['title']]]}
    by_title: dict[str, dict[str, Any]] = {}
    for r in existing:
        title = str(r.get('title', ''))
        if title not in relevant:
            continue
        if title in by_title:
            raise RuntimeError(f"Duplicate routine title {title!r}; refusing an ambiguous overwrite.")
        by_title[title] = r
    for r in ROUTINES:
        find_existing_routine(by_title, r['title'])
    return by_title


def backup_routines(existing: list[dict[str, Any]], directory: str) -> Path:
    by_title = preflight_existing(existing)
    affected = [find_existing_routine(by_title, r['title'])[0] for r in ROUTINES]
    directory_path = Path(directory).expanduser()
    directory_path.mkdir(parents=True, exist_ok=True)
    path = directory_path / ('hevy_before_v22_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    with path.open('x', encoding='utf-8') as f:
        json.dump({'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                   'note': 'Reference snapshot of API-returned routines; not an automatic restore payload.',
                   'routines': [r for r in affected if r is not None]}, f, indent=2)
    return path


def upsert_routines(
    session: requests.Session,
    key: str,
    folder_id: int,
    built: list[dict[str, Any]],
    existing: list[dict[str, Any]] | None = None,
) -> None:
    if existing is None:
        existing = fetch_all(session, "routines", key, 10)
    by_title = preflight_existing(existing)

    for routine in built:
        title = routine["title"]
        common = {
            "title": title,
            "notes": routine["notes"],
            "exercises": routine["exercises"],
        }

        existing_routine, matched_title = find_existing_routine(by_title, title)
        if existing_routine is not None:
            routine_id = existing_routine["id"]
            # Hevy's current PUT routine schema does not include folder_id.
            body = {"routine": common}
            response = session.put(
                f"{BASE_URL}/routines/{routine_id}",
                headers={"api-key": key, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            action = "MIGRATED" if matched_title != title else "UPDATED"
        else:
            body = {"routine": {**common, "folder_id": folder_id}}
            response = session.post(
                f"{BASE_URL}/routines",
                headers={"api-key": key, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            action = "CREATED"

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"{action} failed for {title}: {response.status_code} {api_error(response)}. Earlier successful writes may remain. Inspect Hevy and rerun; exact V2.2 titles update in place."
            )
        if action == "MIGRATED":
            print(f"MIGRATED: {matched_title} -> {title}")
        else:
            print(f"{action}: {title}")


def print_workout_rules() -> None:
    print("\n=== HOW TO USE V2.2 IN HEVY ===")
    print("1. PRIMARY = preferred movement for the slot.")
    print("2. ALT = approved substitute. Complete ONE exercise for that slot, not both.")
    print("3. OPTIONAL = actual add-on work; skip when recovery/time do not support it.")
    print("4. Leave unused ALT exercises untouched in the live workout.")
    print("5. If you complete an ALT, do not return later to the PRIMARY when it becomes free.")
    print("6. Machine/variation weights are independent. New equipment starts with a 2-3 RIR calibration set.")
    print("7. Follow Upper A > Lower A > Upper B > Lower B; resume the sequence after missed days.")
    print("8. Recovery + Arms is optional: six primary sets, plus at most ONE two-set accessory (eight total).")
    print("9. Main routine planned sets: Upper A 17; Lower A 12; Upper B 16; Lower B 15, before optional work.")


def preview_program() -> None:
    print('V2.2 OFFLINE PREVIEW - no credentials, API calls or changes. All loads are pounds as logged.')
    for r in ROUTINES:
        print('\n' + r['title'] + '\n' + r['notes'])
        for e in r['exercises']:
            load = f"{e['weight_lb']:g} lb" if e['weight_lb'] is not None else 'bodyweight/calibrate per notes'
            print(f"\n  {e['aliases'][0]}: {e['sets_count']} x {e['rep_min']}-{e['rep_max']} @ {load}; rest {e['rest_seconds']}s")
            print('  ' + e['notes'])
    print_workout_rules()


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Alex Core-4 V2 routines to flexible-slot V2.2 in Hevy")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create/update routines. Without this flag, the script is a dry run.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip final UPLOAD confirmation (only used with --apply).",
    )
    parser.add_argument(
        "--auto-match",
        action="store_true",
        help="Noninteractive exact-title matching only. Missing/ambiguous matches abort; fuzzy guesses are never automatic.",
    )
    parser.add_argument('--preview', action='store_true', help='Show all exercise notes and prescriptions offline without an API key.')
    parser.add_argument('--backup-dir', default='hevy_backups', help='Local directory for the pre-upload routine snapshot.')
    args = parser.parse_args()
    if args.preview and args.apply:
        parser.error('--preview and --apply cannot be combined.')

    # Validate the local program before asking for credentials or touching the API.
    validate_program()
    if args.preview:
        preview_program()
        return 0
    if requests is None:
        print('Install the upload dependency: python3 -m pip install requests')
        return 2

    key = os.getenv("HEVY_API_KEY", "").strip()
    if not key:
        key = getpass.getpass("Hevy API key (hidden): ").strip()
    if not key:
        print("No API key supplied.")
        return 2

    session = requests.Session()

    print("Checking Hevy API key...")
    response = session.get(f"{BASE_URL}/user/info", headers={"api-key": key}, timeout=30)
    if response.status_code != 200:
        print(f"API authentication failed: {response.status_code} {api_error(response)}")
        return 3
    user_data = response.json()
    user = user_data.get("user", user_data) if isinstance(user_data, dict) else user_data
    username = user.get("username") if isinstance(user, dict) else None
    print(f"Authenticated{f' as {username}' if username else ''}.")

    print("Fetching exercise templates...")
    templates = fetch_all(session, "exercise_templates", key, 100)
    print(f"Loaded {len(templates)} exercise templates.")

    try:
        built = build_payloads(templates, args.auto_match)
    except KeyboardInterrupt:
        print("\nAborted before making changes.")
        return 130

    print("\n=== CORE-4 V2.2 FLEXIBLE-SLOT UPLOAD PLAN ===")
    for routine in built:
        print(f"\n{routine['title']}  [routine contains {routine['routine_set_count']} pre-loaded sets]")
        for line in routine["display_exercises"]:
            print(f"  - {line}")

    print_workout_rules()

    # Resolve every migration conflict in dry-run and before ANY write.
    existing = fetch_all(session, 'routines', key, 10)
    by_title = preflight_existing(existing)
    for r in built:
        target, matched = find_existing_routine(by_title, r['title'])
        print(f"{'UPDATE ' + str(target['id']) + ' (' + str(matched) + ')' if target else 'CREATE'} -> {r['title']}")

    if not args.apply:
        print("\nDRY RUN ONLY — nothing was written to Hevy.")
        print("Review every exercise-template match above, especially custom/machine exercises.")
        print("If everything looks correct, run:")
        print("  python hevy_core4_v22_flexible_slots.py --apply")
        return 0

    if not args.yes:
        print("\nThis will update five routine templates. Existing V2/V2.1 routines migrate in place to V2.2 by ID; completed workouts are not edited.")
        print("The update adds pre-loaded ALT exercises; those are substitutions, not prescribed extra volume.")
        confirmation = input("Type UPLOAD to continue: ").strip()
        if confirmation != "UPLOAD":
            print("Cancelled. Nothing was written.")
            return 0

    # Refresh after interactive review, back up, then write without automatic retries.
    existing = fetch_all(session, 'routines', key, 10)
    by_title = preflight_existing(existing)
    backup_path = backup_routines(existing, args.backup_dir)
    print(f'Pre-upload routine snapshot saved: {backup_path}')
    need_create = any(find_existing_routine(by_title, r['title'])[0] is None for r in built)
    folder_id = get_or_create_folder(session, key, apply_changes=True) if need_create else 0
    if folder_id is None:
        raise RuntimeError("Could not resolve Core-4 folder ID.")

    upsert_routines(session, key, folder_id, built, existing)
    print("\nDone. Open Hevy and verify exercise choices, imperial weights, notes and routine order before the first V2.2 session.")
    print("Most important behavior: complete ONE exercise per PRIMARY/ALT slot and leave unused alternatives untouched.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nStopped. If uploading had begun, inspect Hevy before rerunning; earlier writes may remain.')
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(5)
