"""CRUD wrapper for Twenty CRM REST API — all custom and standard objects."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Rate limit: 100 req/min → ~0.6s between calls
_API_DELAY = 0.6


class TwentyCRUD:
    """Async CRUD client for Twenty CRM objects."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, headers=self._headers, timeout=30.0
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _throttle(self):
        await asyncio.sleep(_API_DELAY)

    # ── Generic CRUD ──────────────────────────────────────────────

    async def _list(self, endpoint: str, key: str, params: dict | None = None) -> list[dict]:
        """GET /rest/{endpoint} and return data.{key} list."""
        client = await self._get_client()
        resp = await client.get(f"/rest/{endpoint}", params=params or {})
        if resp.status_code == 200:
            return resp.json().get("data", {}).get(key, [])
        logger.warning("List %s failed: %s %s", endpoint, resp.status_code, resp.text[:200])
        return []

    async def _get(self, endpoint: str, record_id: str) -> dict | None:
        """GET /rest/{endpoint}/{id}."""
        client = await self._get_client()
        resp = await client.get(f"/rest/{endpoint}/{record_id}")
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            # Twenty wraps single record in a key like "scrapeRun" or "company"
            if isinstance(data, dict):
                # Return the first value that's a dict (the record)
                for v in data.values():
                    if isinstance(v, dict) and "id" in v:
                        return v
            return data
        return None

    async def _create(self, endpoint: str, data: dict) -> str | None:
        """POST /rest/{endpoint}. Returns created record ID."""
        client = await self._get_client()
        resp = await client.post(f"/rest/{endpoint}", json=data)
        await self._throttle()
        if resp.status_code in (200, 201):
            result = resp.json().get("data", {})
            # Find the ID in nested response
            for v in result.values():
                if isinstance(v, dict) and "id" in v:
                    return v["id"]
            return result.get("id")
        logger.warning("Create %s failed: %s %s", endpoint, resp.status_code, resp.text[:300])
        return None

    async def _update(self, endpoint: str, record_id: str, data: dict) -> bool:
        """PATCH /rest/{endpoint}/{id}."""
        client = await self._get_client()
        resp = await client.patch(f"/rest/{endpoint}/{record_id}", json=data)
        await self._throttle()
        return resp.status_code == 200

    async def _delete(self, endpoint: str, record_id: str) -> bool:
        """DELETE /rest/{endpoint}/{id}."""
        client = await self._get_client()
        resp = await client.delete(f"/rest/{endpoint}/{record_id}")
        return resp.status_code in (200, 204)

    async def _find_one(self, endpoint: str, key: str, filter_str: str) -> dict | None:
        """Search for a single record by filter."""
        records = await self._list(endpoint, key, {"filter": filter_str, "limit": "1"})
        return records[0] if records else None

    # ── Companies (standard object) ───────────────────────────────

    async def list_companies(self, search: str | None = None, limit: int = 50) -> list[dict]:
        params: dict[str, Any] = {"limit": str(limit)}
        if search:
            params["filter"] = f"name[like]:%{search}%,deletedAt[is]:NULL"
        else:
            params["filter"] = "deletedAt[is]:NULL"
        return await self._list("companies", "companies", params)

    async def delete_company(self, crm_id: str) -> bool:
        return await self._delete("companies", crm_id)

    async def find_company_by_name(self, name: str) -> dict | None:
        return await self._find_one("companies", "companies", f"name[eq]:{name}")

    async def find_or_create_company(self, name: str, linkedin_url: str | None = None) -> str | None:
        """Find a company by LinkedIn URL or name. Create if not found. Returns CRM ID."""
        existing = None
        if linkedin_url:
            existing = await self.find_company_by_linkedin_url(linkedin_url)
        if not existing and name:
            existing = await self.find_company_by_name(name)
        if existing:
            return existing["id"]

        # Create new company
        company_data: dict[str, Any] = {"name": name}
        if linkedin_url:
            company_data["linkedinUrl"] = {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": linkedin_url}
        return await self.create_company(company_data)

    async def get_company(self, crm_id: str) -> dict | None:
        return await self._get("companies", crm_id)

    async def find_company_by_linkedin_url(self, url: str) -> dict | None:
        return await self._find_one("companies", "companies", f"linkedinUrl.primaryLinkUrl[like]:%{url}%")

    async def create_company(self, data: dict) -> str | None:
        return await self._create("companies", data)

    async def update_company(self, crm_id: str, data: dict) -> bool:
        return await self._update("companies", crm_id, data)

    # ── People (standard object) ──────────────────────────────────

    async def list_people(self, params: dict | None = None) -> list[dict]:
        return await self._list("people", "people", params)

    async def find_person_by_linkedin_url(self, url: str) -> dict | None:
        return await self._find_one("people", "people", f"linkedinUrl.primaryLinkUrl[like]:%{url}%")

    async def create_person(self, data: dict) -> str | None:
        return await self._create("people", data)

    async def update_person(self, crm_id: str, data: dict) -> bool:
        return await self._update("people", crm_id, data)

    async def link_person_to_company(self, person_crm_id: str, company_crm_id: str) -> bool:
        """Set the company relation on a person record."""
        return await self._update("people", person_crm_id, {
            "companyId": company_crm_id,
        })

    async def list_users_for_company(self, company_url: str) -> list[dict]:
        return await self._list("people", "people", {
            "filter": f"discoveredFromCompany[eq]:{company_url}",
            "limit": "200",
        })

    # ── Scrape Runs (custom object) ───────────────────────────────

    async def create_scrape_run(self, data: dict) -> str | None:
        return await self._create("scrapeRuns", data)

    async def update_scrape_run(self, crm_id: str, data: dict) -> bool:
        return await self._update("scrapeRuns", crm_id, data)

    async def get_scrape_run(self, crm_id: str) -> dict | None:
        return await self._get("scrapeRuns", crm_id)

    async def list_runs_for_company(self, company_url: str) -> list[dict]:
        return await self._list("scrapeRuns", "scrapeRuns", {
            "filter": f"companyLinkedinUrl[eq]:{company_url}",
            "limit": "50",
            "orderBy": "createdAt[AscNullsLast]",
        })

    # ── Company Posts (custom object) ─────────────────────────────

    async def find_post_by_urn(self, urn: str) -> dict | None:
        return await self._find_one("companyPosts", "companyPosts", f"urn[eq]:{urn}")

    async def create_post(self, data: dict) -> str | None:
        return await self._create("companyPosts", data)

    async def update_post(self, crm_id: str, data: dict) -> bool:
        return await self._update("companyPosts", crm_id, data)

    async def list_posts_for_company(self, company_url: str) -> list[dict]:
        return await self._list("companyPosts", "companyPosts", {
            "filter": f"companyLinkedinUrl[eq]:{company_url}",
            "limit": "500",
        })

    # ── Post Engagements (custom object) ──────────────────────────

    async def find_engagement(self, post_urn: str, user_url: str, eng_type: str) -> dict | None:
        """Check if a (post, user, type) engagement already exists."""
        records = await self._list("postEngagements", "postEngagements", {
            "filter": f"postUrn[eq]:{post_urn},userProfileUrl[eq]:{user_url},engagementType[eq]:{eng_type}",
            "limit": "1",
        })
        return records[0] if records else None

    async def create_engagement(self, data: dict) -> str | None:
        return await self._create("postEngagements", data)

    async def list_engagements_for_company(self, company_url: str) -> list[dict]:
        return await self._list("postEngagements", "postEngagements", {
            "filter": f"companyLinkedinUrl[eq]:{company_url}",
            "limit": "500",
        })

    # ── Connection check ──────────────────────────────────────────

    async def check_connection(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("/rest/metadata/objects")
            return resp.status_code == 200
        except Exception:
            return False

    # ── Person data mapping ───────────────────────────────────────

    @staticmethod
    def map_person_from_scraper(person) -> dict:
        """Map linkedin_scraper Person model to Twenty People fields.

        Returns dict with 'crm_data' (fields for Twenty) and 'company_info'
        (current employer details for company linking).
        """
        data: dict[str, Any] = {}

        if person.name:
            parts = person.name.strip().split(None, 1)
            data["name"] = {
                "firstName": parts[0] if parts else "",
                "lastName": parts[1] if len(parts) > 1 else "",
            }

        # Job title + company from current experience
        if person.experiences:
            exp = person.experiences[0]
            data["jobTitle"] = exp.position_title or ""

        # City
        if person.location:
            data["city"] = person.location

        # Email
        for c in person.contacts:
            if c.type == "email":
                data["emails"] = {"primaryEmail": c.value}
                break

        # Phone
        for c in person.contacts:
            if c.type == "phone":
                data["phones"] = {"primaryPhoneNumber": c.value}
                break

        # LinkedIn URL
        if person.linkedin_url:
            data["linkedinUrl"] = {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": person.linkedin_url}

        # About
        if person.about:
            data["intro"] = person.about
        data["openToWork"] = person.open_to_work

        # Full experience/education JSON
        if person.experiences:
            data["experiencesJson"] = [e.model_dump() for e in person.experiences]
        if person.educations:
            data["educationsJson"] = [e.model_dump() for e in person.educations]

        data["profileScrapedAt"] = datetime.now(timezone.utc).isoformat()

        return data

    @staticmethod
    def extract_current_company(person) -> dict | None:
        """Extract current employer info from Person for company creation/linking.

        Returns {name, linkedin_url} or None if no experience found.
        """
        if not person.experiences:
            return None
        exp = person.experiences[0]
        if not exp.institution_name:
            return None
        return {
            "name": exp.institution_name,
            "linkedin_url": exp.linkedin_url,  # may be None
        }

    @staticmethod
    def map_company_from_scraper(company) -> dict:
        """Map linkedin_scraper Company model to Twenty Companies fields."""
        import re
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
            nums = re.findall(r"[\d,]+", company.company_size.replace(",", ""))
            if nums:
                data["employeeCount"] = int(nums[0])

        return data
