import csv
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_DIR = BASE_DIR / "sample_data"
STAFF_CSV_PATH = Path(os.getenv("STAFF_PROFILES_CSV", DATA_DIR / "staff_profiles.csv"))
SAMPLE_CSV_PATH = SAMPLE_DIR / "staff_profiles.csv"
FIELDNAMES = ["number", "short_name", "full_name", "position", "bio", "uploaded", "sno_link"]


def _read_path():
    return STAFF_CSV_PATH if STAFF_CSV_PATH.exists() else SAMPLE_CSV_PATH


def get_profiles():
    profiles = []
    path = _read_path()

    if not path.exists():
        return profiles

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for index, row in enumerate(reader):
            row["id"] = str(index)
            for field in FIELDNAMES:
                row.setdefault(field, "")
            profiles.append(row)

    return profiles


def get_profile_by_id(profile_id):
    for profile in get_profiles():
        if profile["id"] == str(profile_id):
            return profile
    return None


def search_profiles(query):
    query = query.lower().strip()
    if not query:
        return get_profiles()

    results = []
    for profile in get_profiles():
        text = " ".join([
            profile.get("short_name", ""),
            profile.get("full_name", ""),
            profile.get("position", ""),
            profile.get("bio", ""),
        ]).lower()
        if query in text:
            results.append(profile)
    return results


def write_profiles(profiles):
    STAFF_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean_profiles = [
        {field: profile.get(field, "") for field in FIELDNAMES}
        for profile in profiles
    ]

    with STAFF_CSV_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(clean_profiles)


def mark_staff_uploaded(profile_id, sno_link="DRY_RUN_STAFF_PROFILE"):
    profiles = get_profiles()
    for profile in profiles:
        if profile["id"] == str(profile_id):
            profile["uploaded"] = "true"
            profile["sno_link"] = sno_link
    write_profiles(profiles)


def export_staff_csv(path=None):
    if path is None:
        path = BASE_DIR / "exports" / "staff_profiles_ready.csv"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    profiles = get_profiles()
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows([
            {field: profile.get(field, "") for field in FIELDNAMES}
            for profile in profiles
        ])
    return path
