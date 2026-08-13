#!/usr/bin/env python3
"""
Upload Alex's Core-4 V2 routines to Hevy.

Safety/design choices:
- API key is read from HEVY_API_KEY or prompted securely; never hard-code it.
- Default mode is DRY RUN. Use --apply to write to Hevy.
- Exercise templates are fetched from your own Hevy account and matched by aliases.
- Ambiguous exercise matches are shown for manual selection before anything is written.
- Exact V2 routine titles are updated on reruns; older/non-V2 routines are left untouched.

Usage:
    pip install requests
    python hevy_core4_v2_upload.py
    python hevy_core4_v2_upload.py --apply
    python hevy_core4_v2_upload.py --apply --yes

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
from typing import Any

try:
    import requests
except ImportError:
    print("Missing dependency: requests")
    print("Install it with:  python -m pip install requests")
    sys.exit(1)

BASE_URL = "https://api.hevyapp.com/v1"
FOLDER_TITLE = "Alex Core-4 V2"

LB_PER_KG = 2.2046226218


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


def exercise(
    aliases: list[str],
    sets: int,
    rep_min: int,
    rep_max: int,
    weight_lb: float | None,
    rest_seconds: int,
    notes: str,
) -> dict[str, Any]:
    return {
        "aliases": aliases,
        "sets_count": sets,
        "rep_min": rep_min,
        "rep_max": rep_max,
        "weight_lb": weight_lb,
        "rest_seconds": rest_seconds,
        "notes": notes,
    }


PROGRAM_NOTES = (
    "CORE-4 V2. Complete the Core-4 first; accessories are additions, not requirements. "
    "Progression: add reps before load. Increase load only after every working set reaches "
    "the top of the rep range with clean ROM at the target RIR; when tempted to rush a jump, "
    "repeat that performance for a second exposure. No grinder reps. Most compounds finish "
    "around 2 RIR (RPE ~8); final sets may reach 1 RIR (RPE ~9) if technique is unchanged."
)

# Starting loads are based on the V2 coaching plan. Hevy's API expects kilograms,
# so this script converts the listed pound values before upload.
ROUTINES: list[dict[str, Any]] = [
    {
        "title": "Upper A - Chest + Lats Strength V2",
        "notes": (
            "MONDAY. Upper-body strength/hypertrophy with balanced unilateral + bilateral pulling. "
            "Core-4 first; seated lateral raise is the priority accessory. " + PROGRAM_NOTES
        ),
        "exercises": [
            exercise(
                ["Incline Bench Press (Dumbbell)", "Incline Dumbbell Bench Press", "Incline Dumbbell Press", "Incline DB Press"],
                4, 6, 8, 52.5, 180,
                "Performance press. 15-30° incline. Target ~2 RIR; final set may reach 1 RIR. "
                "Current benchmark: 52.5 lb. Stay here until 4 clean sets reach 8 reps before considering 55 lb."
            ),
            exercise(
                ["Iso-Lateral Low Row", "Iso Lateral Low Row", "Single Arm Iso-Lateral Low Row", "Single Arm Low Row", "Iso-Lateral Row"],
                3, 8, 12, 50, 120,
                "UNILATERAL horizontal pull. Stable torso; drive elbow back without rotating. Target 1-2 RIR."
            ),
            exercise(
                ["Iso-Lateral Chest Press", "Iso Lateral Chest Press", "Chest Press (Machine)", "Machine Chest Press", "Chest Press"],
                3, 8, 12, 45, 120,
                "Secondary chest press. Controlled hypertrophy reps; do not turn this into a second max-effort press. Target ~2 RIR."
            ),
            exercise(
                ["Lat Pulldown", "Lat Pulldown (Cable)", "Cable Lat Pulldown", "Wide Grip Lat Pulldown"],
                3, 8, 10, 115, 90,
                "BILATERAL vertical pull. Drive elbows toward ribs. Start around 115 lb rather than forcing the old 120 lb jump. Target 1-2 RIR."
            ),
            exercise(
                ["Lateral Raise (Dumbbell)", "Dumbbell Lateral Raise", "Seated Lateral Raise", "Seated Dumbbell Lateral Raise", "Lateral Raise"],
                3, 12, 20, 20, 60,
                "PRIORITY ACCESSORY. Seated/strict if possible. No shrugging or torso swing. Start at 20 lb; earn 22.5 through reps and control. Target ~2 RIR."
            ),
        ],
    },
    {
        "title": "Lower A - Quads + Glutes V2",
        "notes": (
            "TUESDAY. One main bilateral quad compound + unilateral quad isolation. "
            "Hack squat OR leg press is the main heavy squat-pattern choice; do not automatically stack both. "
            "Optional after Core-4 if fresh: Pallof press or hip abduction. " + PROGRAM_NOTES
        ),
        "exercises": [
            exercise(
                ["Hack Squat", "Hack Squat (Machine)", "Machine Hack Squat"],
                3, 6, 10, 230, 180,
                "BILATERAL primary quad movement. Controlled depth and bracing. Stop before hips/pelvis shift. Target ~2 RIR."
            ),
            exercise(
                ["Leg Extension (Single Leg)", "Single Leg Extension", "Single-Leg Extension", "Leg Extension - Single Leg", "Leg Extension"],
                3, 10, 15, 40, 75,
                "UNILATERAL quad work. Match ROM and tempo side to side. Add reps before load. Target 1-2 RIR."
            ),
            exercise(
                ["Seated Leg Curl", "Leg Curl (Seated)", "Seated Hamstring Curl"],
                3, 8, 12, 115, 90,
                "BILATERAL hamstring curl. Slow eccentric; full contraction. Target 1-2 RIR."
            ),
            exercise(
                ["Standing Calf Raise", "Calf Raise (Standing)", "Machine Standing Calf Raise"],
                3, 10, 15, 65, 60,
                "Full stretch at the bottom and controlled top. Add reps before load. Target 1-2 RIR."
            ),
        ],
    },
    {
        "title": "Recovery + Arms V2",
        "notes": (
            "WEDNESDAY. Recovery-biased arm work, not a fifth hard upper-body day. Keep most sets at 2-3 RIR; no grinders. "
            "Optional: 10-20 min easy incline walk/bike + mobility. Do not add chest/back/shoulder compounds. "
            "If Thursday Upper B performance drops, remove the final curl + extension pair first."
        ),
        "exercises": [
            exercise(
                ["Preacher Curl", "Preacher Curl (Machine)", "Machine Preacher Curl", "Biceps Curl (Machine)"],
                3, 8, 12, 65, 75,
                "Primary biceps work. Controlled stretch; no shoulder roll. Keep ~2 RIR."
            ),
            exercise(
                ["Triceps Pushdown (Rope)", "Rope Triceps Pushdown", "Triceps Rope Pushdown", "Cable Triceps Pushdown", "Triceps Pushdown"],
                3, 10, 15, 42.5, 60,
                "Primary triceps work. Elbows fixed; full extension. Keep ~2 RIR."
            ),
            exercise(
                ["Incline Dumbbell Curl", "Seated Dumbbell Curl", "Dumbbell Curl", "Bicep Curl (Dumbbell)", "Dumbbell Biceps Curl"],
                2, 10, 15, 22.5, 60,
                "SECONDARY / OPTIONAL if recovery is good. Keep 2-3 RIR. Do not chase load before Thursday Upper B."
            ),
            exercise(
                ["Overhead Triceps Extension (Cable)", "Cable Overhead Triceps Extension", "Overhead Cable Triceps Extension", "Triceps Extension (Cable)", "Cable Triceps Extension"],
                2, 10, 15, 35, 60,
                "SECONDARY / OPTIONAL if recovery is good. Long-head focus; controlled stretch. Keep 2-3 RIR."
            ),
        ],
    },
    {
        "title": "Upper B - Shoulders + V-Taper V2",
        "notes": (
            "THURSDAY. V-taper emphasis. Unilateral vertical pull + bilateral horizontal pull. "
            "The new plate-loaded single-arm pulldown must be calibrated rather than copied from the old stack machine. " + PROGRAM_NOTES
        ),
        "exercises": [
            exercise(
                ["Iso-Lateral Pulldown", "Iso Lateral Pulldown", "Hammer Strength Iso-Lateral Pulldown", "Single Arm Lat Pulldown", "Single-Arm Lat Pulldown"],
                3, 8, 12, None, 90,
                "UNILATERAL vertical pull. NEW MACHINE: calibrate the first session. Choose a load that gives ~10 clean reps at 2-3 RIR. "
                "Then keep that load until all 3 sets reach 12 with clean ROM before adding the smallest plate jump."
            ),
            exercise(
                ["Seated Overhead Press (Dumbbell)", "Seated Dumbbell Shoulder Press", "Dumbbell Shoulder Press", "Shoulder Press (Dumbbell)"],
                3, 6, 10, 35, 120,
                "Primary press on Upper B. Current benchmark ~35 lb. Target ~2 RIR; no grinder reps."
            ),
            exercise(
                ["T Bar Row", "T-Bar Row", "Chest Supported T-Bar Row", "Chest-Supported T-Bar Row", "T Bar Row (Chest Supported)"],
                3, 8, 10, 70, 120,
                "BILATERAL horizontal pull. Prefer chest-supported. Stable torso; full scapular movement. Target 1-2 RIR."
            ),
            exercise(
                ["Cable Fly Crossover", "Low Cable Fly Crossover", "Cable Crossover", "Cable Fly", "Chest Fly (Cable)"],
                3, 10, 15, 17, 75,
                "Direct chest hypertrophy without extra heavy pressing. Controlled stretch and squeeze. Target 1-2 RIR."
            ),
            exercise(
                ["Lateral Raise (Cable)", "Cable Lateral Raise", "Single Arm Cable Lateral Raise", "Single-Arm Cable Lateral Raise"],
                3, 12, 20, 12.5, 60,
                "UNILATERAL side-delt work. Strict reps; lead with elbow; avoid shrugging. Add reps before load. Target ~2 RIR."
            ),
        ],
    },
    {
        "title": "Lower B - Posterior + Stability V2",
        "notes": (
            "FRIDAY. Posterior-chain + unilateral stability. Core-4 only is a complete workout. "
            "Optional after Core-4: calves OR Pallof press, not both by default. Avoid stacking extra back extensions/carries onto heavy hinge work. " + PROGRAM_NOTES
        ),
        "exercises": [
            exercise(
                ["Hip Thrust (Machine)", "Hip Thrust Machine", "Machine Hip Thrust", "Hip Thrust"],
                3, 8, 10, 140, 120,
                "BILATERAL glute work. Pause at lockout without lumbar extension. Target ~2 RIR."
            ),
            exercise(
                ["Romanian Deadlift (Dumbbell)", "Dumbbell Romanian Deadlift", "Dumbbell RDL", "Romanian Deadlift"],
                3, 8, 10, 45, 120,
                "BILATERAL hinge. Weight listed is per dumbbell. Slow eccentric; stop ROM before spinal position changes. Target 2-3 RIR."
            ),
            exercise(
                ["Reverse Lunge (Dumbbell)", "Dumbbell Reverse Lunge", "Reverse Lunge", "Dumbbell Lunge"],
                3, 8, 10, 35, 90,
                "UNILATERAL glute/quad work. Weight listed is per dumbbell if using two DBs. Stable pelvis. Stay in rep range before increasing load. Target ~2 RIR."
            ),
            exercise(
                ["Standing Leg Curl", "Leg Curl (Standing)", "Single Leg Standing Leg Curl", "Single-Leg Standing Leg Curl", "Standing Hamstring Curl"],
                3, 8, 12, 60, 90,
                "UNILATERAL hamstring curl if machine permits. Controlled return; equal reps both sides. Target 1-2 RIR."
            ),
        ],
    },
]


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
    normalized_aliases = {normalize(a) for a in aliases}
    exact = [t for t in templates if normalize(title_of(t)) in normalized_aliases]
    if len(exact) == 1:
        return exact[0]

    ranked = sorted(
        ((score_title(title_of(t), aliases), t) for t in templates),
        key=lambda x: x[0],
        reverse=True,
    )
    top = ranked[:8]

    if auto_match and top and top[0][0] >= 0.80:
        return top[0][1]

    if top and top[0][0] >= 0.92 and (len(top) == 1 or top[0][0] - top[1][0] >= 0.10):
        return top[0][1]

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


def build_payloads(templates: list[dict[str, Any]], auto_match: bool) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    match_cache: dict[tuple[str, ...], dict[str, Any]] = {}

    for routine in ROUTINES:
        payload_exercises = []
        display_exercises = []
        for ex in routine["exercises"]:
            cache_key = tuple(ex["aliases"])
            if cache_key not in match_cache:
                match_cache[cache_key] = resolve_template(templates, ex["aliases"], auto_match)
            template = match_cache[cache_key]

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
            weight_text = "CALIBRATE" if ex["weight_lb"] is None else f"{ex['weight_lb']:g} lb"
            display_exercises.append(
                f"{title_of(template)} — {ex['sets_count']} x {ex['rep_min']}-{ex['rep_max']} @ {weight_text}; rest {ex['rest_seconds']}s"
            )

        built.append(
            {
                "title": routine["title"],
                "notes": routine["notes"],
                "exercises": payload_exercises,
                "display_exercises": display_exercises,
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


def upsert_routines(
    session: requests.Session,
    key: str,
    folder_id: int,
    built: list[dict[str, Any]],
) -> None:
    existing = fetch_all(session, "routines", key, 10)
    by_title = {str(r.get("title", "")): r for r in existing}

    for routine in built:
        title = routine["title"]
        common = {
            "title": title,
            "notes": routine["notes"],
            "exercises": routine["exercises"],
        }

        if title in by_title:
            routine_id = by_title[title]["id"]
            # Hevy's current PUT routine schema does not include folder_id.
            body = {"routine": common}
            response = session.put(
                f"{BASE_URL}/routines/{routine_id}",
                headers={"api-key": key, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            action = "UPDATED"
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
                f"{action} failed for {title}: {response.status_code} {api_error(response)}"
            )
        print(f"{action}: {title}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Alex Core-4 V2 routines to Hevy")
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
        help="Automatically accept the strongest exercise-template match when score >= 0.80. Interactive confirmation is safer.",
    )
    args = parser.parse_args()

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

    print("\n=== CORE-4 V2 UPLOAD PLAN ===")
    for routine in built:
        print(f"\n{routine['title']}")
        for line in routine["display_exercises"]:
            print(f"  - {line}")

    if not args.apply:
        print("\nDRY RUN ONLY — nothing was written to Hevy.")
        print("If the exercise matches above look correct, run:")
        print("  python hevy_core4_v2_upload.py --apply")
        return 0

    if not args.yes:
        print("\nThis will create/update ONLY the exact V2 titles shown above.")
        print("Older routines with different titles will not be changed.")
        confirmation = input("Type UPLOAD to continue: ").strip()
        if confirmation != "UPLOAD":
            print("Cancelled. Nothing was written.")
            return 0

    folder_id = get_or_create_folder(session, key, apply_changes=True)
    if folder_id is None:
        raise RuntimeError("Could not resolve Core-4 V2 folder ID.")

    upsert_routines(session, key, folder_id, built)
    print("\nDone. Open Hevy and verify exercise choices, displayed imperial weights, and routine order before your first session.")
    print("Important: the new Hammer Strength iso-pulldown intentionally has no starting weight; calibrate it on the first session.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.RequestException as exc:
        print(f"Network/API error: {exc}")
        raise SystemExit(4)
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(5)
