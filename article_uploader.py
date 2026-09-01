import os

from dotenv import load_dotenv

from browser_sno_article_client import create_sno_draft_with_browser


load_dotenv()


def upload_article_to_sno(title, subheadline, body_html, author, writer_job_title, category):
    dry_run = os.getenv("DRY_RUN_ARTICLES", "true").lower() == "true"

    if dry_run:
        return {
            "ok": True,
            "link": "DRY_RUN_NO_REAL_SNO_LINK",
            "message": f"DRY RUN: Pretended to upload '{title}' as a full SNO article draft. No real post was created.",
        }

    return create_sno_draft_with_browser(
        title=title,
        subheadline=subheadline,
        body_html=body_html,
        author=author,
        writer_job_title=writer_job_title,
        category=category,
    )
