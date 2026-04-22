#!/usr/bin/env python3
"""
Create custom fields in Twenty CRM for the LinkedIn scraper integration.

Usage:
    python setup_fields.py --url https://your-crm.com --key YOUR_API_KEY

This script is idempotent — it checks for existing fields before creating.
"""

import argparse
import json
import sys
import requests

# Custom fields to create on the People object
PEOPLE_FIELDS = [
    {"name": "linkedinUrl", "label": "LinkedIn URL", "type": "LINKS",
     "description": "LinkedIn profile URL from scraper"},
    {"name": "intro", "label": "Intro / About", "type": "RICH_TEXT",
     "description": "LinkedIn about section"},
    {"name": "openToWork", "label": "Open to Work", "type": "BOOLEAN",
     "description": "Whether the person is open to work on LinkedIn"},
    {"name": "engagementSource", "label": "Engagement Source", "type": "TEXT",
     "description": "How this person was discovered (e.g. reacted to company post)"},
    {"name": "experiencesJson", "label": "Experiences (JSON)", "type": "RAW_JSON",
     "description": "Full work experience history from LinkedIn"},
    {"name": "educationsJson", "label": "Educations (JSON)", "type": "RAW_JSON",
     "description": "Education history from LinkedIn"},
]

# Custom fields to create on the Companies object
COMPANY_FIELDS = [
    {"name": "linkedinUrl", "label": "LinkedIn URL", "type": "LINKS",
     "description": "LinkedIn company page URL from scraper"},
    {"name": "industry", "label": "Industry", "type": "TEXT",
     "description": "Industry classification from LinkedIn"},
    {"name": "employeeCount", "label": "Employee Count", "type": "NUMBER",
     "description": "Number of employees from LinkedIn"},
    {"name": "founded", "label": "Founded", "type": "TEXT",
     "description": "Year the company was founded"},
    {"name": "aboutUs", "label": "About Us", "type": "RICH_TEXT",
     "description": "Company description from LinkedIn"},
    {"name": "specialties", "label": "Specialties", "type": "TEXT",
     "description": "Company specialties from LinkedIn"},
    {"name": "companyType", "label": "Company Type", "type": "TEXT",
     "description": "Type of company (Public, Private, etc.)"},
]


def get_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def get_object_metadata(base_url: str, api_key: str) -> dict:
    """Fetch all object metadata and return a map of name -> id."""
    url = f"{base_url.rstrip('/')}/rest/metadata/objects"
    resp = requests.get(url, headers=get_headers(api_key))
    resp.raise_for_status()
    data = resp.json()
    objects = data.get("data", data) if isinstance(data, dict) else data
    result = {}
    for obj in objects:
        name = obj.get("nameSingular", obj.get("name", ""))
        result[name.lower()] = obj["id"]
    return result


def get_existing_fields(base_url: str, api_key: str, object_id: str) -> set:
    """Get names of existing fields on an object."""
    url = f"{base_url.rstrip('/')}/rest/metadata/fields"
    resp = requests.get(url, headers=get_headers(api_key), params={"filter": f"objectMetadataId[eq]={object_id}"})
    resp.raise_for_status()
    data = resp.json()
    fields = data.get("data", data) if isinstance(data, dict) else data
    return {f.get("name", "") for f in fields}


def create_field(base_url: str, api_key: str, object_id: str, field: dict) -> bool:
    """Create a single custom field. Returns True if created, False if skipped."""
    url = f"{base_url.rstrip('/')}/rest/metadata/fields"
    payload = {
        "name": field["name"],
        "label": field["label"],
        "type": field["type"],
        "objectMetadataId": object_id,
        "description": field.get("description", ""),
    }
    resp = requests.post(url, headers=get_headers(api_key), json=payload)
    if resp.status_code in (200, 201):
        return True
    else:
        print(f"  Warning: failed to create {field['name']}: {resp.status_code} {resp.text}")
        return False


def setup_object_fields(base_url: str, api_key: str, object_name: str, object_id: str, fields: list):
    """Create custom fields on an object, skipping those that already exist."""
    print(f"\nSetting up {object_name} fields...")
    existing = get_existing_fields(base_url, api_key, object_id)

    for field in fields:
        if field["name"] in existing:
            print(f"  [skip] {field['name']} already exists")
        else:
            if create_field(base_url, api_key, object_id, field):
                print(f"  [created] {field['name']} ({field['type']})")


def main():
    parser = argparse.ArgumentParser(description="Setup Twenty CRM custom fields for LinkedIn scraper")
    parser.add_argument("--url", required=True, help="Twenty CRM base URL (e.g. https://crm.example.com)")
    parser.add_argument("--key", required=True, help="Twenty CRM API key")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    print(f"Connecting to Twenty CRM at {base_url}...")

    # Get object metadata
    try:
        objects = get_object_metadata(base_url, args.key)
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    print(f"Found {len(objects)} objects: {', '.join(objects.keys())}")

    # Setup People fields
    people_id = objects.get("person")
    if people_id:
        setup_object_fields(base_url, args.key, "People", people_id, PEOPLE_FIELDS)
    else:
        print("Warning: 'person' object not found in metadata")

    # Setup Company fields
    company_id = objects.get("company")
    if company_id:
        setup_object_fields(base_url, args.key, "Companies", company_id, COMPANY_FIELDS)
    else:
        print("Warning: 'company' object not found in metadata")

    print("\nDone! Custom fields are ready for the LinkedIn scraper integration.")


if __name__ == "__main__":
    main()
