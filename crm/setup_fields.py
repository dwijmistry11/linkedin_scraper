#!/usr/bin/env python3
"""
Create custom objects and fields in Twenty CRM for the LinkedIn scraper.

Usage:
    python3 setup_fields.py --url https://crm.3dsurgical.com --key YOUR_API_KEY

Idempotent — checks for existing objects/fields before creating.
"""

import argparse
import json
import sys
import requests

API_KEY = ""
BASE_URL = ""


def headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# ── Custom objects to create ──────────────────────────────────────

CUSTOM_OBJECTS = [
    {
        "nameSingular": "companyPost",
        "namePlural": "companyPosts",
        "labelSingular": "Company Post",
        "labelPlural": "Company Posts",
        "icon": "IconArticle",
        "description": "LinkedIn posts discovered from monitored companies",
    },
    {
        "nameSingular": "postEngagement",
        "namePlural": "postEngagements",
        "labelSingular": "Post Engagement",
        "labelPlural": "Post Engagements",
        "icon": "IconThumbUp",
        "description": "Tracks which users reacted/reposted which posts",
    },
]

# ── Fields per object ─────────────────────────────────────────────

# Fields for existing People object
PEOPLE_FIELDS = [
    {"name": "linkedinUrl", "label": "LinkedIn URL", "type": "LINKS"},
    {"name": "intro", "label": "Intro / About", "type": "RICH_TEXT"},
    {"name": "openToWork", "label": "Open to Work", "type": "BOOLEAN"},
    {"name": "engagementSource", "label": "Engagement Source", "type": "TEXT"},
    {"name": "experiencesJson", "label": "Experiences (JSON)", "type": "RAW_JSON"},
    {"name": "educationsJson", "label": "Educations (JSON)", "type": "RAW_JSON"},
    {"name": "profileScrapedAt", "label": "Profile Scraped At", "type": "DATE_TIME"},
    {"name": "discoveredFromCompany", "label": "Discovered From Company", "type": "TEXT"},
]

# Fields for existing Companies object
COMPANY_FIELDS = [
    {"name": "linkedinUrl", "label": "LinkedIn URL", "type": "LINKS"},
    {"name": "industry", "label": "Industry", "type": "TEXT"},
    {"name": "employeeCount", "label": "Employee Count", "type": "NUMBER"},
    {"name": "founded", "label": "Founded", "type": "TEXT"},
    {"name": "aboutUs", "label": "About Us", "type": "RICH_TEXT"},
    {"name": "specialties", "label": "Specialties", "type": "TEXT"},
    {"name": "companyType", "label": "Company Type", "type": "TEXT"},
    {"name": "lastPostScrapedAt", "label": "Last Post Scraped At", "type": "DATE_TIME"},
]

# Fields for scrapeRun custom object (already created, we just add fields)
SCRAPE_RUN_FIELDS = [
    {"name": "companyLinkedinUrl", "label": "Company LinkedIn URL", "type": "TEXT"},
    {"name": "companyCrmId", "label": "Company CRM ID", "type": "TEXT"},
    {"name": "status", "label": "Status", "type": "TEXT"},
    {"name": "phase", "label": "Phase", "type": "TEXT"},
    {"name": "progressPercent", "label": "Progress %", "type": "NUMBER"},
    {"name": "progressMessage", "label": "Progress Message", "type": "TEXT"},
    {"name": "errorMessage", "label": "Error Message", "type": "TEXT"},
    {"name": "totalPostsFound", "label": "Total Posts Found", "type": "NUMBER"},
    {"name": "postsProcessed", "label": "Posts Processed", "type": "NUMBER"},
    {"name": "totalUsersFound", "label": "Total Users Found", "type": "NUMBER"},
    {"name": "newUsersFound", "label": "New Users Found", "type": "NUMBER"},
    {"name": "profilesScraped", "label": "Profiles Scraped", "type": "NUMBER"},
    {"name": "profilesToScrape", "label": "Profiles To Scrape", "type": "NUMBER"},
    {"name": "usersSynced", "label": "Users Synced", "type": "NUMBER"},
    {"name": "resumeStateJson", "label": "Resume State (JSON)", "type": "TEXT"},
    {"name": "sessionIdsJson", "label": "Session IDs (JSON)", "type": "TEXT"},
]

# Fields for companyPost custom object
COMPANY_POST_FIELDS = [
    {"name": "companyLinkedinUrl", "label": "Company LinkedIn URL", "type": "TEXT"},
    {"name": "urn", "label": "URN", "type": "TEXT"},
    {"name": "linkedinUrl", "label": "Post URL", "type": "TEXT"},
    {"name": "postText", "label": "Post Text", "type": "TEXT"},
    {"name": "postedDate", "label": "Posted Date", "type": "TEXT"},
    {"name": "reactionsCount", "label": "Reactions", "type": "NUMBER"},
    {"name": "commentsCount", "label": "Comments", "type": "NUMBER"},
    {"name": "repostsCount", "label": "Reposts", "type": "NUMBER"},
    {"name": "lastScrapedAt", "label": "Last Scraped At", "type": "DATE_TIME"},
]

