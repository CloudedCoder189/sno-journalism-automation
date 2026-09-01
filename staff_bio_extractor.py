import csv
import re
from pathlib import Path

import fitz


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_POSITION = "Reporter"
DEFAULT_POSITIONS_CSV = BASE_DIR / "sample_data" / "staff_positions.csv"


def load_positions_csv(path):
    path = Path(path)

    if not path.exists():
        return {}

    positions = {}

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            name = row.get("name", "").strip()
            position = row.get("position", "").strip()

            if name and position:
                positions[name.lower()] = position

    return positions


def clean_chunk(chunk):
    lines = []

    for raw in chunk.splitlines():
        line = raw.strip()

        if not line:
            continue

        low = line.lower()

        if low.startswith("edited") or low.startswith("finalized") or low.startswith("copy:"):
            continue

        if line in {"CLM", "JJ", "HA", "We I", "FINALIZED"}:
            continue

        if re.fullmatch(r"[A-Z]{1,3}\.?", line):
            continue

        if re.fullmatch(r"\[.*\]", line):
            continue

        lines.append(line)

    if len(lines) > 1 and " is " not in lines[0] and len(lines[0].split()) <= 2 and re.search(r"\bis\b", lines[1]):
        lines = lines[1:]

    bio = " ".join(lines)
    bio = re.sub(r"\s+", " ", bio).strip()

    return bio


def full_name_from_bio(bio, short_name):
    match = re.match(
        r"Sophomore\s+((?:[A-Z][A-Za-zÀ-ÿ’'\.-]+\s+){0,4}[A-Z][A-Za-zÀ-ÿ’'\.-]+)\s+is\b",
        bio,
    )

    if match:
        return match.group(1).strip()

    match = re.match(
        r"((?:[A-Z][A-Za-zÀ-ÿ’'\.-]+\s+){1,4}[A-Z][A-Za-zÀ-ÿ’'\.-]+)\s+is\b",
        bio,
    )

    if match:
        return match.group(1).strip()

    return short_name.replace("?", "").strip()


def lookup_position(short_name, full_name, positions):
    short_key = short_name.replace("?", "").strip().lower()
    full_key = full_name.strip().lower()

    if full_key in positions:
        return positions[full_key]

    if short_key in positions:
        return positions[short_key]

    first = full_name.split()[0].lower() if full_name.split() else short_key

    if first in positions:
        return positions[first]

    return DEFAULT_POSITION


def extract_profiles_from_pdf(pdf_path, positions_csv=DEFAULT_POSITIONS_CSV):
    pdf_path = Path(pdf_path)
    positions = load_positions_csv(positions_csv)

    document = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in document)

    entry_pattern = re.compile(r"(?m)^\s*(\d+)\.\s*([^\n]+)")
    matches = list(entry_pattern.finditer(text))

    profiles = []

    for index, match in enumerate(matches):
        number = match.group(1)
        short_name = match.group(2).strip()

        chunk_start = match.end()
        chunk_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[chunk_start:chunk_end]

        bio = clean_chunk(chunk)
        full_name = full_name_from_bio(bio, short_name)
        position = lookup_position(short_name, full_name, positions)

        profiles.append({
            "number": number,
            "short_name": short_name,
            "full_name": full_name,
            "position": position,
            "bio": bio,
            "uploaded": "false",
            "sno_link": "",
        })

    return profiles


def save_profiles_csv(profiles, csv_path=BASE_DIR / "data" / "staff_profiles.csv"):
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["number", "short_name", "full_name", "position", "bio", "uploaded", "sno_link"]

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(profiles)
