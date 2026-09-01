import html
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = Path(os.getenv("PLAYWRIGHT_PROFILE_DIR", BASE_DIR / "playwright_sno_profile"))
DEBUG_DIR = BASE_DIR / "debug"


def _clean_full_name(full_name, bio):
    full_name = (full_name or "").strip()
    bio = (bio or "").strip()

    if len(full_name) > 60 or " is " in full_name:
        match = re.match(
            r"(?:Sophomore\s+)?((?:[A-Z][A-Za-zÀ-ÿ’'\.-]+\s+){1,4}[A-Z][A-Za-zÀ-ÿ’'\.-]+)\s+is\b",
            bio,
        )

        if match:
            return match.group(1).strip()

    if full_name:
        return full_name

    match = re.match(
        r"(?:Sophomore\s+)?((?:[A-Z][A-Za-zÀ-ÿ’'\.-]+\s+){1,4}[A-Z][A-Za-zÀ-ÿ’'\.-]+)\s+is\b",
        bio,
    )

    if match:
        return match.group(1).strip()

    return full_name


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


def _force_title_value(page, full_name):
    result = page.evaluate(
        """
        (fullName) => {
            const fields = [
                document.querySelector("input#title"),
                document.querySelector("input[placeholder='Full Name']"),
                document.querySelector("textarea.editor-post-title__input"),
                document.querySelector(".editor-post-title__input"),
            ].filter(Boolean);

            if (fields.length === 0) {
                return "title_field_not_found";
            }

            const field = fields[0];
            field.focus();
            field.value = fullName;
            field.setAttribute("value", fullName);
            field.dispatchEvent(new Event("input", { bubbles: true }));
            field.dispatchEvent(new Event("change", { bubbles: true }));
            field.blur();

            return "forced_title_value";
        }
        """,
        full_name,
    )

    return result


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


def _bio_to_html(bio, full_name):
    bio = (bio or "").strip()
    full_name = (full_name or "").strip()

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", bio) if p.strip()]

    if not paragraphs and bio:
        paragraphs = [bio]

    html_paragraphs = []
    name_bolded = False

    for paragraph in paragraphs:
        safe_paragraph = html.escape(paragraph)

        if full_name and not name_bolded:
            safe_name = html.escape(full_name)

            if safe_name in safe_paragraph:
                safe_paragraph = safe_paragraph.replace(
                    safe_name,
                    f"<strong>{safe_name}</strong>",
                    1,
                )
                name_bolded = True

        html_paragraphs.append(f"<p>{safe_paragraph}</p>")

    return "\n".join(html_paragraphs)


