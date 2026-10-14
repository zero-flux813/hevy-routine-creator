#!/usr/bin/env python3
"""CORE-4 V3 — Hybrid Hypertrophy: safe Hevy routine uploader.

Generated from the uploaded V2.2 uploader, V3-approved plan and Hevy workbook
through October 13, 2026. All weights are lb in the offline specification and
converted to kg only for the official Hevy routine payload.

Four NEW routines in a NEW folder by default; V2.2 and Recovery + Arms stay intact.
On rerun only exact V3 titles are updated. Completed workouts are never edited.

Commands:
    pip install requests
    python hevy_core4_v3_hybrid_upload.py --preview
    python hevy_core4_v3_hybrid_upload.py                 # online dry run; asks API key
    python hevy_core4_v3_hybrid_upload.py --apply         # asks UPLOAD confirmation
    python hevy_core4_v3_hybrid_upload.py --apply --yes   # skips confirmation
    python hevy_core4_v3_hybrid_upload.py --apply --auto-match

Get your HEVY_API_KEY from https://hevy.com/settings?developer (Hevy Pro).
Set HEVY_API_KEY in your environment or paste when securely prompted. Never
paste it into a script or upload it into a chat.

Each ALT is preloaded as an EXERCISE alternative, not as an extra muscle-building
set. Hevy does not model exclusive-choice slot groups; you must complete exactly
one variant per slot when recording the workout.
"""
from __future__ import annotations
import argparse
import difflib
import getpass
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
try:
    import requests
except ImportError:
    requests = None

