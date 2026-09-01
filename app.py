import os
import secrets
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, send_file

from article_loader import load_article
from article_schedule import (
    get_schedule,
    get_today_articles,
    get_upcoming_articles,
    get_article_by_id,
    mark_article_uploaded,
    search_articles_by_student,
)
from article_uploader import upload_article_to_sno

from staff_bio_extractor import extract_profiles_from_pdf, save_profiles_csv
from staff_data import (
    get_profiles,
    get_profile_by_id,
    search_profiles,
    mark_staff_uploaded,
    export_staff_csv,
    STAFF_CSV_PATH,
)
from staff_uploader import create_staff_profile


BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
POSITIONS_CSV = BASE_DIR / "sample_data" / "staff_positions.csv"


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/articles")
def articles_index():
    return render_template(
        "articles_index.html",
        today_articles=get_today_articles(),
        upcoming_articles=get_upcoming_articles(limit=10),
        full_schedule=get_schedule(),
    )


@app.route("/articles/search", methods=["POST"])
def articles_search():
    student_name = request.form.get("student_name", "").strip()

    if not student_name:
        flash("Enter a student name.")
        return redirect(url_for("articles_index"))

    return render_template(
        "articles_search.html",
        student_name=student_name,
        results=search_articles_by_student(student_name),
    )


@app.route("/articles/preview/<article_id>")
def article_preview(article_id):
    article = get_article_by_id(article_id)

    if article is None:
        flash("Article not found.")
        return redirect(url_for("articles_index"))

    title_guess, html_content, plain_text = load_article(article["article_file"])
    article_title = article.get("title") or title_guess

    return render_template(
        "article_preview.html",
        article=article,
        article_title=article_title,
        html_content=html_content,
        plain_text=plain_text,
    )


@app.route("/articles/upload/<article_id>", methods=["POST"])
def article_upload(article_id):
    article = get_article_by_id(article_id)

    if article is None:
        flash("Article not found.")
        return redirect(url_for("articles_index"))

    if article.get("uploaded", "").lower() == "true":
        flash("This article is already marked uploaded. Duplicate upload blocked.")
        return redirect(url_for("article_preview", article_id=article_id))

    title_guess, html_content, plain_text = load_article(article["article_file"])
    final_title = article.get("title") or title_guess

    result = upload_article_to_sno(
        title=final_title,
        subheadline=article.get("subheadline", ""),
        body_html=html_content,
        author=article.get("author", ""),
        writer_job_title=article.get("writer_job_title", "Reporter"),
        category=article.get("category", "") or article.get("section", ""),
    )

    if result["ok"]:
        mark_article_uploaded(article_id, result.get("link", ""))
        flash(result["message"])
    else:
        flash("Upload failed: " + result["message"])

    return redirect(url_for("article_preview", article_id=article_id))


@app.route("/staff")
def staff_index():
    profiles = get_profiles()
    missing_bio_count = sum(1 for p in profiles if not p.get("bio"))
    reporter_count = sum(1 for p in profiles if p.get("position") == "Reporter")
    created_count = sum(1 for p in profiles if p.get("uploaded", "").lower() == "true")

    return render_template(
        "staff_index.html",
        profiles=profiles,
        missing_bio_count=missing_bio_count,
        reporter_count=reporter_count,
        created_count=created_count,
    )


@app.route("/staff/search", methods=["POST"])
def staff_search():
    query = request.form.get("query", "").strip()

    return render_template(
        "staff_search.html",
        query=query,
        profiles=search_profiles(query),
    )


@app.route("/staff/preview/<profile_id>")
def staff_preview(profile_id):
    profile = get_profile_by_id(profile_id)

    if profile is None:
        flash("Profile not found.")
        return redirect(url_for("staff_index"))

    return render_template("staff_preview.html", profile=profile)


@app.route("/staff/upload_pdf", methods=["POST"])
def staff_upload_pdf():
    uploaded = request.files.get("bio_pdf")

    if uploaded is None or uploaded.filename == "":
        flash("Upload a staff bio PDF first.")
        return redirect(url_for("staff_index"))

    if not uploaded.filename.lower().endswith(".pdf"):
        flash("Please upload a PDF file.")
        return redirect(url_for("staff_index"))

    save_path = UPLOAD_DIR / "latest_staff_bios.pdf"
    uploaded.save(save_path)

    profiles = extract_profiles_from_pdf(
        pdf_path=save_path,
        positions_csv=POSITIONS_CSV,
    )

    save_profiles_csv(profiles, STAFF_CSV_PATH)

    flash(f"Extracted {len(profiles)} staff profiles from the PDF.")
    return redirect(url_for("staff_index"))


@app.route("/staff/create/<profile_id>", methods=["POST"])
def staff_create(profile_id):
    profile = get_profile_by_id(profile_id)

    if profile is None:
        flash("Profile not found.")
        return redirect(url_for("staff_index"))

    result = create_staff_profile(profile)

    if result["ok"]:
        mark_staff_uploaded(profile_id, result.get("link", ""))
        flash(result["message"])
    else:
        flash("Staff profile creation failed: " + result["message"])

    return redirect(url_for("staff_preview", profile_id=profile_id))


@app.route("/staff/create_batch", methods=["POST"])
def staff_create_batch():
    batch_action = request.form.get("batch_action", "").strip()
    selected_ids = request.form.getlist("profile_ids")
    profiles = get_profiles()

    if batch_action == "selected":
        if not selected_ids:
            flash("Select at least one staff profile first.")
            return redirect(url_for("staff_index"))
        ids_to_create = selected_ids

    elif batch_action == "all_not_created":
        ids_to_create = [
            profile["id"]
            for profile in profiles
            if profile.get("uploaded", "").lower() != "true"
        ]

        if not ids_to_create:
            flash("No uncreated staff profiles found.")
            return redirect(url_for("staff_index"))

    elif batch_action == "all_profiles":
        ids_to_create = [profile["id"] for profile in profiles]

        if not ids_to_create:
            flash("No staff profiles found.")
            return redirect(url_for("staff_index"))

    else:
        flash("Unknown batch action.")
        return redirect(url_for("staff_index"))

    success_count = 0
    failure_messages = []

    for profile_id in ids_to_create:
        profile = get_profile_by_id(profile_id)

        if profile is None:
            failure_messages.append(f"Profile ID {profile_id} was not found.")
            continue

        result = create_staff_profile(profile)

        if result["ok"]:
            success_count += 1
            mark_staff_uploaded(profile_id, result.get("link", ""))
        else:
            name = profile.get("full_name", f"ID {profile_id}")
            failure_messages.append(f"{name}: {result['message']}")

    if success_count:
        flash(f"Created {success_count} staff profile draft(s).")

    if failure_messages:
        flash("Some profiles failed: " + " | ".join(failure_messages[:5]))

        if len(failure_messages) > 5:
            flash(f"{len(failure_messages) - 5} more profile(s) also failed.")

    return redirect(url_for("staff_index"))


@app.route("/staff/export_csv")
def staff_export_csv():
    path = export_staff_csv()
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
        use_reloader=False,
    )