def _set_editor_body(page, body_html):
    result = page.evaluate(
        """
        (htmlContent) => {
            if (window.tinyMCE && window.tinyMCE.get("content")) {
                const editor = window.tinyMCE.get("content");
                editor.setContent(htmlContent);
                editor.save();
                return "filled_tinymce_content";
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


def _get_metabox_field_point(page, box_title):
    result = page.evaluate(
        """
        (boxTitle) => {
            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);

                return (
                    rect.width > 20 &&
                    rect.height > 8 &&
                    style.display !== "none" &&
                    style.visibility !== "hidden" &&
                    el.type !== "hidden"
                );
            }

            const wanted = boxTitle.trim().toLowerCase();
            const postboxes = Array.from(document.querySelectorAll(".postbox"));

            let targetBox = null;

            for (const box of postboxes) {
                const heading = box.querySelector(".hndle, h2, h3, .postbox-header");
                const headingText = heading ? (heading.textContent || "").trim().toLowerCase() : "";

                if (headingText === wanted || headingText.includes(wanted)) {
                    targetBox = box;
                    break;
                }
            }

            if (!targetBox) {
                const allHeadings = Array.from(document.querySelectorAll("h2, h3, .hndle, .postbox-header"));

                for (const heading of allHeadings) {
                    const text = (heading.textContent || "").trim().toLowerCase();

                    if (text === wanted || text.includes(wanted)) {
                        targetBox = heading.closest(".postbox") || heading.parentElement;
                        break;
                    }
                }
            }

            if (!targetBox) {
                return {
                    ok: false,
                    reason: "box_not_found:" + boxTitle
                };
            }

            const fields = Array.from(
                targetBox.querySelectorAll("input:not([type]), input[type='text'], textarea")
            ).filter(isVisible);

            if (fields.length === 0) {
                return {
                    ok: false,
                    reason: "field_not_found:" + boxTitle
                };
            }

            const field = fields[0];
            field.scrollIntoView({ block: "center" });

            const rect = field.getBoundingClientRect();

            field.setAttribute("data-sno-metabox-target", boxTitle);

            return {
                ok: true,
                selector: `[data-sno-metabox-target="${boxTitle}"]`,
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2
            };
        }
        """,
        box_title,
    )

    return result


def _fill_metabox_field(page, box_title, value):
    if value is None:
        value = ""

    point = _get_metabox_field_point(page, box_title)

    if not point.get("ok"):
        return point.get("reason", f"metabox_not_found:{box_title}")

    try:
        field = page.locator(point["selector"]).first
        field.scroll_into_view_if_needed(timeout=3000)
        field.click()
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(value)
        field.blur()

        page.evaluate(
            """
            (selector) => {
                const field = document.querySelector(selector);

                if (field) {
                    field.dispatchEvent(new Event("input", { bubbles: true }));
                    field.dispatchEvent(new Event("change", { bubbles: true }));
                    field.blur();
                }
            }
            """,
            point["selector"],
        )

        return "typed_metabox:" + box_title

    except Exception as error:
        return "type_failed:" + box_title + ":" + str(error)


def _clear_metabox_field(page, box_title):
    point = _get_metabox_field_point(page, box_title)

    if not point.get("ok"):
        return point.get("reason", f"metabox_not_found:{box_title}")

    try:
        field = page.locator(point["selector"]).first
        field.scroll_into_view_if_needed(timeout=3000)
        field.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        field.blur()

        page.evaluate(
            """
            (selector) => {
                const field = document.querySelector(selector);

                if (field) {
                    field.value = "";
                    field.setAttribute("value", "");
                    field.dispatchEvent(new Event("input", { bubbles: true }));
                    field.dispatchEvent(new Event("change", { bubbles: true }));
                    field.blur();
                }
            }
            """,
            point["selector"],
        )

        return "cleared_metabox:" + box_title

    except Exception as error:
        return "clear_failed:" + box_title + ":" + str(error)


def _check_staff_year(page, staff_year):
    if not staff_year:
        return "skipped_empty"

    result = page.evaluate(
        """
        (staffYear) => {
            const wanted = staffYear
                .trim()
                .toLowerCase()
                .replace(/[–—]/g, "-")
                .replace(/\s+/g, " ");

            function normalize(text) {
                return (text || "")
                    .trim()
                    .toLowerCase()
                    .replace(/[–—]/g, "-")
                    .replace(/\s+/g, " ");
            }

            function getBoxText(box) {
                const parentLabel = box.closest("label");

                if (parentLabel) {
                    return parentLabel.textContent || "";
                }

                if (box.id) {
                    const labelFor = document.querySelector(`label[for="${box.id}"]`);

                    if (labelFor) {
                        return labelFor.textContent || "";
                    }
                }

                const li = box.closest("li");

                if (li) {
                    return li.textContent || "";
                }

                return "";
            }

            const postboxes = Array.from(document.querySelectorAll(".postbox"));

            let staffBox = null;

            for (const box of postboxes) {
                const heading = box.querySelector(".hndle, h2, h3, .postbox-header");
                const headingText = normalize(heading ? heading.textContent : "");

                if (headingText === "staff years" || headingText.includes("staff years")) {
                    staffBox = box;
                    break;
                }
            }

            if (!staffBox) {
                return "staff_year_box_not_found";
            }

            staffBox.scrollIntoView({ block: "center" });

            // Important: the Staff Years list has its own little scrollbar.
            // Scroll every internal scrollable container so hidden bottom years are reachable.
            const scrollables = Array.from(staffBox.querySelectorAll("*")).filter(el => {
                return el.scrollHeight > el.clientHeight;
            });

            for (const el of scrollables) {
                el.scrollTop = el.scrollHeight;
            }

            const boxes = Array.from(staffBox.querySelectorAll("input[type='checkbox']"));

            let target = null;
            let targetText = "";

            for (const box of boxes) {
                const text = normalize(getBoxText(box));

                if (text === wanted || text.includes(wanted)) {
                    target = box;
                    targetText = getBoxText(box).trim();
                    break;
                }
            }

            if (!target) {
                // Try one more time after forcing scroll to the bottom.
                const inside = staffBox.querySelector(".inside");
                const lists = Array.from(staffBox.querySelectorAll("ul, div"));

                if (inside) {
                    inside.scrollTop = inside.scrollHeight;
                }

                for (const list of lists) {
                    if (list.scrollHeight > list.clientHeight) {
                        list.scrollTop = list.scrollHeight;
                    }
                }

                for (const box of boxes) {
                    const text = normalize(getBoxText(box));

                    if (text === wanted || text.includes(wanted)) {
                        target = box;
                        targetText = getBoxText(box).trim();
                        break;
                    }
                }
            }

            if (!target) {
                const availableYears = boxes.map(box => normalize(getBoxText(box))).filter(Boolean);
                return "staff_year_not_found:" + staffYear + " available=" + availableYears.join(",");
            }

            // Uncheck all other staff years.
            for (const box of boxes) {
                if (box !== target && box.checked) {
                    box.checked = false;
                    box.dispatchEvent(new Event("input", { bubbles: true }));
                    box.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }

            // Check the target year.
            target.checked = true;
            target.setAttribute("checked", "checked");
            target.dispatchEvent(new Event("input", { bubbles: true }));
            target.dispatchEvent(new Event("change", { bubbles: true }));

            target.scrollIntoView({ block: "center" });

            return "staff_year_checked:" + targetText;
        }
        """,
        staff_year,
    )

    return result


def _extract_staff_link(page, site):
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


def create_staff_profile_with_browser(full_name, position, bio):
    site = os.getenv("SNO_SITE", "").rstrip("/")

    if not site:
        return {"ok": False, "link": "", "message": "SNO_SITE is not configured. Copy .env.example to .env first."}
    staff_year = os.getenv("STAFF_YEAR", "2026-2027").strip()

    full_name = _clean_full_name(full_name, bio)
    position = (position or "Reporter").strip()

    if not position:
        position = "Reporter"

    body_html = _bio_to_html(bio, full_name)

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
                f"{site}/wp-admin/post-new.php?post_type=staff_profile",
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

            name_result = _first_visible_fill(
                page,
                [
                    "input#title",
                    "input[placeholder='Full Name']",
                    "textarea.editor-post-title__input",
                    ".editor-post-title__input",
                    "[aria-label='Add title']",
                ],
                full_name,
            )

            forced_name_result = _force_title_value(page, full_name)

            if not name_result and forced_name_result == "title_field_not_found":
                page.screenshot(path=str(DEBUG_DIR / "debug_staff_failed_name.png"), full_page=True)
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Could not fill staff full name. A debug screenshot was saved in debug/.",
                }

            body_result = _set_editor_body(page, body_html)

            if body_result == "failed":
                page.screenshot(path=str(DEBUG_DIR / "debug_staff_failed_bio.png"), full_page=True)
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Could not fill staff bio body. A debug screenshot was saved in debug/.",
                }

            name_result_2 = _first_visible_fill(
                page,
                [
                    "input#title",
                    "input[placeholder='Full Name']",
                    "textarea.editor-post-title__input",
                    ".editor-post-title__input",
                    "[aria-label='Add title']",
                ],
                full_name,
            )

            forced_name_result_2 = _force_title_value(page, full_name)

            position_result = _fill_metabox_field(page, "Staff Position", position)

            # These should stay blank.
            group_result = _clear_metabox_field(page, "Staff Group")
            teaser_result = _clear_metabox_field(page, "Staff Bio Teaser for Story Page")

            year_result = _check_staff_year(page, staff_year)

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
                page.screenshot(path=str(DEBUG_DIR / "debug_staff_failed_save.png"), full_page=True)
                context.close()
                return {
                    "ok": False,
                    "link": "",
                    "message": "Could not click Save Draft. A debug screenshot was saved in debug/.",
                }

            page.wait_for_timeout(3000)
            staff_link = _extract_staff_link(page, site)
            page.screenshot(path=str(DEBUG_DIR / "debug_staff_last_success.png"), full_page=True)

            context.close()

            return {
                "ok": True,
                "link": staff_link,
                "message": (
                    f"Browser automation created a SNO staff profile draft: {staff_link}. "
                    f"Filled name={name_result}/{forced_name_result}/{name_result_2}/{forced_name_result_2}, "
                    f"bio={body_result}, position={position_result}, group={group_result}, "
                    f"teaser={teaser_result}, year={year_result}."
                ),
            }

        except Exception as error:
            try:
                page.screenshot(path=str(DEBUG_DIR / "debug_staff_exception.png"), full_page=True)
            except Exception:
                pass

            context.close()

            return {
                "ok": False,
                "link": "",
                "message": str(error),
            }