BASE_URL = 'https://api.hevyapp.com/v1'
FOLDER_TITLE = 'Hybrid Core-4 : V3'
LB_PER_KG = 2.2046226218
HEVY_ROUTINE_SET_LIMIT = 150
EXERCISE_NOTE_MIN, EXERCISE_NOTE_MAX = 300, 600
PROGRAM_RULES = 'V3 HYBRID. Rolling sequence: Upper A > Lower A > Upper B > Lower B; resume after missed days. Only ONE movement per numbered slot: PRIMARY or ALT, never both. Optional CORE is not required. Warm-up sets are separate. Log unused ALT movements as unperformed. Big lifts generally 1-3 RIR; isolation 1-2 RIR; never force pain. Compounds rest 2-3 min, isolations 60-90 sec. Increase weight only after target reps with consistent form and reserve; small clean rep gains count. All dumbbell weights are PER HAND, plate-loaded iso movements PER SIDE, others follow your logged exact machine convention; never double unilateral values. Upper A incline uses 3 heavy sets and one lighter back-off after full rest. Loads come from the exercise history exported through Oct 13, 2026, not mandatory targets. Stop or modify any movement causing back pain, radiating symptoms, numbness or weakness.'
ROUTINES: list[dict[str, Any]] = [{'title': 'Upper A - Chest + Triceps V3',
  'focus': 'Chest first: 4-set incline anchor (3 heavy + one back-off), flys, row, pulldown, lateral '
           'delts, triceps. No direct biceps.',
  'required_sets': 21,
  'exercises': [{'aliases': ['Incline Bench Press (Dumbbell)'],
                 'sets_count': 4,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': 52.5,
                 'rest_seconds': 180,
                 'slot': '01 - INCLINE ANCHOR',
                 'role': 'PRIMARY',
                 'notes': '01 - INCLINE ANCHOR | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Bench 15-30 degrees, stable feet and shoulder blades; load per hand. '
                          'Cues: Lower under control, forearms stacked, press without bouncing or rib '
                          'flare. 4x6-10; 1-2 RIR; 180s rest. Add reps before load; track each machine '
                          'independently. Progress tip: Special set 4 is BACK-OFF: 45 lb/hand for 8-12 at '
                          '1-2 RIR after a full rest; not a drop set. 3 heavy sets target 6-10. Oct 8: '
                          '52.5 for 8/8/8/8, so do not jump to 55 yet. Latest Oct 8, 2026: 52.5x8, 52.5x8, '
                          '52.5x8, 52.5x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 52.5x8, 52.5x8, 52.5x8, 52.5x8.',
                 'set_loads_lb': [52.5, 52.5, 52.5, 45]},
                {'aliases': ['Incline Chest Press (Machine)'],
                 'sets_count': 4,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 45,
                 'rest_seconds': 150,
                 'slot': '01 - INCLINE ANCHOR',
                 'role': 'ALT',
                 'notes': '01 - INCLINE ANCHOR | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Match seat and grip; ensure a comfortable low-incline path; machine load '
                          'is station-specific. Cues: Maintain rib control, a smooth lowering phase and '
                          'even arm drive. 4x8-12; 1-2 RIR; 150s rest. Add reps before load; track each '
                          'machine independently. Progress tip: Oct 5: 45 for 8/8. If using this ALT, use '
                          '3 regular sets and a lighter fourth set adjusted by feel; note change for 4th '
                          'set. Calibration required because V3 has more sets than your log. Latest Oct 5, '
                          '2026: 45x8, 45x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 5, 2026: 45x8, 45x8.'},
                {'aliases': ['Incline Bench Press (Barbell)'],
                 'sets_count': 4,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 180,
                 'slot': '01 - INCLINE ANCHOR',
                 'role': 'ALT',
                 'notes': '01 - INCLINE ANCHOR | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Use safeties or spotter and a low-incline bench; total bar weight. Cues: '
                          'Touch at a consistent location; keep elbows comfortable and avoid bouncing. '
                          '4x6-10; 1-2 RIR; 180s rest. Add reps before load; track each machine '
                          'independently. Progress tip: Last barbell-incline log is from April; calibrate '
                          'from about 2-3 RIR. Fourth set may be 10-15% lighter, 8-12 reps. Do not '
                          'transfer 52.5 DB load. Latest Apr 6, 2026: 115x8, 125x6, 130x4, 115x7. Old '
                          'exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Apr 6, 2026: 115x8, 125x6, 130x4, 115x7. Old exposure; recalibrate '
                           'before using historical numbers.'},
                {'aliases': ['Iso-Lateral Low Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 120,
                 'slot': '02 - HORIZONTAL ROW',
                 'role': 'PRIMARY',
                 'notes': '02 - HORIZONTAL ROW | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Chest supported, same seat and handles; load logged per side. Cues: '
                          'Elbows toward lower ribs with controlled reach; do not rotate torso or shrug. '
                          'Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on '
                          '2 comparable sessions before the smallest increment; keep separate loads for '
                          'each station. Progress tip: Oct 1: 55/side for 12/12/12 with final RPE 9. '
                          'Repeat at stable 1-2 RIR before a small increase. Latest Oct 1, 2026: 55x12, '
                          '55x12, 55x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 1, 2026: 55x12, 55x12, 55x12.'},
                {'aliases': ['Seated Row (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': '02 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '02 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Set seat/chest support and grip consistently on same machine. Cues: '
                          'Control the forward reach and pull without heaving or lifting your chest. Work '
                          '3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 8: 115 for 12/12/12; final RPE 9.5. Hold until '
                          'quality and reserve improve. Latest Oct 8, 2026: 115x12, 115x12, 115x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 115x12, 115x12, 115x12.'},
                {'aliases': ['Seated Cable Row - V Grip (Cable)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 42.5,
                 'rest_seconds': 120,
                 'slot': '02 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '02 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Record exact dual-stack/pulley setup; logged stack weight may not equal '
                          'resistance. Cues: Sit braced, pull toward low ribs, avoid rocking or rounding '
                          'lumbar spine. Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Oct 12: 42.5 stack convention '
                          'for 10/10/10 at RPE 8. Build to 3x12. Latest Oct 12, 2026: 42.5x10, 42.5x10, '
                          '42.5x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 42.5x10, 42.5x10, 42.5x10.'},
                {'aliases': ['Chest Supported T Bar Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 60,
                 'rest_seconds': 120,
                 'slot': '02 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '02 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Keep sternum on support, grip consistent and feet braced. Cues: Pull '
                          'elbows behind torso under control without lifting chest from pad. Work 3 sets '
                          'of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 5: 60 for 10/10/10. Keep support and full range '
                          'consistent. Latest Oct 5, 2026: 60x10, 60x10, 60x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 5, 2026: 60x10, 60x10, 60x10.'},
                {'aliases': ['Dumbbell Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 40,
                 'rest_seconds': 120,
                 'slot': '02 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '02 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Support free hand on a bench; keep hips square and back comfortable; per '
                          'hand. Cues: Reach the weight downward, then row elbow toward hip without '
                          'twisting. Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Sep 5: 40/hand for 10/10/10. Use '
                          'a stable support and protect lower back. Latest Sep 5, 2026: 40x10, 40x10, '
                          '40x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 5, 2026: 40x10, 40x10, 40x10.'},
                {'aliases': ['Iso-Lateral Chest Press (Machine)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 50,
                 'rest_seconds': 150,
                 'slot': '03 - HORIZONTAL CHEST PRESS',
                 'role': 'PRIMARY',
                 'notes': '03 - HORIZONTAL CHEST PRESS | PRIMARY. Choose this PRIMARY or ONE ALT; never '
                          'both. Setup: Match your actual seat, handles and arm path; plates logged per '
                          'side. Cues: Control lowering and stop before shoulder discomfort; avoid rib '
                          'flare. Work 2 sets of 8-12 reps, aim 1-2 RIR, rest 150s. Build clean top-range '
                          'reps on 2 comparable sessions before the smallest increment; keep separate '
                          'loads for each station. Progress tip: Oct 1: 50/side for 12/12/12, 7.5-8.5 RPE; '
                          'two V3 sets. Consider the next small increment if 1-2 RIR remains. Latest Oct '
                          '1, 2026: 50x12, 50x12, 50x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 1, 2026: 50x12, 50x12, 50x12.'},
                {'aliases': ['Bench Press (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 40,
                 'rest_seconds': 150,
                 'slot': '03 - HORIZONTAL CHEST PRESS',
                 'role': 'ALT',
                 'notes': '03 - HORIZONTAL CHEST PRESS | ALT. REPLACES this slot primary; choose ONE '
                          'variation. Setup: Flat bench, stable feet and shoulder blades; weight per hand. '
                          'Cues: Lower through comfortable shoulder range then press evenly without '
                          'clashing bells. Work 2 sets of 8-12 reps, aim 1-2 RIR, rest 150s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Sep 5: 40/hand for 10/10/10. Use '
                          'two prescribed sets and build to 12. Latest Sep 5, 2026: 40x10, 40x10, 40x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 5, 2026: 40x10, 40x10, 40x10.'},
                {'aliases': ['Bench Press (Barbell)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 180,
                 'slot': '03 - HORIZONTAL CHEST PRESS',
                 'role': 'ALT',
                 'notes': '03 - HORIZONTAL CHEST PRESS | ALT. REPLACES this slot primary; choose ONE '
                          'variation. Setup: Stable flat bench and foot plant; safeties or spotter; total '
                          'load including bar. Cues: Touch consistently without bounce; press with '
                          'shoulder blades stable. Work 2 sets of 8-12 reps, aim 1-2 RIR, rest 180s. Build '
                          'clean top-range reps on 2 comparable sessions before the smallest increment; '
                          'keep separate loads for each station. Progress tip: Sep 22: 115 total for '
                          '10/9/7; only two sets now. Do not assume 3x12 readiness. Latest Sep 22, 2026: '
                          '115x10, 115x9, 115x7.',
                 'group': 'required',
                 'latest': 'Latest Sep 22, 2026: 115x10, 115x9, 115x7.'},
                {'aliases': ['Lat Pulldown (Machine)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': '04 - VERTICAL PULL',
                 'role': 'PRIMARY',
                 'notes': '04 - VERTICAL PULL | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Secure thigh pad and match exact selectorized machine/grip. Cues: Lean '
                          'slightly and pull elbows to sides; no torso heave or neck reach. Work 2 sets of '
                          '8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 1: 115 for 10/10/9, RPE up to 9.5. Hold 115 and accumulate '
                          'clean reps. Latest Oct 1, 2026: 115x10, 115x10, 115x9.',
                 'group': 'required',
                 'latest': 'Latest Oct 1, 2026: 115x10, 115x10, 115x9.'},
                {'aliases': ['Lat Pulldown (Cable)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 70,
                 'rest_seconds': 120,
                 'slot': '04 - VERTICAL PULL',
                 'role': 'ALT',
                 'notes': '04 - VERTICAL PULL | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Keep station, attachment and stack convention consistent. Cues: Draw '
                          'elbows toward ribs with a stable torso; resist the return. Work 2 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 8: 70 for 12/12/12 at 8-8.5 RPE; consider next increment '
                          'conservatively. Latest Oct 8, 2026: 70x12, 70x12, 70x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 70x12, 70x12, 70x12.'},
                {'aliases': ['Iso Pulldown'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 65,
                 'rest_seconds': 120,
                 'slot': '04 - VERTICAL PULL',
                 'role': 'ALT',
                 'notes': '04 - VERTICAL PULL | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Same plate-loaded iso machine; use per-side logging convention. Cues: '
                          'Lead with elbows toward hips and resist the stretch without twisting. Work 2 '
                          'sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 12: 65/side 12/12/12; load and range do not equal '
                          'selectorized pulldown. Latest Oct 12, 2026: 65x12, 65x12, 65x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 65x12, 65x12, 65x12.'},
                {'aliases': ['Single Arm Lat Pulldown'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': None,
                 'rest_seconds': 120,
                 'slot': '04 - VERTICAL PULL',
                 'role': 'ALT',
                 'notes': '04 - VERTICAL PULL | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Confirm cable ratio/station; load not comparable to iso pulldown. Cues: '
                          'Keep torso square, draw elbow toward hip and match weaker-side reps. Work 2 '
                          'sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Unfamiliar pulley ratio; recalibrate from 2-3 RIR. Old '
                          '120 stack log is not transferable. Latest Aug 6, 2026: 120x8, 120x7, 120x6. Old '
                          'exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Aug 6, 2026: 120x8, 120x7, 120x6. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Cable Fly Crossovers'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 90,
                 'slot': '05 - HIGH-TO-LOW FLY',
                 'role': 'PRIMARY',
                 'notes': '05 - HIGH-TO-LOW FLY | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Use HIGH pulleys for the approved high-to-low fly; station/load ratio '
                          'matters. Cues: Soft elbows; arc hands downward/inward, avoiding deep forced '
                          'stretch or shrug. 3x12-15; 1-2 RIR; 90s rest. Add reps before load; track each '
                          'machine independently. Progress tip: Priority fly slot: select HIGH pulley '
                          'angle. May log 20 for 18/18/12 used an unspecified path; start with 2 RIR, '
                          'record height and exact stack. Latest May 30, 2026: 20x18, 20x18, 20x12. Old '
                          'exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest May 30, 2026: 20x18, 20x18, 20x12. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Chest Fly (Machine)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 15,
                 'weight_lb': 85,
                 'rest_seconds': 90,
                 'slot': '05 - HIGH-TO-LOW FLY',
                 'role': 'ALT',
                 'notes': '05 - HIGH-TO-LOW FLY | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Set handles to chest height and match machine/seat. Cues: Keep torso '
                          'fixed; bring arms inward with smooth stretch and squeeze. Work 3 sets of 12-15 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 3: 85 for 15/15/12; same chest fly machine only. Latest Sep '
                          '3, 2026: 85x15, 85x15, 85x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 3, 2026: 85x15, 85x15, 85x12.'},
                {'aliases': ['Chest Fly (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 15,
                 'weight_lb': 25,
                 'rest_seconds': 90,
                 'slot': '05 - HIGH-TO-LOW FLY',
                 'role': 'ALT',
                 'notes': '05 - HIGH-TO-LOW FLY | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Flat bench, stable shoulder blades; dumbbell load per hand. Cues: Soft '
                          'elbows; lower only to a comfortable stretch and lift without turning it into a '
                          'press. Work 3 sets of 12-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range '
                          'reps on 2 comparable sessions before the smallest increment; keep separate '
                          'loads for each station. Progress tip: Sep 30: 25/hand for 15/15; third set '
                          'requires re-calibration. Latest Sep 30, 2026: 25x15, 25x15.',
                 'group': 'required',
                 'latest': 'Latest Sep 30, 2026: 25x15, 25x15.'},
                {'aliases': ['Decline Chest Fly (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 15,
                 'weight_lb': 27.5,
                 'rest_seconds': 90,
                 'slot': '05 - HIGH-TO-LOW FLY',
                 'role': 'ALT',
                 'notes': '05 - HIGH-TO-LOW FLY | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Secure feet and use modest decline; load per dumbbell. Cues: Soft elbows '
                          'and a controlled comfortable arc; do not force the shoulder behind torso. Work '
                          '3 sets of 12-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 8: 30/hand gave 10/8/8; 27.5 produced 3x12 Sep 28. '
                          'Use 27.5 to target 12-15. Latest Oct 8, 2026: 30x10, 30x8, 30x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 30x10, 30x8, 30x8.'},
                {'aliases': ['Single Arm Lateral Raise (Cable)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 10,
                 'rest_seconds': 75,
                 'slot': '06 - SIDE DELTS',
                 'role': 'PRIMARY',
                 'notes': '06 - SIDE DELTS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Hold the frame; fix pulley height, body distance and start-side. Cues: Lead '
                          'with elbows, avoid shrug and leaning; lower slowly and match sides. Work 3 sets '
                          'of 12-20 reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 12: 10 for 20/18/16 at 8-8.5 RPE; hold 10 and bring '
                          'later sets up. Latest Oct 12, 2026: 10x20, 10x18, 10x16.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 10x20, 10x18, 10x16.'},
                {'aliases': ['Seated Lateral Raise (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': '06 - SIDE DELTS',
                 'role': 'ALT',
                 'notes': '06 - SIDE DELTS | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Sit stable with bells slightly forward; per dumbbell. Cues: Soft elbows, raise '
                          'with delts not traps, no torso swing; control descent. Work 3 sets of 12-20 '
                          'reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 3: 12.5x20 then 15x12 twice; 12.5 is safer strict baseline. '
                          'Latest Sep 3, 2026: 12.5x20, 15x12, 15x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 3, 2026: 12.5x20, 15x12, 15x12.'},
                {'aliases': ['Lateral Raise (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': None,
                 'rest_seconds': 75,
                 'slot': '06 - SIDE DELTS',
                 'role': 'ALT',
                 'notes': '06 - SIDE DELTS | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Stand tall with soft knees, shoulders neutral; per dumbbell. Cues: Lead elbows, '
                          'stop before shrugging and do not use momentum to reach higher. Work 3 sets of '
                          '12-20 reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Jul 30 older 20x16 log; re-calibrate strict load based on current '
                          'form. Latest Jul 30, 2026: 20x16, 20x16. Old exposure; recalibrate before using '
                          'historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Jul 30, 2026: 20x16, 20x16. Old exposure; recalibrate before using '
                           'historical numbers.'},
                {'aliases': ['Triceps Rope Pushdown'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 45,
                 'rest_seconds': 75,
                 'slot': '07 - TRICEPS PUSHDOWN',
                 'role': 'PRIMARY',
                 'notes': '07 - TRICEPS PUSHDOWN | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Use same rope/pulley; set upper arms close to sides. Cues: Extend elbows '
                          'without rocking shoulders or torso, then return slowly. Work 4 sets of 10-15 '
                          'reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 30: 45 for 3x15 at 7.5-8.5 RPE. V3 adds a fourth set; retain '
                          '45 initially and adjust if reps drop. Latest Sep 30, 2026: 45x15, 45x15, 45x15.',
                 'group': 'required',
                 'latest': 'Latest Sep 30, 2026: 45x15, 45x15, 45x15.'},
                {'aliases': ['Triceps Extension (Machine)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 75,
                 'rest_seconds': 75,
                 'slot': '07 - TRICEPS PUSHDOWN',
                 'role': 'ALT',
                 'notes': '07 - TRICEPS PUSHDOWN | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Match seat and elbow pads to the machine; stack is station-specific. '
                          'Cues: Keep upper arms supported, extend without slamming, avoid painful '
                          'lockout. Work 4 sets of 10-15 reps, aim 1-2 RIR, rest 75s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Sep 16: 75 for 15/12/12. Build '
                          'all four sets conservatively; not equivalent to cable. Latest Sep 16, 2026: '
                          '75x15, 75x12, 75x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 16, 2026: 75x15, 75x12, 75x12.'},
                {'aliases': ['Single Arm Triceps Pushdown (Cable)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 75,
                 'slot': '07 - TRICEPS PUSHDOWN',
                 'role': 'ALT',
                 'notes': '07 - TRICEPS PUSHDOWN | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: One handle, same pulley; brace torso and keep elbow by side. Cues: '
                          'Straighten elbow with wrist neutral; no shoulder swing; match arms. Work 4 sets '
                          'of 10-15 reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Only older May data; work weaker side first and '
                          'calibrate per arm. Latest May 6, 2026: 15x12, 15x10. Old exposure; recalibrate '
                          'before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest May 6, 2026: 15x12, 15x10. Old exposure; recalibrate before using '
                           'historical numbers.'}],
  'notes': 'Chest first: 4-set incline anchor (3 heavy + one back-off), flys, row, pulldown, lateral '
           'delts, triceps. No direct biceps. V3 HYBRID. Rolling sequence: Upper A > Lower A > Upper B > '
           'Lower B; resume after missed days. Only ONE movement per numbered slot: PRIMARY or ALT, never '
           'both. Optional CORE is not required. Warm-up sets are separate. Log unused ALT movements as '
           'unperformed. Big lifts generally 1-3 RIR; isolation 1-2 RIR; never force pain. Compounds rest '
           '2-3 min, isolations 60-90 sec. Increase weight only after target reps with consistent form and '
           'reserve; small clean rep gains count. All dumbbell weights are PER HAND, plate-loaded iso '
           'movements PER SIDE, others follow your logged exact machine convention; never double '
           'unilateral values. Upper A incline uses 3 heavy sets and one lighter back-off after full rest. '
           'Loads come from the exercise history exported through Oct 13, 2026, not mandatory targets. '
           'Stop or modify any movement causing back pain, radiating symptoms, numbness or weakness.'},
 {'title': 'Lower A - Quads + Biceps V3',
  'focus': 'Quad-dominant compounds and isolations first; add direct neutral-grip biceps after calves and '
           'hip abduction.',
  'required_sets': 18,
  'exercises': [{'aliases': ['Leg Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 250,
                 'rest_seconds': 180,
                 'slot': '01 - QUAD COMPOUND',
                 'role': 'PRIMARY',
                 'notes': '01 - QUAD COMPOUND | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Use same machine and foot stance; hips/pelvis against backrest. Cues: '
                          'Lower only until before pelvic tuck, drive evenly, no bounce or hard knee lock. '
                          'Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 180s. Build clean top-range reps on '
                          '2 comparable sessions before the smallest increment; keep separate loads for '
                          'each station. Progress tip: Oct 9: 250 for 12/12/12 at 7.5-8.5 RPE; repeat to '
                          'confirm then try smallest increase. Latest Oct 9, 2026: 250x12, 250x12, 250x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 250x12, 250x12, 250x12.'},
                {'aliases': ['Hack Squat (Machine)'],
                 'sets_count': 3,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': 215,
                 'rest_seconds': 180,
                 'slot': '01 - QUAD COMPOUND',
                 'role': 'ALT',
                 'notes': '01 - QUAD COMPOUND | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Shoulder-width feet; stable heel contact and comfortable platform '
                          'position. Cues: Knees track naturally; go only as deep as pelvis stays stable; '
                          'no bouncing. Work 3 sets of 6-10 reps, aim 1-2 RIR, rest 180s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Oct 2: 215 for 10/10/10 at 8-8.5 '
                          'RPE; repeat and progress cautiously. Latest Oct 2, 2026: 215x10, 215x10, '
                          '215x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 2, 2026: 215x10, 215x10, 215x10.'},
                {'aliases': ['Leg Press Horizontal (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': None,
                 'rest_seconds': 180,
                 'slot': '01 - QUAD COMPOUND',
                 'role': 'ALT',
                 'notes': '01 - QUAD COMPOUND | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Keep seat and foot stance repeatable; horizontal machine has separate '
                          'load history. Cues: Control eccentric with hips supported, avoid low-back '
                          'rounding. Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 180s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Last logged Apr 15 at 160; very '
                          'different station, recalibrate. Latest Apr 15, 2026: 160x10, 160x10, 160x12. '
                          'Old exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Apr 15, 2026: 160x10, 160x10, 160x12. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Single Leg Extensions'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 50,
                 'rest_seconds': 90,
                 'slot': '02 - QUAD ISOLATION',
                 'role': 'PRIMARY',
                 'notes': '02 - QUAD ISOLATION | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Align knee with machine pivot; pad just above ankle; load logged per '
                          'leg. Cues: Begin with weaker leg, extend smoothly and pause, no hip lifting. '
                          'Work 3 sets of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on '
                          '2 comparable sessions before the smallest increment; keep separate loads for '
                          'each station. Progress tip: Oct 9: 50 for 14/12/12; hold until 3x15, then '
                          'increment. Log per leg. Latest Oct 9, 2026: 50x14, 50x12, 50x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 50x14, 50x12, 50x12.'},
                {'aliases': ['Leg Extension (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 90,
                 'slot': '02 - QUAD ISOLATION',
                 'role': 'ALT',
                 'notes': '02 - QUAD ISOLATION | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Use bilateral station with knees aligned to pivot and pelvis planted. '
                          'Cues: Extend without kicking, squeeze quadriceps briefly and control lowering. '
                          '3x10-15; 1-2 RIR; 90s rest. Add reps before load; track each machine '
                          'independently. Progress tip: Last logged Apr 28: 105 for 15x3, but this '
                          'bilateral machine needs fresh 2 RIR calibration. Latest Apr 28, 2026: 105x15, '
                          '105x15, 105x15, 65x10. Old exposure; recalibrate before using historical '
                          'numbers.',
                 'group': 'required',
                 'latest': 'Latest Apr 28, 2026: 105x15, 105x15, 105x15, 65x10. Old exposure; recalibrate '
                           'before using historical numbers.'},
                {'aliases': ['Seated Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 120,
                 'rest_seconds': 90,
                 'slot': '03 - LEG CURL',
                 'role': 'PRIMARY',
                 'notes': '03 - LEG CURL | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Secure thigh pad; knee at machine pivot, hips remain seated. Cues: Curl through '
                          'comfortable range, brief squeeze and slow return. Work 3 sets of 8-12 reps, aim '
                          '1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Oct '
                          '9: 120 for 12/12/10. Earn 12/12/12 twice before increasing. Latest Oct 9, 2026: '
                          '120x12, 120x12, 120x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 120x12, 120x12, 120x10.'},
                {'aliases': ['Lying Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 75,
                 'rest_seconds': 90,
                 'slot': '03 - LEG CURL',
                 'role': 'ALT',
                 'notes': '03 - LEG CURL | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Knee aligned with pivot, pad above heels, hips on bench. Cues: Curl without '
                          'lumbar arch, hips lifting or swinging; controlled descent. Work 3 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 13: 75 for 12/12/8. Calibrate third set to preserve RIR. '
                          'Latest Oct 13, 2026: 75x12, 75x12, 75x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 75x12, 75x12, 75x8.'},
                {'aliases': ['Standing Leg Curls'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': '03 - LEG CURL',
                 'role': 'ALT',
                 'notes': '03 - LEG CURL | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Use same standing leg-curl station; align knee and stabilize torso. Cues: Match '
                          'weaker leg; curl without hip movement or lumbar extension. Work 3 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 15: 55 for 12/12/10; track one leg at a time. Latest Oct 6, '
                          '2026: 55x12, 55x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 6, 2026: 55x12, 55x12.'},
                {'aliases': ['Calf Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 110,
                 'rest_seconds': 90,
                 'slot': '04 - CALVES',
                 'role': 'PRIMARY',
                 'notes': '04 - CALVES | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Secure forefoot and seat position on same calf/leg-press setup. Cues: '
                          'Controlled ankle stretch and full rise; no bouncing or knee pumping. Work 3 '
                          'sets of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 9: 110 for 15/15/15 with final RPE 8.5. Repeat then '
                          'consider a small increase. Latest Oct 9, 2026: 110x15, 110x15, 110x15.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 110x15, 110x15, 110x15.'},
                {'aliases': ['Standing Calf Raise (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': '04 - CALVES',
                 'role': 'ALT',
                 'notes': '04 - CALVES | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Stable forefoot, shoulders under pads, knees softly extended. Cues: Pause at '
                          'stretch and top; avoid bouncing or torso motion. Work 3 sets of 10-15 reps, aim '
                          '1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Sep '
                          '29: 55 for 15/15/15 but last RPE 9.5; consolidate quality before increasing. '
                          'Latest Oct 13, 2026: 60x12, 60x12, 60x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 60x12, 60x12, 60x10.'},
                {'aliases': ['Calf Extension (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 80,
                 'rest_seconds': 90,
                 'slot': '04 - CALVES',
                 'role': 'ALT',
                 'notes': '04 - CALVES | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Same machine/foot support; note coarse 20-lb jumps when applicable. Cues: Own '
                          'the stretch and contraction; build reps before increasing load. Work 3 sets of '
                          '10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 6: 80 for 15/15/12; keep 80 while building third set and '
                          'controlling tempo. Latest Oct 6, 2026: 80x15, 80x15, 80x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 6, 2026: 80x15, 80x15, 80x12.'},
                {'aliases': ['Hip Abduction (Machine)'],
                 'sets_count': 2,
                 'rep_min': 15,
                 'rep_max': 20,
                 'weight_lb': 80,
                 'rest_seconds': 75,
                 'slot': '05 - GLUTE MEDIUS',
                 'role': 'PRIMARY',
                 'notes': '05 - GLUTE MEDIUS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Set comfortable hip angle, pelvis and back steady against support. Cues: Open '
                          'hips without leaning or bouncing; brief hold, controlled return. Work 2 sets of '
                          '15-20 reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 9: 80 for 20/20, RPE 7.5-8; next increment can be trialed '
                          'when controlled. Latest Oct 9, 2026: 80x20, 80x20.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 80x20, 80x20.'},
                {'aliases': ['Hip Abduction (Cable)'],
                 'sets_count': 2,
                 'rep_min': 15,
                 'rep_max': 20,
                 'weight_lb': None,
                 'rest_seconds': 75,
                 'slot': '05 - GLUTE MEDIUS',
                 'role': 'ALT',
                 'notes': '05 - GLUTE MEDIUS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Cable at ankle cuff; support balance; cable setup is an unlogged '
                          'alternative. Cues: Move leg outward without torso lean or hip hiking; match '
                          'sides. 2x15-20; 1-2 RIR; 75s rest. Add reps before load; track each machine '
                          'independently. Progress tip: No exact prior session. This may need a manually '
                          'selected/custom Hevy exercise template; calibrate each side. No matching '
                          'movement in uploaded history; establish the load at 2-3 RIR on the exact '
                          'machine.',
                 'group': 'required',
                 'latest': 'No matching movement in uploaded history; establish the load at 2-3 RIR on the '
                           'exact machine.'},
                {'aliases': ['Hammer Curl (Cable)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 35,
                 'rest_seconds': 90,
                 'slot': '06 - HAMMER CURL',
                 'role': 'PRIMARY',
                 'notes': '06 - HAMMER CURL | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Neutral-grip rope on same cable station; elbows at sides. Cues: Curl without '
                          'swinging, shrugging or wrist flexion; slow eccentric. Work 4 sets of 10-15 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 30: 35 for 10/10/10. V3 adds fourth set. Add clean reps '
                          'rather than load. Latest Sep 30, 2026: 35x10, 35x10, 35x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 30, 2026: 35x10, 35x10, 35x10.'},
                {'aliases': ['Hammer Curl (Dumbbell)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 20,
                 'rest_seconds': 90,
                 'slot': '06 - HAMMER CURL',
                 'role': 'ALT',
                 'notes': '06 - HAMMER CURL | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Neutral wrists, arms at sides; load per hand. Cues: Keep elbow position '
                          'stable, no torso sway; lower fully and deliberately. Work 4 sets of 10-15 reps, '
                          'aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions '
                          'before the smallest increment; keep separate loads for each station. Progress '
                          'tip: May log: 20/hand for 12. Old baseline; recalibrate with 1-2 RIR. Latest '
                          'May 30, 2026: 20x12. Old exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest May 30, 2026: 20x12. Old exposure; recalibrate before using historical '
                           'numbers.'},
                {'aliases': ['Preacher Curl (Machine)'],
                 'sets_count': 4,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 65,
                 'rest_seconds': 90,
                 'slot': '06 - HAMMER CURL',
                 'role': 'ALT',
                 'notes': '06 - HAMMER CURL | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Adjust seat and elbow pad; same preacher machine. Cues: Upper arms stay '
                          'planted; do not drop into hard elbow extension. Work 4 sets of 8-12 reps, aim '
                          '1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Sep '
                          '2: 65 for 8/8/10; supinated substitute for same biceps slot, not neutral grip. '
                          'Latest Sep 2, 2026: 65x8, 65x8, 65x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 2, 2026: 65x8, 65x8, 65x10.'},
                {'aliases': ['Cable Crunch'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 60,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - CORE | OPTIONAL. True add-on; skip if time/recovery are limited. '
                          'Setup: Kneel with cable overhead; keep hips relatively quiet. Cues: Curl ribs '
                          'toward pelvis rather than pulling hands down; controlled breathing. Work 2 sets '
                          'of 10-15 reps, aim 1-2 RIR, rest 60s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 9: 60 for 15/15; add core only if main quad + arm '
                          'work is complete. Latest Oct 9, 2026: 60x15, 60x15.',
                 'group': 'optional',
                 'latest': 'Latest Oct 9, 2026: 60x15, 60x15.'},
                {'aliases': ['Cable Core Pallof Press'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. True add-on; skip if time/recovery are limited. Setup: '
                          'Cable at sternum height, feet stable, ribs over pelvis. Cues: Press hands away '
                          'while resisting rotation; hold 1-2 sec, do both sides. Work 2 sets of 10-15 '
                          'reps, aim 1-2 RIR, rest 60s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 6: 17.5 for 20/20; prescribed slower 10-15 each side and a '
                          'pause. Latest Oct 6, 2026: 17.5x20, 17.5x20.',
                 'group': 'optional',
                 'latest': 'Latest Oct 6, 2026: 17.5x20, 17.5x20.'},
                {'aliases': ['Dead Bug'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. True add-on; skip if time/recovery are limited. Setup: '
                          'Supine, knees and hips flexed; start unloaded and brace lightly. Cues: Reach '
                          'opposite limbs slowly while maintaining trunk control; exhale. Work 2 sets of '
                          '6-10 reps, aim 1-2 RIR, rest 60s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Bodyweight anti-extension choice; track slow reps per side. '
                          'Latest Oct 6, 2026: BWx6.',
                 'group': 'optional',
                 'latest': 'Latest Oct 6, 2026: BWx6.'}],
  'notes': 'Quad-dominant compounds and isolations first; add direct neutral-grip biceps after calves and '
           'hip abduction. V3 HYBRID. Rolling sequence: Upper A > Lower A > Upper B > Lower B; resume '
           'after missed days. Only ONE movement per numbered slot: PRIMARY or ALT, never both. Optional '
           'CORE is not required. Warm-up sets are separate. Log unused ALT movements as unperformed. Big '
           'lifts generally 1-3 RIR; isolation 1-2 RIR; never force pain. Compounds rest 2-3 min, '
           'isolations 60-90 sec. Increase weight only after target reps with consistent form and reserve; '
           'small clean rep gains count. All dumbbell weights are PER HAND, plate-loaded iso movements PER '
           'SIDE, others follow your logged exact machine convention; never double unilateral values. '
           'Upper A incline uses 3 heavy sets and one lighter back-off after full rest. Loads come from '
           'the exercise history exported through Oct 13, 2026, not mandatory targets. Stop or modify any '
           'movement causing back pain, radiating symptoms, numbness or weakness.'},
 {'title': 'Upper B - V-Taper + Biceps V3',
  'focus': 'Lat width, shoulder press, row, lighter chest press, mandatory low-to-high fly, delts, '
           'supinated biceps.',
  'required_sets': 21,
  'exercises': [{'aliases': ['Iso Pulldown'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 65,
                 'rest_seconds': 120,
                 'slot': '01 - PULLDOWN',
                 'role': 'PRIMARY',
                 'notes': '01 - PULLDOWN | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Same plate-loaded iso machine; use per-side logging convention. Cues: Lead with '
                          'elbows toward hips and resist the stretch without twisting. Work 3 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 12: 65/side for 12/12/12 at 7.5-8.5 RPE. Trial smallest next '
                          'plate only if clean. Latest Oct 12, 2026: 65x12, 65x12, 65x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 65x12, 65x12, 65x12.'},
                {'aliases': ['Lat Pulldown (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': '01 - PULLDOWN',
                 'role': 'ALT',
                 'notes': '01 - PULLDOWN | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Secure thigh pad and match exact selectorized machine/grip. Cues: Lean slightly '
                          'and pull elbows to sides; no torso heave or neck reach. Work 3 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 1: 115 for 10/10/9 at high late effort. Maintain and rebuild. '
                          'Latest Oct 1, 2026: 115x10, 115x10, 115x9.',
                 'group': 'required',
                 'latest': 'Latest Oct 1, 2026: 115x10, 115x10, 115x9.'},
                {'aliases': ['Lat Pulldown (Cable)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 70,
                 'rest_seconds': 120,
                 'slot': '01 - PULLDOWN',
                 'role': 'ALT',
                 'notes': '01 - PULLDOWN | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Keep station, attachment and stack convention consistent. Cues: Draw elbows '
                          'toward ribs with a stable torso; resist the return. Work 3 sets of 8-12 reps, '
                          'aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 comparable sessions '
                          'before the smallest increment; keep separate loads for each station. Progress '
                          'tip: Oct 8: 70 for 12/12/12 at 8-8.5 RPE. Progress next step cautiously. Latest '
                          'Oct 8, 2026: 70x12, 70x12, 70x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 70x12, 70x12, 70x12.'},
                {'aliases': ['Single Arm Lat Pulldown'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': None,
                 'rest_seconds': 120,
                 'slot': '01 - PULLDOWN',
                 'role': 'ALT',
                 'notes': '01 - PULLDOWN | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Confirm cable ratio/station; load not comparable to iso pulldown. Cues: Keep '
                          'torso square, draw elbow toward hip and match weaker-side reps. Work 3 sets of '
                          '8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Possible 2:1 pulley; old stack 120 is not iso equivalence. '
                          'Recalibrate. Latest Aug 6, 2026: 120x8, 120x7, 120x6. Old exposure; recalibrate '
                          'before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Aug 6, 2026: 120x8, 120x7, 120x6. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Seated Overhead Press (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 35,
                 'rest_seconds': 150,
                 'slot': '02 - SHOULDER PRESS',
                 'role': 'PRIMARY',
                 'notes': '02 - SHOULDER PRESS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Back-supported bench at about 60-75 degrees; load per hand. Cues: Brace '
                          'ribs, press in comfortable arc without excessive leaning or shrugging. Work 2 '
                          'sets of 8-12 reps, aim 1-2 RIR, rest 150s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 5: 35 for 10/10/10. Oct 12: 37.5 gave 8/6/6; return '
                          'to 35 and earn 2x12 before retrying 37.5. Latest Oct 12, 2026: 37.5x8, 37.5x6, '
                          '37.5x6.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 37.5x8, 37.5x6, 37.5x6.'},
                {'aliases': ['Seated Shoulder Press (Machine)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 150,
                 'slot': '02 - SHOULDER PRESS',
                 'role': 'ALT',
                 'notes': '02 - SHOULDER PRESS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Match seat/handles; keep back and ribs supported. Cues: Press evenly '
                          'without shoulders shrugging or forceful lockout. Work 2 sets of 8-12 reps, aim '
                          '1-2 RIR, rest 150s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Sep '
                          '28: 55 for 12/12/12; preserve RIR with two-set V3 prescription. Latest Sep 28, '
                          '2026: 55x12, 55x12, 55x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 28, 2026: 55x12, 55x12, 55x12.'},
                {'aliases': ['Seated Row (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 115,
                 'rest_seconds': 120,
                 'slot': '03 - HORIZONTAL ROW',
                 'role': 'PRIMARY',
                 'notes': '03 - HORIZONTAL ROW | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Set seat/chest support and grip consistently on same machine. Cues: '
                          'Control the forward reach and pull without heaving or lifting your chest. Work '
                          '3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 8: 115 for 12/12/12, final RPE 9.5; maintain until '
                          'reserve is adequate. Latest Oct 8, 2026: 115x12, 115x12, 115x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 115x12, 115x12, 115x12.'},
                {'aliases': ['Chest Supported T Bar Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 60,
                 'rest_seconds': 120,
                 'slot': '03 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '03 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Keep sternum on support, grip consistent and feet braced. Cues: Pull '
                          'elbows behind torso under control without lifting chest from pad. Work 3 sets '
                          'of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 5: 60 for 10/10/10; same T-bar station. Latest Oct '
                          '5, 2026: 60x10, 60x10, 60x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 5, 2026: 60x10, 60x10, 60x10.'},
                {'aliases': ['Seated Cable Row - V Grip (Cable)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 42.5,
                 'rest_seconds': 120,
                 'slot': '03 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '03 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Record exact dual-stack/pulley setup; logged stack weight may not equal '
                          'resistance. Cues: Sit braced, pull toward low ribs, avoid rocking or rounding '
                          'lumbar spine. Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Oct 12: 42.5 for 10/10/10 at RPE '
                          '8 on dual-pulley station. Latest Oct 12, 2026: 42.5x10, 42.5x10, 42.5x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 42.5x10, 42.5x10, 42.5x10.'},
                {'aliases': ['Iso-Lateral Low Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 120,
                 'slot': '03 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '03 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Chest supported, same seat and handles; load logged per side. Cues: '
                          'Elbows toward lower ribs with controlled reach; do not rotate torso or shrug. '
                          'Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on '
                          '2 comparable sessions before the smallest increment; keep separate loads for '
                          'each station. Progress tip: Oct 1: 55/side 12/12/12; keep identical per-side '
                          'logging. Latest Oct 1, 2026: 55x12, 55x12, 55x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 1, 2026: 55x12, 55x12, 55x12.'},
                {'aliases': ['Dumbbell Row'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 40,
                 'rest_seconds': 120,
                 'slot': '03 - HORIZONTAL ROW',
                 'role': 'ALT',
                 'notes': '03 - HORIZONTAL ROW | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Support free hand on a bench; keep hips square and back comfortable; per '
                          'hand. Cues: Reach the weight downward, then row elbow toward hip without '
                          'twisting. Work 3 sets of 8-12 reps, aim 1-2 RIR, rest 120s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Sep 5: 40/hand for 10x3; chest '
                          'support preferred if back fatigued. Latest Sep 5, 2026: 40x10, 40x10, 40x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 5, 2026: 40x10, 40x10, 40x10.'},
                {'aliases': ['Incline Bench Press (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 47.5,
                 'rest_seconds': 150,
                 'slot': '04 - LIGHT INCLINE',
                 'role': 'PRIMARY',
                 'notes': '04 - LIGHT INCLINE | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Bench 15-30 degrees, stable feet and shoulder blades; load per hand. '
                          'Cues: Lower under control, forearms stacked, press without bouncing or rib '
                          'flare. Work 2 sets of 8-12 reps, aim 1-2 RIR, rest 150s. Build clean top-range '
                          'reps on 2 comparable sessions before the smallest increment; keep separate '
                          'loads for each station. Progress tip: Lighter than Upper A; use 2-3 RIR and no '
                          'backoff here. Per-hand load is suggested, not a recent identical-set test. '
                          'Latest Oct 8, 2026: 52.5x8, 52.5x8, 52.5x8, 52.5x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 8, 2026: 52.5x8, 52.5x8, 52.5x8, 52.5x8.'},
                {'aliases': ['Incline Chest Press (Machine)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 45,
                 'rest_seconds': 150,
                 'slot': '04 - LIGHT INCLINE',
                 'role': 'ALT',
                 'notes': '04 - LIGHT INCLINE | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Match seat and grip; ensure a comfortable low-incline path; machine load '
                          'is station-specific. Cues: Maintain rib control, a smooth lowering phase and '
                          'even arm drive. Work 2 sets of 8-12 reps, aim 1-2 RIR, rest 150s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Oct 5: 45 for 8/8 on this exact '
                          'machine. Build toward 2x12. Latest Oct 5, 2026: 45x8, 45x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 5, 2026: 45x8, 45x8.'},
                {'aliases': ['Incline Bench Press (Barbell)'],
                 'sets_count': 2,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': None,
                 'rest_seconds': 180,
                 'slot': '04 - LIGHT INCLINE',
                 'role': 'ALT',
                 'notes': '04 - LIGHT INCLINE | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Use safeties or spotter and a low-incline bench; total bar weight. Cues: '
                          'Touch at a consistent location; keep elbows comfortable and avoid bouncing. '
                          'Work 2 sets of 8-12 reps, aim 1-2 RIR, rest 180s. Build clean top-range reps on '
                          '2 comparable sessions before the smallest increment; keep separate loads for '
                          'each station. Progress tip: Last April; reintroduce conservatively with proper '
                          'safeties and 2-3 RIR. Latest Apr 6, 2026: 115x8, 125x6, 130x4, 115x7. Old '
                          'exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Apr 6, 2026: 115x8, 125x6, 130x4, 115x7. Old exposure; recalibrate '
                           'before using historical numbers.'},
                {'aliases': ['Low Cable Fly Crossovers'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 10,
                 'rest_seconds': 90,
                 'slot': '05 - LOW-TO-HIGH FLY',
                 'role': 'PRIMARY',
                 'notes': '05 - LOW-TO-HIGH FLY | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Use LOW pulleys, same station and balanced stance; weight per logged '
                          'stack/side. Cues: Sweep arms upward/inward with soft elbows; avoid torso swing '
                          'or shoulder rolling. Work 2 sets of 12-20 reps, aim 1-2 RIR, rest 90s. Build '
                          'clean top-range reps on 2 comparable sessions before the smallest increment; '
                          'keep separate loads for each station. Progress tip: Oct 12: 10 per logged '
                          'side/stack for 20/20 at RPE 7.5. Try next small increment with consistent '
                          'angle. Latest Oct 12, 2026: 10x20, 10x20.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 10x20, 10x20.'},
                {'aliases': ['Seated Chest Flys (Cable)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 40,
                 'rest_seconds': 90,
                 'slot': '05 - LOW-TO-HIGH FLY',
                 'role': 'ALT',
                 'notes': '05 - LOW-TO-HIGH FLY | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Use same seated dual-cable station; confirm pulley configuration. Cues: '
                          'Bring handles inward at a comfortable chest path; controlled eccentric. Work 2 '
                          'sets of 12-20 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 5: 40 gave 15/12/12; V3 two sets. Same station only; '
                          'may not reproduce low-to-high bias. Latest Oct 5, 2026: 40x15, 40x12, 40x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 5, 2026: 40x15, 40x12, 40x12.'},
                {'aliases': ['Chest Fly (Machine)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 85,
                 'rest_seconds': 90,
                 'slot': '05 - LOW-TO-HIGH FLY',
                 'role': 'ALT',
                 'notes': '05 - LOW-TO-HIGH FLY | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Set handles to chest height and match machine/seat. Cues: Keep torso '
                          'fixed; bring arms inward with smooth stretch and squeeze. Work 2 sets of 12-20 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 3: 85 gave 15/15/12; choose appropriate RIR and use 2 sets. '
                          'Latest Sep 3, 2026: 85x15, 85x15, 85x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 3, 2026: 85x15, 85x15, 85x12.'},
                {'aliases': ['Chest Fly (Dumbbell)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 25,
                 'rest_seconds': 90,
                 'slot': '05 - LOW-TO-HIGH FLY',
                 'role': 'ALT',
                 'notes': '05 - LOW-TO-HIGH FLY | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Flat bench, stable shoulder blades; dumbbell load per hand. Cues: Soft '
                          'elbows; lower only to a comfortable stretch and lift without turning it into a '
                          'press. Work 2 sets of 12-20 reps, aim 1-2 RIR, rest 90s. Build clean top-range '
                          'reps on 2 comparable sessions before the smallest increment; keep separate '
                          'loads for each station. Progress tip: Sep 30: 25/hand for 15/15; stop well '
                          'before deep shoulder stretch. Latest Sep 30, 2026: 25x15, 25x15.',
                 'group': 'required',
                 'latest': 'Latest Sep 30, 2026: 25x15, 25x15.'},
                {'aliases': ['Single Arm Lateral Raise (Cable)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 10,
                 'rest_seconds': 75,
                 'slot': '06 - SIDE DELTS',
                 'role': 'PRIMARY',
                 'notes': '06 - SIDE DELTS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Hold the frame; fix pulley height, body distance and start-side. Cues: Lead '
                          'with elbows, avoid shrug and leaning; lower slowly and match sides. Work 3 sets '
                          'of 12-20 reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 12: 10 for 20/18/16; same stance as Upper A. Latest '
                          'Oct 12, 2026: 10x20, 10x18, 10x16.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 10x20, 10x18, 10x16.'},
                {'aliases': ['Seated Lateral Raise (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 12.5,
                 'rest_seconds': 75,
                 'slot': '06 - SIDE DELTS',
                 'role': 'ALT',
                 'notes': '06 - SIDE DELTS | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Sit stable with bells slightly forward; per dumbbell. Cues: Soft elbows, raise '
                          'with delts not traps, no torso swing; control descent. Work 3 sets of 12-20 '
                          'reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 3: mixed 12.5 and 15; start 12.5 with strict form. Latest Sep '
                          '3, 2026: 12.5x20, 15x12, 15x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 3, 2026: 12.5x20, 15x12, 15x12.'},
                {'aliases': ['Lateral Raise (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': None,
                 'rest_seconds': 75,
                 'slot': '06 - SIDE DELTS',
                 'role': 'ALT',
                 'notes': '06 - SIDE DELTS | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Stand tall with soft knees, shoulders neutral; per dumbbell. Cues: Lead elbows, '
                          'stop before shrugging and do not use momentum to reach higher. Work 3 sets of '
                          '12-20 reps, aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Old 20-lb July result may not match strict cable form; '
                          'recalibrate. Latest Jul 30, 2026: 20x16, 20x16. Old exposure; recalibrate '
                          'before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Jul 30, 2026: 20x16, 20x16. Old exposure; recalibrate before using '
                           'historical numbers.'},
                {'aliases': ['Rear Delt Reverse Fly (Cable)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 7.5,
                 'rest_seconds': 75,
                 'slot': '07 - REAR DELTS',
                 'role': 'PRIMARY',
                 'notes': '07 - REAR DELTS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Set cables around shoulder height and fixed elbow bend. Cues: Open arms in wide '
                          'arc without shrugging, rowing or torso rotation. Work 2 sets of 12-20 reps, aim '
                          '1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Oct '
                          '12: 7.5 for 20/20 at RPE 7.5. Trial 10 only if range and reserve stay clean. '
                          'Latest Oct 12, 2026: 7.5x20, 7.5x20.',
                 'group': 'required',
                 'latest': 'Latest Oct 12, 2026: 7.5x20, 7.5x20.'},
                {'aliases': ['Rear Delt Reverse Fly (Machine)'],
                 'sets_count': 2,
                 'rep_min': 12,
                 'rep_max': 20,
                 'weight_lb': 55,
                 'rest_seconds': 75,
                 'slot': '07 - REAR DELTS',
                 'role': 'ALT',
                 'notes': '07 - REAR DELTS | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Keep chest against pad; set handles near shoulder height. Cues: Spread arms out '
                          'with soft elbows; do not turn movement into a row. Work 2 sets of 12-20 reps, '
                          'aim 1-2 RIR, rest 75s. Build clean top-range reps on 2 comparable sessions '
                          'before the smallest increment; keep separate loads for each station. Progress '
                          'tip: Oct 1: 55 for 15/15 at RPE 7.5. Independent load history. Latest Oct 1, '
                          '2026: 55x15, 55x15.',
                 'group': 'required',
                 'latest': 'Latest Oct 1, 2026: 55x15, 55x15.'},
                {'aliases': ['Bicep Curl (Dumbbell)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 20,
                 'rest_seconds': 90,
                 'slot': '08 - SUPINATED BICEPS',
                 'role': 'PRIMARY',
                 'notes': '08 - SUPINATED BICEPS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Stand or sit braced, supinate palms; weight per hand. Cues: Keep elbows '
                          'mostly still; no hip swing or shoulder shrug; lower slowly. 4x10-15; 1-2 RIR; '
                          '90s rest. Add reps before load; track each machine independently. Progress tip: '
                          'Last direct DB curl Jun 23: 22.5 for 3x10, no RPE. Begin 20/hand for V3 four '
                          'sets at ~2 RIR; calibrate. Latest Jun 23, 2026: 22.5x10, 22.5x10, 22.5x10. Old '
                          'exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Jun 23, 2026: 22.5x10, 22.5x10, 22.5x10. Old exposure; recalibrate '
                           'before using historical numbers.'},
                {'aliases': ['Preacher Curl (Machine)'],
                 'sets_count': 4,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 65,
                 'rest_seconds': 90,
                 'slot': '08 - SUPINATED BICEPS',
                 'role': 'ALT',
                 'notes': '08 - SUPINATED BICEPS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Adjust seat and elbow pad; same preacher machine. Cues: Upper arms stay '
                          'planted; do not drop into hard elbow extension. Work 4 sets of 8-12 reps, aim '
                          '1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Sep '
                          '2: 65 for 8/8/10; four V3 sets may require conservative loading. Latest Sep 2, '
                          '2026: 65x8, 65x8, 65x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 2, 2026: 65x8, 65x8, 65x10.'},
                {'aliases': ['Seated Incline Curl (Dumbbell)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 20,
                 'rest_seconds': 90,
                 'slot': '08 - SUPINATED BICEPS',
                 'role': 'ALT',
                 'notes': '08 - SUPINATED BICEPS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Use supported incline and let arms hang without forced shoulder stretch. '
                          'Cues: Supinate and curl with still upper arms; controlled eccentric. Work 4 '
                          'sets of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Sep 30: 20/hand for 15/15; add volume cautiously with '
                          'four sets. Latest Sep 30, 2026: 20x15, 20x15.',
                 'group': 'required',
                 'latest': 'Latest Sep 30, 2026: 20x15, 20x15.'},
                {'aliases': ['Single Arm Curl (Cable)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 90,
                 'slot': '08 - SUPINATED BICEPS',
                 'role': 'ALT',
                 'notes': '08 - SUPINATED BICEPS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Single handle and same pulley; keep elbow position stable. Cues: Curl '
                          'palm-up without swinging; start weaker side and match clean reps. Work 4 sets '
                          'of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Aug old 15 for 15/12; new four-set arrangement needs 2 '
                          'RIR recalibration. Latest Aug 6, 2026: 15x15, 15x12. Old exposure; recalibrate '
                          'before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Aug 6, 2026: 15x15, 15x12. Old exposure; recalibrate before using '
                           'historical numbers.'}],
  'notes': 'Lat width, shoulder press, row, lighter chest press, mandatory low-to-high fly, delts, '
           'supinated biceps. V3 HYBRID. Rolling sequence: Upper A > Lower A > Upper B > Lower B; resume '
           'after missed days. Only ONE movement per numbered slot: PRIMARY or ALT, never both. Optional '
           'CORE is not required. Warm-up sets are separate. Log unused ALT movements as unperformed. Big '
           'lifts generally 1-3 RIR; isolation 1-2 RIR; never force pain. Compounds rest 2-3 min, '
           'isolations 60-90 sec. Increase weight only after target reps with consistent form and reserve; '
           'small clean rep gains count. All dumbbell weights are PER HAND, plate-loaded iso movements PER '
           'SIDE, others follow your logged exact machine convention; never double unilateral values. '
           'Upper A incline uses 3 heavy sets and one lighter back-off after full rest. Loads come from '
           'the exercise history exported through Oct 13, 2026, not mandatory targets. Stop or modify any '
           'movement causing back pain, radiating symptoms, numbness or weakness.'},
 {'title': 'Lower B - Glutes + Triceps V3',
  'focus': 'Hip thrust, controlled hinge, unilateral quads/glutes, hamstrings, calves, overhead triceps. '
           'No extra heavy hinge finishers.',
  'required_sets': 19,
  'exercises': [{'aliases': ['Hip Thrust (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 145,
                 'rest_seconds': 180,
                 'slot': '01 - HIP THRUST',
                 'role': 'PRIMARY',
                 'notes': '01 - HIP THRUST | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Pad across pelvis, feet braced and ribs down; same thrust machine. Cues: Drive '
                          'through feet and pause at top with glutes, not lower-back arch. Work 3 sets of '
                          '8-10 reps, aim 1-2 RIR, rest 180s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 13: 145 for 10/9/8, RPE 8-8.5. Earn 10/10/10 before adding. '
                          'Latest Oct 13, 2026: 145x10, 145x9, 145x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 145x10, 145x9, 145x8.'},
                {'aliases': ['Hip Thrust (Barbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 180,
                 'slot': '01 - HIP THRUST',
                 'role': 'ALT',
                 'notes': '01 - HIP THRUST | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Pad bar over pelvis and brace shoulders on firm bench; new station means '
                          'recalibrate. Cues: Ribs down, heels stable; pause top without lumbar '
                          'hyperextension. 3x8-10; 1-2 RIR; 180s rest. Add reps before load; track each '
                          'machine independently. Progress tip: No recent barbell hip thrust data; '
                          'recalibrate for 2 RIR, with pad, stable bench and load recorded total. No '
                          'matching movement in uploaded history; establish the load at 2-3 RIR on the '
                          'exact machine.',
                 'group': 'required',
                 'latest': 'No matching movement in uploaded history; establish the load at 2-3 RIR on the '
                           'exact machine.'},
                {'aliases': ['Romanian Deadlift (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 50,
                 'rest_seconds': 180,
                 'slot': '02 - HINGE',
                 'role': 'PRIMARY',
                 'notes': '02 - HINGE | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: Feet '
                          'hip-width, soft knees, dumbbells close; weight per hand. Cues: Hinge hips back, '
                          'stop before spinal rounding; stand through glutes. Work 3 sets of 8-10 reps, '
                          'aim 1-2 RIR, rest 180s. Build clean top-range reps on 2 comparable sessions '
                          'before the smallest increment; keep separate loads for each station. Progress '
                          'tip: Oct 13: 50/hand for 10/10/9, RPE 7.5-8. Progress to 3x10 before '
                          'increasing; stop for radiating symptoms. Latest Oct 13, 2026: 50x10, 50x10, '
                          '50x9.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 50x10, 50x10, 50x9.'},
                {'aliases': ['Romanian Deadlift (Barbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 180,
                 'slot': '02 - HINGE',
                 'role': 'ALT',
                 'notes': '02 - HINGE | ALT. REPLACES this slot primary; choose ONE variation. Setup: Grip '
                          'stable, soft knees and bar near thighs; old barbell history may not reflect '
                          'readiness. Cues: Hinge hips backward with neutral trunk; do not chase floor '
                          'depth or radiating symptoms. 3x8-10; 1-2 RIR; 180s rest. Add reps before load; '
                          'track each machine independently. Progress tip: Apr 5: 165 for 8/8; after long '
                          'gap, retest with 2-3 RIR rather than using 165 automatically. Latest Apr 5, '
                          '2026: 165x8, 165x8, 135x10. Old exposure; recalibrate before using historical '
                          'numbers.',
                 'group': 'required',
                 'latest': 'Latest Apr 5, 2026: 165x8, 165x8, 135x10. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Cable Pull Through'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 120,
                 'slot': '02 - HINGE',
                 'role': 'ALT',
                 'notes': '02 - HINGE | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Cable behind with rope, step forward enough for stack clearance. Cues: Hinge '
                          'hips backward and drive through hips without leaning or spinal extension. Work '
                          '3 sets of 10-15 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Last April: 25-30 for 12-15; rerun calibration as '
                          'lighter hinge alternative. Latest Apr 21, 2026: 25x12, 25x15, 30x12. Old '
                          'exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Apr 21, 2026: 25x12, 25x15, 30x12. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Reverse Lunge (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': 30,
                 'rest_seconds': 120,
                 'slot': '03 - UNILATERAL LEG',
                 'role': 'PRIMARY',
                 'notes': '03 - UNILATERAL LEG | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Start with reliable footing; hold a load per hand and use balance '
                          'support if useful. Cues: Step back under control, front knee tracks with toes, '
                          'drive through front foot. Work 3 sets of 8-10 reps, aim 1-2 RIR, rest 120s. '
                          'Build clean top-range reps on 2 comparable sessions before the smallest '
                          'increment; keep separate loads for each station. Progress tip: Oct 13: 30/hand '
                          'for 10/10/10 at 7.5-8 RPE. Oct 6 heavier 35 caused second-set RPE 9.5; choose '
                          'sustainable progression. Latest Oct 13, 2026: 30x10, 30x10, 30x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 30x10, 30x10, 30x10.'},
                {'aliases': ['Lunge (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 120,
                 'slot': '03 - UNILATERAL LEG',
                 'role': 'ALT',
                 'notes': '03 - UNILATERAL LEG | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Select stable step or stationary lunge; hold dumbbells per hand. Cues: '
                          'Maintain bracing, comfortable knee tracking and controlled depth. Work 3 sets '
                          'of 8-10 reps, aim 1-2 RIR, rest 120s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: May 27: 25 for 10x2 then 30x8; recalibrate if changing '
                          'lunge direction/stride. Latest May 27, 2026: 25x10, 25x10, 30x8. Old exposure; '
                          'recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest May 27, 2026: 25x10, 25x10, 30x8. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Bulgarian Split Squat (Dumbbell)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 120,
                 'slot': '03 - UNILATERAL LEG',
                 'role': 'ALT',
                 'notes': '03 - UNILATERAL LEG | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Rear foot supported and front foot placed for stable depth; hold support '
                          'if necessary. Cues: Drive through front foot without torso twisting or pelvis '
                          'dipping. 3x8-10; 1-2 RIR; 120s rest. Add reps before load; track each machine '
                          'independently. Progress tip: July data with ~31/hand; start lighter and '
                          'prioritize safe balance and hip control. Latest Jul 28, 2026: 31x10, 31x10, '
                          '35x6. Old exposure; recalibrate before using historical numbers.',
                 'group': 'required',
                 'latest': 'Latest Jul 28, 2026: 31x10, 31x10, 35x6. Old exposure; recalibrate before '
                           'using historical numbers.'},
                {'aliases': ['Lying Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 75,
                 'rest_seconds': 90,
                 'slot': '04 - LEG CURL',
                 'role': 'PRIMARY',
                 'notes': '04 - LEG CURL | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: '
                          'Knee aligned with pivot, pad above heels, hips on bench. Cues: Curl without '
                          'lumbar arch, hips lifting or swinging; controlled descent. Work 3 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 13: 75 for 12/12/8 at RPE 8-8.5. Hold 75 until third set '
                          'improves. Latest Oct 13, 2026: 75x12, 75x12, 75x8.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 75x12, 75x12, 75x8.'},
                {'aliases': ['Seated Leg Curl (Machine)'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 120,
                 'rest_seconds': 90,
                 'slot': '04 - LEG CURL',
                 'role': 'ALT',
                 'notes': '04 - LEG CURL | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Secure thigh pad; knee at machine pivot, hips remain seated. Cues: Curl through '
                          'comfortable range, brief squeeze and slow return. Work 3 sets of 8-12 reps, aim '
                          '1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Oct '
                          '9: 120 for 12/12/10. Recalibrate after hinge fatigue. Latest Oct 9, 2026: '
                          '120x12, 120x12, 120x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 120x12, 120x12, 120x10.'},
                {'aliases': ['Standing Leg Curls'],
                 'sets_count': 3,
                 'rep_min': 8,
                 'rep_max': 12,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': '04 - LEG CURL',
                 'role': 'ALT',
                 'notes': '04 - LEG CURL | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Use same standing leg-curl station; align knee and stabilize torso. Cues: Match '
                          'weaker leg; curl without hip movement or lumbar extension. Work 3 sets of 8-12 '
                          'reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 15: 55 for 12/12/10 per leg; match sides. Latest Oct 6, 2026: '
                          '55x12, 55x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 6, 2026: 55x12, 55x12.'},
                {'aliases': ['Calf Extension (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 80,
                 'rest_seconds': 90,
                 'slot': '05 - CALVES',
                 'role': 'PRIMARY',
                 'notes': '05 - CALVES | PRIMARY. Choose this PRIMARY or ONE ALT; never both. Setup: Same '
                          'machine/foot support; note coarse 20-lb jumps when applicable. Cues: Own the '
                          'stretch and contraction; build reps before increasing load. Work 3 sets of '
                          '10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 6: 80 for 15/15/12. Build all three to 15, and account for '
                          '20-lb jumps. Latest Oct 6, 2026: 80x15, 80x15, 80x12.',
                 'group': 'required',
                 'latest': 'Latest Oct 6, 2026: 80x15, 80x15, 80x12.'},
                {'aliases': ['Standing Calf Raise (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 55,
                 'rest_seconds': 90,
                 'slot': '05 - CALVES',
                 'role': 'ALT',
                 'notes': '05 - CALVES | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Stable forefoot, shoulders under pads, knees softly extended. Cues: Pause at '
                          'stretch and top; avoid bouncing or torso motion. Work 3 sets of 10-15 reps, aim '
                          '1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable sessions before '
                          'the smallest increment; keep separate loads for each station. Progress tip: Sep '
                          '29: 55 for 15x3 but final RPE 9.5; hold and improve reserve. Latest Oct 13, '
                          '2026: 60x12, 60x12, 60x10.',
                 'group': 'required',
                 'latest': 'Latest Oct 13, 2026: 60x12, 60x12, 60x10.'},
                {'aliases': ['Calf Press (Machine)'],
                 'sets_count': 3,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 110,
                 'rest_seconds': 90,
                 'slot': '05 - CALVES',
                 'role': 'ALT',
                 'notes': '05 - CALVES | ALT. REPLACES this slot primary; choose ONE variation. Setup: '
                          'Secure forefoot and seat position on same calf/leg-press setup. Cues: '
                          'Controlled ankle stretch and full rise; no bouncing or knee pumping. Work 3 '
                          'sets of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 9: 110 for 15x3 at final RPE 8.5; different machine '
                          'from extension. Latest Oct 9, 2026: 110x15, 110x15, 110x15.',
                 'group': 'required',
                 'latest': 'Latest Oct 9, 2026: 110x15, 110x15, 110x15.'},
                {'aliases': ['Overhead Triceps Extension (Cable)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 35,
                 'rest_seconds': 90,
                 'slot': '06 - OVERHEAD TRICEPS',
                 'role': 'PRIMARY',
                 'notes': '06 - OVERHEAD TRICEPS | PRIMARY. Choose this PRIMARY or ONE ALT; never both. '
                          'Setup: Set cable behind/above, stagger feet and keep ribs down. Cues: Keep '
                          'elbows comfortable; extend with triceps and avoid lumbar arch. Work 4 sets of '
                          '10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 2: 35 for 15/15/10 with RPE rising 6 to 8.5. Four V3 sets: '
                          'maintain or reduce as necessary. Latest Sep 2, 2026: 35x15, 35x15, 35x10.',
                 'group': 'required',
                 'latest': 'Latest Sep 2, 2026: 35x15, 35x15, 35x10.'},
                {'aliases': ['Single Arm Tricep Extension (Dumbbell)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 20,
                 'rest_seconds': 90,
                 'slot': '06 - OVERHEAD TRICEPS',
                 'role': 'ALT',
                 'notes': '06 - OVERHEAD TRICEPS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Use comfortable single-arm overhead position; per-hand weight. Cues: Do '
                          'not flare or force shoulder; control lowering, match arm reps. Work 4 sets of '
                          '10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 30: 20/hand for 15/15. Build added volume carefully with '
                          'elbows and shoulders comfortable. Latest Sep 30, 2026: 20x15, 20x15.',
                 'group': 'required',
                 'latest': 'Latest Sep 30, 2026: 20x15, 20x15.'},
                {'aliases': ['Triceps Extension (Machine)'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 75,
                 'rest_seconds': 90,
                 'slot': '06 - OVERHEAD TRICEPS',
                 'role': 'ALT',
                 'notes': '06 - OVERHEAD TRICEPS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Match seat and elbow pads to the machine; stack is station-specific. '
                          'Cues: Keep upper arms supported, extend without slamming, avoid painful '
                          'lockout. Work 4 sets of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean '
                          'top-range reps on 2 comparable sessions before the smallest increment; keep '
                          'separate loads for each station. Progress tip: Sep 16: 75 for 15/12/12; '
                          'different shoulder position but acceptable triceps substitute. Latest Sep 16, '
                          '2026: 75x15, 75x12, 75x12.',
                 'group': 'required',
                 'latest': 'Latest Sep 16, 2026: 75x15, 75x12, 75x12.'},
                {'aliases': ['Reverse Grip Single Triceps Extension'],
                 'sets_count': 4,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 90,
                 'slot': '06 - OVERHEAD TRICEPS',
                 'role': 'ALT',
                 'notes': '06 - OVERHEAD TRICEPS | ALT. REPLACES this slot primary; choose ONE variation. '
                          'Setup: Underhand grip at same cable, elbow near torso and wrist straight. Cues: '
                          'Extend gently without wrist bending or shoulder swing; avoid elbow irritation. '
                          'Work 4 sets of 10-15 reps, aim 1-2 RIR, rest 90s. Build clean top-range reps on '
                          '2 comparable sessions before the smallest increment; keep separate loads for '
                          'each station. Progress tip: Sep 9: 17.5 for 15/15, last RPE 9. Alternative if '
                          'overhead position bothers shoulder; monitor wrists. Latest Sep 9, 2026: '
                          '17.5x15, 17.5x15.',
                 'group': 'required',
                 'latest': 'Latest Sep 9, 2026: 17.5x15, 17.5x15.'},
                {'aliases': ['Cable Core Pallof Press'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': 17.5,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'OPTIONAL',
                 'notes': 'OPTIONAL - CORE | OPTIONAL. True add-on; skip if time/recovery are limited. '
                          'Setup: Cable at sternum height, feet stable, ribs over pelvis. Cues: Press '
                          'hands away while resisting rotation; hold 1-2 sec, do both sides. Work 2 sets '
                          'of 10-15 reps, aim 1-2 RIR, rest 60s. Build clean top-range reps on 2 '
                          'comparable sessions before the smallest increment; keep separate loads for each '
                          'station. Progress tip: Oct 6: 17.5 for 20/20; slow and pause at extension. Not '
                          'counted in 19 required sets. Latest Oct 6, 2026: 17.5x20, 17.5x20.',
                 'group': 'optional',
                 'latest': 'Latest Oct 6, 2026: 17.5x20, 17.5x20.'},
                {'aliases': ['Dead Bug'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. True add-on; skip if time/recovery are limited. Setup: '
                          'Supine, knees and hips flexed; start unloaded and brace lightly. Cues: Reach '
                          'opposite limbs slowly while maintaining trunk control; exhale. Work 2 sets of '
                          '6-10 reps, aim 1-2 RIR, rest 60s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Oct 6: 6 controlled bodyweight reps logged; use slow alternating '
                          'sides. Latest Oct 6, 2026: BWx6.',
                 'group': 'optional',
                 'latest': 'Latest Oct 6, 2026: BWx6.'},
                {'aliases': ['Bird Dog'],
                 'sets_count': 2,
                 'rep_min': 6,
                 'rep_max': 10,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. True add-on; skip if time/recovery are limited. Setup: '
                          'Quadruped with hands under shoulders and knees under hips. Cues: Reach opposite '
                          'hand/leg long, not high; no hip rotation or spinal arch. Work 2 sets of 6-10 '
                          'reps, aim 1-2 RIR, rest 60s. Build clean top-range reps on 2 comparable '
                          'sessions before the smallest increment; keep separate loads for each station. '
                          'Progress tip: Sep 23: 10/10 without loading; use consistent 1-2-second holds. '
                          'Latest Sep 23, 2026: BWx10, BWx10.',
                 'group': 'optional',
                 'latest': 'Latest Sep 23, 2026: BWx10, BWx10.'},
                {'aliases': ['Reverse Crunch'],
                 'sets_count': 2,
                 'rep_min': 10,
                 'rep_max': 15,
                 'weight_lb': None,
                 'rest_seconds': 60,
                 'slot': 'OPTIONAL - CORE',
                 'role': 'ALT',
                 'notes': 'OPTIONAL - CORE | ALT. True add-on; skip if time/recovery are limited. Setup: '
                          'Lie supine with bent knees and arms braced. Cues: Curl pelvis gently off floor; '
                          'no swinging legs or arching at descent. Work 2 sets of 10-15 reps, aim 1-2 RIR, '
                          'rest 60s. Build clean top-range reps on 2 comparable sessions before the '
                          'smallest increment; keep separate loads for each station. Progress tip: Sep 23: '
                          '25/25; use slower 10-15 with controlled pelvic curl, not momentum. Latest Sep '
                          '23, 2026: BWx25, BWx25.',
                 'group': 'optional',
                 'latest': 'Latest Sep 23, 2026: BWx25, BWx25.'}],
  'notes': 'Hip thrust, controlled hinge, unilateral quads/glutes, hamstrings, calves, overhead triceps. '
           'No extra heavy hinge finishers. V3 HYBRID. Rolling sequence: Upper A > Lower A > Upper B > '
           'Lower B; resume after missed days. Only ONE movement per numbered slot: PRIMARY or ALT, never '
           'both. Optional CORE is not required. Warm-up sets are separate. Log unused ALT movements as '
           'unperformed. Big lifts generally 1-3 RIR; isolation 1-2 RIR; never force pain. Compounds rest '
           '2-3 min, isolations 60-90 sec. Increase weight only after target reps with consistent form and '
           'reserve; small clean rep gains count. All dumbbell weights are PER HAND, plate-loaded iso '
           'movements PER SIDE, others follow your logged exact machine convention; never double '
           'unilateral values. Upper A incline uses 3 heavy sets and one lighter back-off after full rest. '
           'Loads come from the exercise history exported through Oct 13, 2026, not mandatory targets. '
           'Stop or modify any movement causing back pain, radiating symptoms, numbness or weakness.'}]


def lb_to_kg(lb: float | None) -> float | None:
    return None if lb is None else round(lb / LB_PER_KG, 4)


def normal_set(rep_min: int, rep_max: int, weight_lb: float | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        'type': 'normal',
        'rep_range': {'start': rep_min, 'end': rep_max},
    }
    if weight_lb is not None:
        result['weight_kg'] = lb_to_kg(weight_lb)
    return result


def prescribed_sets(ex: dict[str, Any]) -> list[dict[str, Any]]:
    weights = ex.get('set_loads_lb', [ex['weight_lb']] * ex['sets_count'])
    result = []
    for ix, weight in enumerate(weights):
        # 45 -> 40 lb is an explicit suggested fourth-set back-off for
        # the incline machine ALT (distinct from the 52.5 -> 45 DB back-off).
        if ex['slot'] == '01 - INCLINE ANCHOR' and ix == 3 and ex['aliases'][0] == 'Incline Chest Press (Machine)':
            weight = 40
        rep_min, rep_max = ex['rep_min'], ex['rep_max']
        if ex['slot'] == '01 - INCLINE ANCHOR' and ix == 3:
            # Hevy does not have a 'back-off' set type. Represent a real normal
            # set with lighter programmed weight and wider 8-12 rep prescription.
            rep_min, rep_max = 8, 12
        result.append(normal_set(rep_min, rep_max, weight))
    return result


def validate_program() -> None:
    issues: list[str] = []
    if len(ROUTINES) != 4 or len({r['title'] for r in ROUTINES}) != 4:
        issues.append('Expected exactly four distinctly named V3 routines.')
    required_sum = 0
    for routine in ROUTINES:
        title = routine['title']
        if not title.endswith(' V3') or 'V2.' in title:
            issues.append(f'Not a new V3 title: {title}')
        all_names = [e['aliases'][0] for e in routine['exercises']]
        if len(all_names) != len(set(all_names)):
            issues.append(f'{title}: duplicate exercise name within a routine.')
        planned = sum(e['sets_count'] for e in routine['exercises'])
        if planned > HEVY_ROUTINE_SET_LIMIT:
            issues.append(f'{title}: {planned} preloaded sets exceeds {HEVY_ROUTINE_SET_LIMIT}.')
        for ex in routine['exercises']:
            if ex['sets_count'] < 1 or not 1 <= ex['rep_min'] <= ex['rep_max']:
                issues.append(f'Bad prescription: {title}/{ex["aliases"][0]}')
            if ex['role'] not in ('PRIMARY', 'ALT', 'OPTIONAL'):
                issues.append(f'Bad slot role: {title}/{ex["aliases"][0]}')
            weights = ex.get('set_loads_lb', [ex['weight_lb']] * ex['sets_count'])
            if len(weights) != ex['sets_count'] or any(w is not None and w < 0 for w in weights):
                issues.append(f'Invalid load count/weight: {title}/{ex["aliases"][0]}')
            if not EXERCISE_NOTE_MIN <= len(ex['notes']) <= EXERCISE_NOTE_MAX:
                issues.append(f'Note length {len(ex["notes"])}: {title}/{ex["aliases"][0]}')
        for slot_name in {x['slot'] for x in routine['exercises']}:
            group = [x for x in routine['exercises'] if x['slot'] == slot_name]
            anchors = [x for x in group if x['role'] in ('PRIMARY', 'OPTIONAL')]
            if len(anchors) != 1 or any(x['role'] != 'ALT' for x in group[1:]):
                issues.append(f'{title}/{slot_name}: expected one PRIMARY/OPTIONAL then ALT(s).')
            if len({x['sets_count'] for x in group}) != 1:
                issues.append(f'{title}/{slot_name}: ALT set counts should match primary.')
        count = sum(x['sets_count'] for x in routine['exercises'] if x['role'] == 'PRIMARY')
        required_sum += count
        if count != routine['required_sets']:
            issues.append(f'{title}: {count} primary sets vs {routine["required_sets"]} expected.')
    if required_sum != 79:
        issues.append(f'V3 total expected 79 required sets, got {required_sum}.')
    if issues:
        raise ValueError('Program validation failed:\n - ' + '\n - '.join(issues))


def normalize(value: str) -> str:
    value = value.casefold().replace('dumbbell', 'db').replace('single-arm', 'single arm')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', value).split())


def title_of(template: dict[str, Any]) -> str:
    return str(template.get('title') or template.get('name') or '')


def score_title(candidate: str, aliases: list[str]) -> float:
    c = normalize(candidate)
    best = 0.0
    for alias in aliases:
        a = normalize(alias)
        if c == a:
            return 1.0
        similarity = difflib.SequenceMatcher(None, c, a).ratio()
        a_set, c_set = set(a.split()), set(c.split())
        word_overlap = len(a_set & c_set) / max(1, len(a_set | c_set))
        best = max(best, 0.7 * similarity + 0.3 * word_overlap)
    return best


def resolve_template(templates: list[dict[str, Any]], aliases: list[str],
                     auto_match: bool, saved: dict[str, str]) -> dict[str, Any]:
    wanted = aliases[0]
    id_matches = [t for t in templates if str(t.get('id')) == str(saved.get(wanted))]
    if len(id_matches) == 1:
        chosen = id_matches[0]
        # A saved mapping may legitimately have a different name, chosen manually.
        print(f'MATCH SAVED: {wanted} -> {title_of(chosen)} [{chosen["id"]}]')
        return chosen
    exact = [t for t in templates if title_of(t).strip().casefold() == wanted.strip().casefold()]
    if len(exact) == 1:
        return exact[0]
    if auto_match:
        raise ValueError(f'No unique exact template for {wanted!r}. Rerun without --auto-match, select manually, then reuse the saved mapping.')
    ranked = sorted(templates, key=lambda t: score_title(title_of(t), aliases), reverse=True)[:10]
    print(f'\nEXERCISE MATCH NEEDS REVIEW: {wanted}')
    for ix, t in enumerate(ranked, 1):
        print(f'  {ix}. {title_of(t)}  [id={t.get("id")}]  score={score_title(title_of(t), aliases):.2f}')
    print('  Pick number, paste existing template ID, or q to abort. Never auto-guess machine vs cable.')
    while True:
        choice = input('Template: ').strip()
        if choice.casefold() == 'q':
            raise KeyboardInterrupt
        if choice.isdigit() and 1 <= int(choice) <= len(ranked):
            return ranked[int(choice)-1]
        result = next((t for t in templates if str(t.get('id')) == choice), None)
        if result:
            return result
        print('Invalid selection; try again or type q.')


def build_payloads(templates: list[dict[str, Any]], auto_match: bool,
                   matches_file: Path) -> list[dict[str, Any]]:
    known: dict[str, str] = {}
    if matches_file.exists():
        mapping = json.loads(matches_file.read_text(encoding='utf-8'))
        if not isinstance(mapping, dict):
            raise ValueError('Saved template matches must be a JSON object.')
        known = {str(k): str(v) for k, v in mapping.items()}
    selected: dict[str, dict[str, Any]] = {}
    built = []
    for routine in ROUTINES:
        payload_exercises = []
        human_exercises = []
        used_ids: set[str] = set()
        for ex in routine['exercises']:
            name = ex['aliases'][0]
            if name not in selected:
                selected[name] = resolve_template(templates, ex['aliases'], auto_match, known)
            t = selected[name]
            tid = str(t.get('id', ''))
            if not tid or tid in used_ids:
                raise ValueError(f'Exercise template collision in {routine["title"]}: {name} -> {title_of(t)} [{tid}]. Choose distinct matching exercises.')
            used_ids.add(tid)
            payload_exercises.append({
                'exercise_template_id': t['id'],
                'rest_seconds': ex['rest_seconds'],
                'notes': ex['notes'],
                'sets': prescribed_sets(ex),
            })
            weights = ex.get('set_loads_lb')
            load_str = ('/'.join('?' if w is None else f'{w:g}' for w in weights) + ' lb') if weights else (
                'CALIBRATE' if ex['weight_lb'] is None else f'{ex["weight_lb"]:g} lb')
            human_exercises.append(f'{ex["slot"]} [{ex["role"]}] {title_of(t)}: {ex["sets_count"]}x{ex["rep_min"]}-{ex["rep_max"]}, {load_str}, rest {ex["rest_seconds"]}s')
        built.append({
            'title': routine['title'], 'notes': routine['notes'], 'exercises': payload_exercises,
            'summary': human_exercises,
            'required_sets': routine['required_sets'],
            'preloaded_sets': sum(e['sets_count'] for e in routine['exercises']),
        })
    # Mapping is local and contains IDs only (no credentials). Save it only after
    # all routines resolve, so a partly completed manual review leaves no cache.
    matches_file.parent.mkdir(parents=True, exist_ok=True)
    matches_file.write_text(json.dumps({name: str(t['id']) for name, t in selected.items()}, indent=2), encoding='utf-8')
    return built


def fetch_all(session: Any, endpoint: str, key: str, page_size: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while True:
        response = session.get(f'{BASE_URL}/{endpoint}', headers={'api-key': key},
                               params={'page': page, 'pageSize': page_size}, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f'Unexpected API response from {endpoint}.')
        key_name = {'routines':'routines','exercise_templates':'exercise_templates',
                    'routine_folders':'routine_folders'}[endpoint]
        result.extend(data.get(key_name) or [])
        pages = int(data.get('page_count', 1))
        if page >= pages:
            return result
        page += 1


def api_error(response: Any) -> str:
    try:
        return str(response.json())
    except Exception:
        return str(response.text)[:500]


def preflight_existing(routines: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    v3_titles = {r['title'] for r in ROUTINES}
    found: dict[str, dict[str, Any]] = {}
    for routine in routines:
        title = routine.get('title', '')
        if title not in v3_titles:
            continue
        if title in found:
            raise RuntimeError(f'Duplicate V3 routine title: {title}. Resolve conflict in Hevy before continuing.')
        found[title] = routine
    return found


def save_snapshot(affected: dict[str, dict[str, Any]], backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = backup_dir / f'hevy_before_v3_{stamp}.json'
    with path.open('x', encoding='utf-8') as f:
        json.dump({
            'captured_at_utc': datetime.now(timezone.utc).isoformat(),
            'note': 'Reference snapshot only, not an automatic restoration payload. V2.2 is never overwritten by this script.',
            'routines': list(affected.values())
        }, f, indent=2)
    return path


def get_or_create_folder(session: Any, key: str) -> int:
    folders = fetch_all(session, 'routine_folders', key, 10)
    selected = [f for f in folders if str(f.get('title', '')).casefold() == FOLDER_TITLE.casefold()]
    if len(selected) > 1:
        raise RuntimeError(f'More than one folder named {FOLDER_TITLE!r}; refusing ambiguous placement.')
    if len(selected) == 1:
        return int(selected[0]['id'])
    response = session.post(f'{BASE_URL}/routine_folders', headers={'api-key':key,'Content-Type':'application/json'},
                            json={'routine_folder': {'title':FOLDER_TITLE}},timeout=30)
    if response.status_code not in (200,201):
        raise RuntimeError(f'Folder creation failed: {response.status_code} {api_error(response)}')
    data=response.json()
    folder=data.get('routine_folder',data) if isinstance(data,dict) else data
    return int(folder['id'])


def apply_v3(session: Any, key: str, built: list[dict[str, Any]],
             existing: dict[str, dict[str, Any]], folder_id: int | None) -> None:
    for routine in built:
        common={name:routine[name] for name in ('title','notes','exercises')}
        if routine['title'] in existing:
            routine_id=existing[routine['title']]['id']
            response=session.put(f'{BASE_URL}/routines/{routine_id}', headers={'api-key':key,'Content-Type':'application/json'},
                                 json={'routine':common},timeout=30)
            action='UPDATED'
        else:
            if folder_id is None:
                raise RuntimeError('Cannot create without an existing or newly created V3 folder ID.')
            response=session.post(f'{BASE_URL}/routines', headers={'api-key':key,'Content-Type':'application/json'},
                                  json={'routine':{**common,'folder_id':folder_id}},timeout=30)
            action='CREATED'
        if response.status_code not in (200,201):
            raise RuntimeError(f'{action} {routine["title"]} failed: {response.status_code} {api_error(response)}. Earlier writes may remain; inspect Hevy then rerun.')
        print(f'{action}: {routine["title"]}')


def preview() -> None:
    print('CORE-4 V3 OFFLINE PREVIEW — NO KEY, API CALLS OR WRITES\n')
    for routine in ROUTINES:
        print(f'\n{routine["title"]}: {routine["required_sets"]} REQUIRED primary sets')
        print(f'FOCUS: {routine["focus"]}')
        for ex in routine['exercises']:
            loads=ex.get('set_loads_lb')
            weight=('/'.join('?' if x is None else f'{x:g}' for x in loads) if loads else
                    ('CALIBRATE' if ex['weight_lb'] is None else f'{ex["weight_lb"]:g}'))
            print(f'\n [{ex["role"]}] {ex["slot"]} | {ex["aliases"][0]} | {ex["sets_count"]}x{ex["rep_min"]}-{ex["rep_max"]} @ {weight} lb | {ex["rest_seconds"]}s rest')
            print(' ' + ex['notes'])
    print('\nRules: ONE exercise per numbered slot. All ALT choices are mutually exclusive. OPTIONAL core is extra.')
    print('Upper A incline: 3 heavy sets at 52.5 + back-off at 45 per hand, after regular rest.')
    print('Approved required total: 21 + 18 + 21 + 19 = 79 working sets/week. No routines changed.')


def main() -> int:
    parser=argparse.ArgumentParser(description='Create four Core-4 V3 Hybrid routines in Hevy without touching V2.2.')
    parser.add_argument('--preview',action='store_true',help='Full offline review of all prescriptions/notes. No key or network.')
    parser.add_argument('--apply',action='store_true',help='Write V3 to Hevy after reviewing the online preflight.')
    parser.add_argument('--yes',action='store_true',help='Skip confirmation prompt with --apply.')
    parser.add_argument('--auto-match',action='store_true',help='Only exact-name or previously approved template mappings; abort otherwise.')
    parser.add_argument('--mapping-file',type=Path,default=Path('hevy_v3_template_matches.json'),help='Local file caching user-approved exercise template IDs.')
    parser.add_argument('--backup-dir',type=Path,default=Path('hevy_backups'),help='Local pre-write reference snapshot directory.')
    args=parser.parse_args()
    if args.preview and args.apply:
        parser.error('--preview cannot be combined with --apply')
    validate_program()
    if args.preview:
        preview()
        return 0
    if requests is None:
        print('Please install requests: python -m pip install requests')
        return 2
    key=os.getenv('HEVY_API_KEY','').strip() or getpass.getpass('Hevy API key (hidden): ').strip()
    if not key:
        print('No key supplied; no changes made.')
        return 2
    session=requests.Session()
    response=session.get(f'{BASE_URL}/user/info',headers={'api-key':key},timeout=30)
    if response.status_code!=200:
        print(f'Hevy authentication failed: {response.status_code} {api_error(response)}')
        return 3
    user_info=response.json()
    user=user_info.get('user',user_info) if isinstance(user_info,dict) else user_info
    print('Authenticated'+(f' as {user.get("username")}' if isinstance(user,dict) and user.get('username') else '')+'.')
    print('Fetching exercise templates and V3-only routine IDs for preflight...')
    templates=fetch_all(session,'exercise_templates',key,100)
    built=build_payloads(templates,args.auto_match,args.mapping_file)
    existing_all=fetch_all(session,'routines',key,10)
    existing=preflight_existing(existing_all)
    print('\n=== CORE-4 V3 HYBRID UPLOAD PREVIEW ===')
    for routine in built:
        operation='UPDATE V3 ONLY' if routine['title'] in existing else 'CREATE NEW V3'
        print(f'\n{operation}: {routine["title"]}  | actual work: {routine["required_sets"]} sets; preloaded incl ALT: {routine["preloaded_sets"]} sets')
        for summary in routine['summary']:
            print(' - '+summary)
    if not args.apply:
        print('\nDRY RUN ONLY — no Hevy routines or folders changed. V2.2 and Recovery + Arms retained.')
        print('If every template match is correct, run: python hevy_core4_v3_hybrid_upload.py --apply')
        return 0
    if not args.yes:
        print('\nWill CREATE four V3 routines in a separate folder, or UPDATE only exact V3 titles on rerun.')
        print('Existing V2.2 routines and recorded workouts remain untouched; ALT entries are not extra sets.')
        if input('Type UPLOAD to proceed: ').strip()!='UPLOAD':
            print('Cancelled. No Hevy writes performed.')
            return 0
    # Refresh once after interactive review, before writes; take local snapshot even if
    # this is the first run and the affected-routine list is empty.
    fresh=fetch_all(session,'routines',key,10)
    existing=preflight_existing(fresh)
    snapshot=save_snapshot(existing,args.backup_dir)
    print(f'Pre-write V3 routine snapshot: {snapshot}')
    need_folder=any(r['title'] not in existing for r in built)
    folder_id=get_or_create_folder(session,key) if need_folder else None
    apply_v3(session,key,built,existing,folder_id)
    print('\nV3 upload completed. Open Hevy, confirm all four routines and check the back-off prescription, loads, notes and ALT ordering.')
    print('Critical: perform only ONE exercise per numbered slot. Log no sets for unused ALTs.')
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nStopped. If writes had started, inspect Hevy before rerunning; earlier successful writes may remain.')
        raise SystemExit(130)
    except Exception as exc:
        print(f'Error: {exc}')
        raise SystemExit(5)
