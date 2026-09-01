import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = Path(os.getenv("PLAYWRIGHT_PROFILE_DIR", BASE_DIR / "playwright_sno_profile"))


def main():
    site = os.getenv("SNO_SITE", "").rstrip("/")
    if not site:
        raise RuntimeError("SNO_SITE is not configured. Copy .env.example to .env first.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            slow_mo=150,
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(f"{site}/wp-admin/", wait_until="domcontentloaded")

        print()
        print("A Chromium window opened.")
        print("Log into SNO normally in that browser.")
        print("When you can see the SNO dashboard, return here and press ENTER.")
        input()
        context.close()

        print(f"Login profile saved in {PROFILE_DIR}.")


if __name__ == "__main__":
    main()
