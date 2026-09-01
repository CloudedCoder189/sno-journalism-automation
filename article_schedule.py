import csv
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_DIR = BASE_DIR / "sample_data"
CSV_PATH = Path(os.getenv("PUBLISHING_SCHEDULE_CSV", DATA_DIR / "publishing_schedule.csv"))
SAMPLE_CSV_PATH = SAMPLE_DIR / "publishing_schedule.csv"

FIELDNAMES = [
    "publish_date",
    "student_name",
    "title",
    "subheadline",
    "section",
    "category",
    "article_file",
    "author",
    "writer_job_title",
    "uploaded",
    "sno_link",
]


def get_today_string():
    override = os.getenv("TODAY_OVERRIDE", "").strip()
    return override if override else date.today().isoformat()


def _parse_date(date_text):
    return datetime.strptime(date_text, "%Y-%m-%d").date()


def _read_path():
    return CSV_PATH if CSV_PATH.exists() else SAMPLE_CSV_PATH


def get_schedule():
    rows = []
    path = _read_path()

    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for index, row in enumerate(reader):
            row["id"] = str(index)

            for field in FIELDNAMES:
                row.setdefault(field, "")

            rows.append(row)

    rows.sort(key=lambda row: row.get("publish_date", "9999-99-99"))
    return rows


def write_schedule(rows):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean_rows = [{field: row.get(field, "") for field in FIELDNAMES} for row in rows]

    with CSV_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(clean_rows)


def get_today_articles():
    today = get_today_string()
    return [row for row in get_schedule() if row.get("publish_date") == today]


def get_upcoming_articles(limit=10):
    today = _parse_date(get_today_string())
    upcoming = []

    for row in get_schedule():
        try:
            article_date = _parse_date(row.get("publish_date", ""))
        except ValueError:
            continue

        if article_date > today:
            upcoming.append(row)

    return upcoming[:limit]


def get_article_by_id(article_id):
    for row in get_schedule():
        if row["id"] == str(article_id):
            return row
    return None


def mark_article_uploaded(article_id, sno_link):
    rows = get_schedule()

    for row in rows:
        if row["id"] == str(article_id):
            row["uploaded"] = "true"
            row["sno_link"] = sno_link
            break

    write_schedule(rows)


def search_articles_by_student(student_name):
    student_name = student_name.lower().strip()
    results = []

    for row in get_schedule():
        row_name = row.get("student_name", "").lower().strip()
        author = row.get("author", "").lower().strip()

        if student_name in row_name or student_name in author:
            results.append(row)

    return results
