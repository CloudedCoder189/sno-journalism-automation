import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = Path(os.getenv("PLAYWRIGHT_PROFILE_DIR", BASE_DIR / "playwright_sno_profile"))
DEBUG_DIR = BASE_DIR / "debug"


def _first_visible_fill(page, selectors, value, timeout=3000):
    if value is None:
        value = ""

    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            loc.fill(value)
            return selector
        except Exception:
            pass

    return None


def _first_visible_click(page, selectors, timeout=5000):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return selector
        except Exception:
            pass

    return None


def _type_into_visible_sno_field(page, field_label, value):
    if not value:
        return "skipped_empty"

    try:
        loc = page.get_by_placeholder(field_label).first
        loc.wait_for(state="visible", timeout=1500)
        loc.click()
        loc.fill(value)
        return f"filled_by_placeholder:{field_label}"
    except Exception:
        pass

    try:
        loc = page.get_by_text(field_label, exact=True).first
        loc.wait_for(state="visible", timeout=2500)
        loc.click()
        page.wait_for_timeout(200)
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(value)
        page.wait_for_timeout(200)
        return f"typed_by_visible_text:{field_label}"
    except Exception:
        pass

    return f"not_found:{field_label}"


def _set_story_body(page, body_html):
    result = page.evaluate(
        """
        (htmlContent) => {
            if (window.tinyMCE && window.tinyMCE.get("content")) {
                const editor = window.tinyMCE.get("content");
                editor.setContent(htmlContent);
                editor.save();
                return "filled_tinymce_content";
            }

            if (window.tinyMCE && window.tinyMCE.activeEditor) {
                const editor = window.tinyMCE.activeEditor;
                editor.setContent(htmlContent);
                editor.save();
                return "filled_tinymce_active";
            }

            const textarea = document.querySelector("#content");

            if (textarea) {
                textarea.value = htmlContent;
                textarea.dispatchEvent(new Event("input", { bubbles: true }));
                textarea.dispatchEvent(new Event("change", { bubbles: true }));
                return "filled_textarea_content";
            }

            return "failed";
        }
        """,
        body_html,
    )

    return result


def _check_category(page, category):
    if not category:
        return "skipped_empty"

    result = page.evaluate(
        """
        (categoryName) => {
            const targetName = categoryName.trim().toLowerCase();

            const categoryRoot =
                document.querySelector("#categorydiv") ||
                document.querySelector("#side-sortables") ||
                document;

            const allBoxes = Array.from(
                categoryRoot.querySelectorAll("input[type='checkbox']")
            );

            function getBoxText(box) {
                const labelByParent = box.closest("label");

                if (labelByParent) {
                    return (labelByParent.textContent || "").trim();
                }

                if (box.id) {
                    const labelByFor = document.querySelector(`label[for="${box.id}"]`);

                    if (labelByFor) {
                        return (labelByFor.textContent || "").trim();
                    }
                }

                const li = box.closest("li");

                if (li) {
                    return (li.textContent || "").trim();
                }

                return "";
            }

            const exactMatches = allBoxes.filter(box => {
                const text = getBoxText(box).toLowerCase();
                return text === targetName;
            });

            const containsMatches = allBoxes.filter(box => {
                const text = getBoxText(box).toLowerCase();
                return text.includes(targetName);
            });

            const targetBoxes = exactMatches.length > 0 ? exactMatches : containsMatches;

            if (targetBoxes.length === 0) {
                return "category_not_found:" + categoryName;
            }

            for (const box of allBoxes) {
                const isTarget = targetBoxes.includes(box);

                if (!isTarget && box.checked) {
                    box.scrollIntoView({ block: "center" });
                    box.click();
                    box.dispatchEvent(new Event("input", { bubbles: true }));
                    box.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }

            for (const box of targetBoxes) {
                if (!box.checked) {
                    box.scrollIntoView({ block: "center" });
                    box.click();
                }

                box.dispatchEvent(new Event("input", { bubbles: true }));
                box.dispatchEvent(new Event("change", { bubbles: true }));
            }

            return "category_checked:" + getBoxText(targetBoxes[0]);
        }
        """,
        category,
    )

    return result


def _extract_story_link(page, site):
    try:
        page.wait_for_timeout(2000)

        links = page.eval_on_selector_all(
            "a",
            """
            (els, site) => els
                .map(a => a.href)
                .filter(h => h && h.startsWith(site))
            """,
            site,
        )

        for href in links:
            if (
                "wp-admin" not in href
                and "wp-login" not in href
                and "action=logout" not in href
                and href != site + "/"
            ):
                return href

    except Exception:
        pass

    return page.url


def create_sno_draft_with_browser(
    title,
    subheadline,
    body_html,
    author,
    writer_job_title,
    category,
):
    site = os.getenv("SNO_SITE", "").rstrip("/")

    if not site:
        return {"ok": False, "link": "", "message": "SNO_SITE is not configured. Copy .env.example to .env first."}

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            slow_mo=150,
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(
                f"{site}/wp-admin/post-new.php",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            if "wp-login.php" in page.url or "login" in page.url.lower():
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Login required. Run py -3.13 prepare_sno_login.py first, then try again.",
                }

            title_result = _first_visible_fill(
                page,
                [
                    "input#title",
                    "textarea.editor-post-title__input",
                    ".editor-post-title__input",
                    "[aria-label='Add title']",
                ],
                title,
            )

            if not title_result:
                page.screenshot(path=str(DEBUG_DIR / "debug_article_failed_title.png"), full_page=True)
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Could not fill SNO title. A debug screenshot was saved in debug/.",
                }

            deck_result = _type_into_visible_sno_field(page, "Secondary Headline (Deck)", subheadline)
            author_result = _type_into_visible_sno_field(page, "Writer's Name", author)
            job_result = _type_into_visible_sno_field(page, "Writer's Job Title", writer_job_title)

            body_result = _set_story_body(page, body_html)

            if body_result == "failed":
                page.screenshot(path=str(DEBUG_DIR / "debug_article_failed_body.png"), full_page=True)
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Could not fill SNO Story Body. A debug screenshot was saved in debug/.",
                }

            category_result = _check_category(page, category)

            save_result = _first_visible_click(
                page,
                [
                    "input#save-post",
                    "button:has-text('Save Draft')",
                    "button:has-text('Save draft')",
                    "button.editor-post-save-draft",
                ],
                timeout=8000,
            )

            if not save_result:
                page.screenshot(path=str(DEBUG_DIR / "debug_article_failed_save.png"), full_page=True)
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Could not click Save Draft. A debug screenshot was saved in debug/.",
                }

            page.wait_for_timeout(3000)
            story_link = _extract_story_link(page, site)
            page.screenshot(path=str(DEBUG_DIR / "debug_article_last_success.png"), full_page=True)
            context.close()

            return {
                "ok": True,
                "link": story_link,
                "message": (
                    f"Browser automation created a SNO article draft: {story_link}. "
                    f"Filled title={title_result}, deck={deck_result}, author={author_result}, "
                    f"job_title={job_result}, body={body_result}, category={category_result}."
                ),
            }

        except Exception as error:
            try:
                page.screenshot(path=str(DEBUG_DIR / "debug_article_exception.png"), full_page=True)
            except Exception:
                pass

            context.close()

            return {
                "ok": False,
                "link": "",
                "message": str(error),
            }
