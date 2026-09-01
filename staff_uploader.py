import os

from dotenv import load_dotenv

from browser_sno_staff_client import create_staff_profile_with_browser


load_dotenv()


def create_staff_profile(profile):
    dry_run = os.getenv("DRY_RUN_STAFF", "true").lower() == "true"

    full_name = profile.get("full_name", "")
    position = profile.get("position", "")
    bio = profile.get("bio", "")

    if dry_run:
        return {
            "ok": True,
            "link": "DRY_RUN_STAFF_PROFILE",
            "message": f"DRY RUN: Pretended to create staff profile for {full_name}. No real SNO profile was created.",
        }

    return create_staff_profile_with_browser(
        full_name=full_name,
        position=position,
        bio=bio,
    )
