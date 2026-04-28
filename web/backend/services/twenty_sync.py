"""Twenty CRM sync client — maps scraped LinkedIn data to CRM records."""

import asyncio
import json
import logging
from typing import Any, Optional

import httpx

from linkedin_scraper.models.person import Person
from linkedin_scraper.models.company import Company
from linkedin_scraper.models.post import ExtractUsersResult, PostEngagementUser

logger = logging.getLogger(__name__)


class TwentyCRMClient:
    """Async client for syncing LinkedIn scraper data to Twenty CRM."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Health check ──────────────────────────────────────────────

    async def check_connection(self) -> bool:
        """Test if the CRM is reachable and the API key is valid."""
        try:
            client = await self._get_client()
            resp = await client.get("/rest/metadata/objects")
            return resp.status_code == 200
        except Exception as e:
            logger.warning("CRM connection check failed: %s", e)
            return False

    # ── Search ────────────────────────────────────────────────────

    async def _search_people_by_linkedin_url(self, linkedin_url: str) -> Optional[dict]:
        """Search for a person by LinkedIn URL. Returns the record or None."""
        client = await self._get_client()
        # Twenty REST filter syntax
        resp = await client.get(
            "/rest/people",
            params={"filter": f"linkedinUrl[like]=%{linkedin_url}%", "limit": 1},
        )
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("data", {}).get("people", [])
            if records:
                return records[0]
        return None

    async def _search_companies_by_linkedin_url(self, linkedin_url: str) -> Optional[dict]:
        """Search for a company by LinkedIn URL."""
        client = await self._get_client()
        resp = await client.get(
            "/rest/companies",
            params={"filter": f"linkedinUrl[like]=%{linkedin_url}%", "limit": 1},
        )
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("data", {}).get("companies", [])
            if records:
                return records[0]
        return None

    async def _search_companies_by_name(self, name: str) -> Optional[dict]:
        """Search for a company by name."""
        client = await self._get_client()
        resp = await client.get(
            "/rest/companies",
            params={"filter": f"name[eq]={name}", "limit": 1},
        )
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("data", {}).get("companies", [])
            if records:
                return records[0]
        return None

    # ── Create / Update ───────────────────────────────────────────

    async def _create_person(self, data: dict) -> Optional[str]:
        """Create a person record. Returns the ID or None."""
        client = await self._get_client()
        resp = await client.post("/rest/people", json=data)
        if resp.status_code in (200, 201):
            result = resp.json()
            record = result.get("data", {}).get("createPerson", result.get("data", {}))
            return record.get("id")
        logger.warning("Failed to create person: %s %s", resp.status_code, resp.text[:200])
        return None

    async def _update_person(self, person_id: str, data: dict) -> bool:
        """Update an existing person record."""
        client = await self._get_client()
        resp = await client.patch(f"/rest/people/{person_id}", json=data)
        if resp.status_code == 200:
            return True
        logger.warning("Failed to update person %s: %s %s", person_id, resp.status_code, resp.text[:200])
        return False

    async def _create_company(self, data: dict) -> Optional[str]:
        """Create a company record. Returns the ID or None."""
        client = await self._get_client()
        resp = await client.post("/rest/companies", json=data)
        if resp.status_code in (200, 201):
            result = resp.json()
            record = result.get("data", {}).get("createCompany", result.get("data", {}))
            return record.get("id")
        logger.warning("Failed to create company: %s %s", resp.status_code, resp.text[:200])
        return None

    async def _update_company(self, company_id: str, data: dict) -> bool:
        """Update an existing company record."""
        client = await self._get_client()
        resp = await client.patch(f"/rest/companies/{company_id}", json=data)
        if resp.status_code == 200:
            return True
        logger.warning("Failed to update company %s: %s", company_id, resp.text[:200])
        return False

    async def _create_note(self, body: str, person_id: Optional[str] = None) -> Optional[str]:
        """Create a note, optionally linked to a person."""
        client = await self._get_client()
        payload: dict[str, Any] = {"body": body}
        resp = await client.post("/rest/notes", json=payload)
        if resp.status_code in (200, 201):
            result = resp.json()
            note_id = result.get("data", {}).get("id")
            # Link note to person via noteTargets
            if person_id and note_id:
                await client.post("/rest/noteTargets", json={
                    "noteId": note_id,
                    "personId": person_id,
                })
            return note_id
        return None

    # ── Mapping helpers ───────────────────────────────────────────

    @staticmethod
    def _split_name(full_name: str) -> dict:
        """Split a full name into firstName and lastName."""
        parts = full_name.strip().split(None, 1)
        return {
            "firstName": parts[0] if parts else "",
            "lastName": parts[1] if len(parts) > 1 else "",
        }

    @staticmethod
    def _map_person(person: Person) -> dict:
        """Map LinkedIn Person model to Twenty People fields."""
        data: dict[str, Any] = {}

        if person.name:
            data["name"] = TwentyCRMClient._split_name(person.name)

        # Job title from first experience
        if person.experiences:
            data["jobTitle"] = person.experiences[0].position_title or ""

        # Location
        if person.location:
            data["city"] = person.location

        # Email from contacts
        for c in person.contacts:
            if c.type == "email":
                data["emails"] = {"primaryEmail": c.value}
                break

        # Phone from contacts
        for c in person.contacts:
            if c.type == "phone":
                data["phones"] = {"primaryPhoneNumber": c.value}
                break

        # Custom fields
        if person.linkedin_url:
            data["linkedinUrl"] = {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": person.linkedin_url}
        if person.about:
            data["intro"] = person.about
        data["openToWork"] = person.open_to_work

        if person.experiences:
            data["experiencesJson"] = [e.model_dump() for e in person.experiences]
        if person.educations:
            data["educationsJson"] = [e.model_dump() for e in person.educations]

        return data

    @staticmethod
    def _map_company(company: Company) -> dict:
        """Map LinkedIn Company model to Twenty Companies fields."""
        data: dict[str, Any] = {}

        if company.name:
            data["name"] = company.name
        if company.website:
            data["domainName"] = {"primaryLinkLabel": "Website", "primaryLinkUrl": company.website}
        if company.linkedin_url:
            data["linkedinUrl"] = {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": company.linkedin_url}
        if company.industry:
            data["industry"] = company.industry
        if company.headquarters:
            data["address"] = {"addressCity": company.headquarters}
        if company.founded:
            data["founded"] = company.founded
        if company.about_us:
            data["aboutUs"] = company.about_us
        if company.specialties:
            data["specialties"] = company.specialties
        if company.company_type:
            data["companyType"] = company.company_type
        if company.headcount:
            data["employeeCount"] = company.headcount
        elif company.company_size:
            # Try to extract a number from "1,001-5,000 employees"
            import re
            nums = re.findall(r"[\d,]+", company.company_size.replace(",", ""))
            if nums:
                data["employeeCount"] = int(nums[0])

        return data

    @staticmethod
    def _map_engagement_user(user: PostEngagementUser) -> dict:
        """Map PostEngagementUser to Twenty People fields."""
        data: dict[str, Any] = {}

        data["name"] = TwentyCRMClient._split_name(user.name)

        if user.headline:
            data["jobTitle"] = user.headline
        if user.profile_url:
            data["linkedinUrl"] = {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": user.profile_url}

        data["engagementSource"] = f"LinkedIn post {user.engagement_type}"

        return data

    # ── High-level sync methods ───────────────────────────────────

    async def sync_person(self, person: Person) -> dict:
        """Sync a LinkedIn Person to Twenty CRM. Returns {id, action}."""
        data = self._map_person(person)

        # Dedup by LinkedIn URL
        existing = None
        if person.linkedin_url:
            existing = await self._search_people_by_linkedin_url(person.linkedin_url)

        if existing:
            person_id = existing["id"]
            await self._update_person(person_id, data)
            logger.info("Updated person %s (%s)", person.name, person_id)
            return {"id": person_id, "action": "updated"}
        else:
            person_id = await self._create_person(data)
            logger.info("Created person %s (%s)", person.name, person_id)
            return {"id": person_id, "action": "created"}

    async def sync_company(self, company: Company) -> dict:
        """Sync a LinkedIn Company to Twenty CRM. Returns {id, action}."""
        data = self._map_company(company)

        # Dedup by LinkedIn URL or name
        existing = None
        if company.linkedin_url:
            existing = await self._search_companies_by_linkedin_url(company.linkedin_url)
        if not existing and company.name:
            existing = await self._search_companies_by_name(company.name)

        if existing:
            company_id = existing["id"]
            await self._update_company(company_id, data)
            logger.info("Updated company %s (%s)", company.name, company_id)
            return {"id": company_id, "action": "updated"}
        else:
            company_id = await self._create_company(data)
            logger.info("Created company %s (%s)", company.name, company_id)
            return {"id": company_id, "action": "created"}

    async def sync_engagement_users(self, result: ExtractUsersResult) -> dict:
        """Sync PostEngagementUsers to Twenty CRM. Returns summary."""
        created = 0
        updated = 0
        failed = 0

        for user in result.users:
            try:
                data = self._map_engagement_user(user)

                # Dedup
                existing = None
                if user.profile_url:
                    existing = await self._search_people_by_linkedin_url(user.profile_url)

                if existing:
                    person_id = existing["id"]
                    await self._update_person(person_id, data)
                    updated += 1
                else:
                    person_id = await self._create_person(data)
                    created += 1

                # Add engagement note
                if person_id:
                    note = f"{user.engagement_type.capitalize()}d on a post from {result.company_url}"
                    await self._create_note(note, person_id)

                # Rate limit: ~100 req/min, we use ~3 per user
                await asyncio.sleep(0.6)

            except Exception as e:
                logger.warning("Failed to sync user %s: %s", user.name, e)
                failed += 1

        summary = {
            "total": len(result.users),
            "created": created,
            "updated": updated,
            "failed": failed,
        }
        logger.info("Engagement sync complete: %s", summary)
        return summary

    async def sync_result(self, scrape_type: str, result_data: str) -> dict:
        """Sync a stored scrape result (JSON string) based on its type."""
        parsed = json.loads(result_data)

        if scrape_type == "person":
            person = Person.model_validate(parsed)
            return await self.sync_person(person)

        elif scrape_type == "company":
            company = Company.model_validate(parsed)
            return await self.sync_company(company)

        elif scrape_type == "extract_users":
            result = ExtractUsersResult.model_validate(parsed)
            return await self.sync_engagement_users(result)

        else:
            return {"error": f"Sync not supported for type: {scrape_type}"}