# Fields for postEngagement custom object
POST_ENGAGEMENT_FIELDS = [
    {"name": "postUrn", "label": "Post URN", "type": "TEXT"},
    {"name": "userProfileUrl", "label": "User Profile URL", "type": "TEXT"},
    {"name": "engagementType", "label": "Engagement Type", "type": "TEXT"},
    {"name": "companyLinkedinUrl", "label": "Company LinkedIn URL", "type": "TEXT"},
]


# ── API helpers ───────────────────────────────────────────────────

def get_objects_with_fields() -> dict:
    """Fetch all objects. Returns {name_singular: {id, fields: set, isCustom}}."""
    resp = requests.get(f"{BASE_URL}/rest/metadata/objects", headers=headers())
    resp.raise_for_status()
    objects = resp.json()["data"]["objects"]
    result = {}
    for obj in objects:
        name = obj.get("nameSingular", "")
        field_names = {f.get("name", "") for f in obj.get("fields", [])}
        result[name] = {"id": obj["id"], "fields": field_names, "isCustom": obj.get("isCustom", False)}
    return result


def create_custom_object(obj_def: dict) -> str | None:
    """Create a custom object. Returns its ID."""
    resp = requests.post(f"{BASE_URL}/rest/metadata/objects", headers=headers(), json=obj_def)
    if resp.status_code in (200, 201):
        data = resp.json()
        obj_id = data.get("data", {}).get("createOneObject", {}).get("id")
        return obj_id
    print(f"  Warning: failed to create object {obj_def['nameSingular']}: {resp.status_code} {resp.text[:200]}")
    return None


def create_field(object_id: str, field: dict) -> bool:
    """Create a field on an object. Returns True if created."""
    payload = {
        "name": field["name"],
        "label": field["label"],
        "type": field["type"],
        "objectMetadataId": object_id,
        "description": field.get("description", ""),
    }
    resp = requests.post(f"{BASE_URL}/rest/metadata/fields", headers=headers(), json=payload)
    if resp.status_code in (200, 201):
        return True
    print(f"  Warning: failed to create field {field['name']}: {resp.status_code} {resp.text[:200]}")
    return False


def setup_fields(object_name: str, object_id: str, existing_fields: set, fields: list):
    """Create fields on an object, skip existing."""
    print(f"\n  Setting up {object_name} fields...")
    created = 0
    for field in fields:
        if field["name"] in existing_fields:
            print(f"    [skip] {field['name']}")
        else:
            if create_field(object_id, field):
                print(f"    [created] {field['name']} ({field['type']})")
                created += 1
    print(f"  Done: {created} created, {len(fields) - created} skipped")


# ── Main ──────────────────────────────────────────────────────────

def main():
    global API_KEY, BASE_URL

    parser = argparse.ArgumentParser(description="Setup Twenty CRM for LinkedIn scraper")
    parser.add_argument("--url", required=True, help="Twenty CRM base URL")
    parser.add_argument("--key", required=True, help="Twenty CRM API key")
    args = parser.parse_args()

    BASE_URL = args.url.rstrip("/")
    API_KEY = args.key

    print(f"Connecting to {BASE_URL}...")
    objects = get_objects_with_fields()
    print(f"Found {len(objects)} objects")

    # ── Step 1: Create custom objects if needed ──
    print("\n=== Custom Objects ===")
    for obj_def in CUSTOM_OBJECTS:
        name = obj_def["nameSingular"]
        if name in objects:
            print(f"  [skip] {name} already exists")
        else:
            obj_id = create_custom_object(obj_def)
            if obj_id:
                print(f"  [created] {name} (id: {obj_id})")
                objects[name] = {"id": obj_id, "fields": set(), "isCustom": True}

    # Refresh objects to get field lists for newly created objects
    objects = get_objects_with_fields()

    # ── Step 2: Setup fields on standard objects ──
    print("\n=== People Fields ===")
    if "person" in objects:
        setup_fields("People", objects["person"]["id"], objects["person"]["fields"], PEOPLE_FIELDS)

    print("\n=== Company Fields ===")
    if "company" in objects:
        setup_fields("Companies", objects["company"]["id"], objects["company"]["fields"], COMPANY_FIELDS)

    # ── Step 3: Setup fields on custom objects ──
    print("\n=== Scrape Run Fields ===")
    if "scrapeRun" in objects:
        setup_fields("ScrapeRun", objects["scrapeRun"]["id"], objects["scrapeRun"]["fields"], SCRAPE_RUN_FIELDS)

    print("\n=== Company Post Fields ===")
    if "companyPost" in objects:
        setup_fields("CompanyPost", objects["companyPost"]["id"], objects["companyPost"]["fields"], COMPANY_POST_FIELDS)

    print("\n=== Post Engagement Fields ===")
    if "postEngagement" in objects:
        setup_fields("PostEngagement", objects["postEngagement"]["id"], objects["postEngagement"]["fields"], POST_ENGAGEMENT_FIELDS)

    print("\n=== Done! All objects and fields are ready. ===")


if __name__ == "__main__":
    main()
