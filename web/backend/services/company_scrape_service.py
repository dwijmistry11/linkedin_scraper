"""Company scraping pipeline — 5 phases with pause/resume, verbose progress."""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from linkedin_scraper import CompanyScraper, CompanyPostsScraper, PersonScraper
from linkedin_scraper.scrapers.post_reactions import PostReactionsScraper
from linkedin_scraper.core.session_rotator import SessionRotator
from linkedin_scraper.core.human import human_between_pages, human_between_profiles, human_delay, random_mouse_move

from ..browser_pool import BrowserPool
from .twenty_crud import TwentyCRUD

logger = logging.getLogger(__name__)

SEVEN_DAYS = timedelta(days=7)
BATCH_BREAK_EVERY = 3

# Phase labels for UI
PHASES = [
    ("company_info", "Scrape Company Info"),
    ("scraping_posts", "Discover Posts"),
    ("extracting_users", "Extract Engaged Users"),
    ("scraping_profiles", "Scrape Full Profiles"),
    ("done", "Complete"),
]


async def run_company_scrape(
    pool: BrowserPool,
    crud: TwentyCRUD,
    run_crm_id: str,
    company_crm_id: str,
    company_url: str,
    session_entries: list[dict],
    ws_callback=None,
) -> None:
    """Main pipeline — runs as a background task."""
    try:
        # Build session rotator
        await _progress(crud, run_crm_id, ws_callback, 0, "Starting browser sessions...", "company_info")
        rotator = SessionRotator()
        first_page = None
        for entry in session_entries:
            browser = await pool.get_browser(entry["id"], entry["file"])
            rotator.add(entry["id"], browser.page)
            if first_page is None:
                first_page = browser.page

        if not first_page:
            await _fail_run(crud, run_crm_id, ws_callback, "No browser sessions available")
            return

        await _progress(crud, run_crm_id, ws_callback, 1,
                        f"Ready — {rotator.session_count} session(s) loaded", "company_info")

        # Load resume state
        run = await crud.get_scrape_run(run_crm_id)
        resume = {}
        if run and run.get("resumeStateJson"):
            try:
                resume = json.loads(run["resumeStateJson"])
            except Exception:
                pass

        start_phase = resume.get("phase", "company_info")
        await crud.update_scrape_run(run_crm_id, {"status": "running"})

        # ── Phase 1: Company Info ─────────────────────────────────
        if start_phase == "company_info":
            await _progress(crud, run_crm_id, ws_callback, 2,
                            "Phase 1/4: Checking company information...", "company_info")

            company = await crud.get_company(company_crm_id)
            needs_scrape = not company or not company.get("name") or company.get("name") == ""

            if needs_scrape:
                await _progress(crud, run_crm_id, ws_callback, 3,
                                "Navigating to company page...", "company_info")

                page = rotator.get_page()
                scraper = CompanyScraper(page)
                try:
                    company_data = await scraper.scrape(company_url)
                    await _progress(crud, run_crm_id, ws_callback, 4,
                                    f"Scraped: {company_data.name or 'company'}. Saving to CRM...", "company_info")

                    mapped = TwentyCRUD.map_company_from_scraper(company_data)
                    mapped["lastPostScrapedAt"] = datetime.now(timezone.utc).isoformat()
                    await crud.update_company(company_crm_id, mapped)

                    await _progress(crud, run_crm_id, ws_callback, 5,
                                    f"Company info saved to CRM: {company_data.name}", "company_info")
                except Exception as e:
                    await _progress(crud, run_crm_id, ws_callback, 5,
                                    f"Company scrape failed ({e}), continuing...", "company_info")
            else:
                await _progress(crud, run_crm_id, ws_callback, 5,
                                f"Company already in CRM: {company.get('name', 'Unknown')}", "company_info")

            start_phase = "scraping_posts"

        # ── Phase 2: Scrape Posts ─────────────────────────────────
        posts_to_process = resume.get("posts_to_process_urns", None)

        if start_phase == "scraping_posts":
            await _progress(crud, run_crm_id, ws_callback, 8,
                            "Phase 2/4: Navigating to posts page...", "scraping_posts")

            page = rotator.get_page()
            posts_scraper = CompanyPostsScraper(page)

            await _progress(crud, run_crm_id, ws_callback, 10,
                            "Scrolling through posts (this may take a while)...", "scraping_posts")
            try:
                posts = await posts_scraper.scrape(company_url, limit=9999)
            except Exception as e:
                await _progress(crud, run_crm_id, ws_callback, 10,
                                f"Posts scraping failed: {e}", "scraping_posts")
                posts = []

            total_posts = len(posts)
            await _progress(crud, run_crm_id, ws_callback, 12,
                            f"Found {total_posts} posts. Checking which need processing...", "scraping_posts")
            await crud.update_scrape_run(run_crm_id, {"totalPostsFound": total_posts})

            now = datetime.now(timezone.utc)
            eligible_urns = []

            for idx, post in enumerate(posts):
                if not post.urn:
                    continue

                existing = await crud.find_post_by_urn(post.urn)
                post_data = {
                    "name": (post.text or "")[:100],
                    "companyLinkedinUrl": company_url,
                    "urn": post.urn,
                    "linkedinUrl": post.linkedin_url or "",
                    "postText": (post.text or "")[:2000],
                    "postedDate": post.posted_date or "",
                    "reactionsCount": post.reactions_count,
                    "commentsCount": post.comments_count,
                    "repostsCount": post.reposts_count,
                }

                if existing:
                    await crud.update_post(existing["id"], post_data)
                    last_scraped = existing.get("lastScrapedAt")
                    if last_scraped:
                        try:
                            last_dt = datetime.fromisoformat(last_scraped.replace("Z", "+00:00"))
                            if now - last_dt < SEVEN_DAYS:
                                continue
                        except Exception:
                            pass
                    eligible_urns.append(post.urn)
                else:
                    await crud.create_post(post_data)
                    eligible_urns.append(post.urn)

            posts_to_process = eligible_urns
            await _progress(crud, run_crm_id, ws_callback, 15,
                            f"Saved {total_posts} posts. {len(eligible_urns)} need user extraction (7-day rule).",
                            "scraping_posts")
            start_phase = "extracting_users"

        # ── Phase 3: Extract Users ────────────────────────────────
        current_post_idx = resume.get("current_post_index", 0)

        if start_phase == "extracting_users" and posts_to_process:
            total_eligible = len(posts_to_process)
            total_new_users = 0

            await _progress(crud, run_crm_id, ws_callback, 16,
                            f"Phase 3/4: Extracting users from {total_eligible} posts...", "extracting_users")

            for i in range(current_post_idx, total_eligible):
                if await _is_paused(crud, run_crm_id):
                    await _save_checkpoint(crud, run_crm_id, ws_callback, "extracting_users", {
                        "posts_to_process_urns": posts_to_process,
                        "current_post_index": i,
                    })
                    return

                urn = posts_to_process[i]
                pct = 16 + int((i / max(total_eligible, 1)) * 49)  # 16% to 65%

                await _progress(crud, run_crm_id, ws_callback, pct,
                                f"Opening post {i + 1}/{total_eligible} reactions...", "extracting_users")

                # Find post URL
                post_record = await crud.find_post_by_urn(urn)
                post_url = (post_record.get("linkedinUrl") if post_record else None) or f"https://www.linkedin.com/feed/update/{urn}/"

                # Extract reactions
                page = rotator.get_page()
                reactions_scraper = PostReactionsScraper(page)
                try:
                    users = await reactions_scraper.scrape(post_url, max_users=200)
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Post {i + 1}/{total_eligible}: found {len(users)} engaged users", "extracting_users")
                except Exception as e:
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Post {i + 1}/{total_eligible}: extraction failed ({e})", "extracting_users")
                    users = []

                # Upsert users
                for user in users:
                    if not user.profile_url:
                        continue

                    existing_person = await crud.find_person_by_linkedin_url(user.profile_url)
                    if existing_person:
                        person_crm_id = existing_person["id"]
                    else:
                        parts = user.name.strip().split(None, 1) if user.name else ["", ""]
                        person_data = {
                            "name": {"firstName": parts[0] if parts else "", "lastName": parts[1] if len(parts) > 1 else ""},
                            "linkedinUrl": {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": user.profile_url},
                            "discoveredFromCompany": company_url,
                        }
                        if user.headline:
                            person_data["jobTitle"] = user.headline
                        person_crm_id = await crud.create_person(person_data)
                        total_new_users += 1

                    if person_crm_id:
                        existing_eng = await crud.find_engagement(urn, user.profile_url, user.engagement_type)
                        if not existing_eng:
                            await crud.create_engagement({
                                "name": f"{user.name} - {user.engagement_type} - {urn[-12:]}",
                                "postUrn": urn,
                                "userProfileUrl": user.profile_url,
                                "engagementType": user.engagement_type,
                                "companyLinkedinUrl": company_url,
                            })

                if post_record:
                    await crud.update_post(post_record["id"], {"lastScrapedAt": datetime.now(timezone.utc).isoformat()})

                await crud.update_scrape_run(run_crm_id, {
                    "postsProcessed": i + 1,
                    "totalUsersFound": total_new_users,
                    "newUsersFound": total_new_users,
                    "progressPercent": pct,
                })

                # Human delay with progress message
                delay = random.uniform(5.0, 12.0)
                await _progress(crud, run_crm_id, ws_callback, pct,
                                f"Post {i + 1}/{total_eligible} done ({total_new_users} new users). Waiting {int(delay)}s...",
                                "extracting_users")
                await asyncio.sleep(delay)
                await random_mouse_move(page)

                # Batch break
                if (i + 1) % BATCH_BREAK_EVERY == 0 and i + 1 < total_eligible:
                    pause = random.randint(15, 30)
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Taking a {pause}s break after {i + 1} posts (human-like behavior)...",
                                    "extracting_users")
                    await asyncio.sleep(pause)

            await _progress(crud, run_crm_id, ws_callback, 65,
                            f"User extraction complete: {total_new_users} new users from {len(posts_to_process)} posts",
                            "extracting_users")
            start_phase = "scraping_profiles"

        elif start_phase == "extracting_users" and not posts_to_process:
            await _progress(crud, run_crm_id, ws_callback, 65,
                            "No posts need user extraction (all scraped within 7 days)", "extracting_users")
            start_phase = "scraping_profiles"

        # ── Phase 4: Scrape Profiles ──────────────────────────────
        if start_phase == "scraping_profiles":
            await _progress(crud, run_crm_id, ws_callback, 66,
                            "Phase 4/4: Checking which profiles need scraping...", "scraping_profiles")

            all_users = await crud.list_users_for_company(company_url)
            now = datetime.now(timezone.utc)

            users_to_scrape = []
            for u in all_users:
                profile_url = None
                lu = u.get("linkedinUrl")
                if isinstance(lu, dict):
                    profile_url = lu.get("primaryLinkUrl")
                elif isinstance(lu, str):
                    profile_url = lu

                if not profile_url or "/in/" not in profile_url:
                    continue

                psa = u.get("profileScrapedAt")
                if psa:
                    try:
                        last_dt = datetime.fromisoformat(psa.replace("Z", "+00:00"))
                        if now - last_dt < SEVEN_DAYS:
                            continue
                    except Exception:
                        pass
                users_to_scrape.append({"crm_id": u["id"], "profile_url": profile_url, "name": u.get("name", {})})

            total_profiles = len(users_to_scrape)
            skipped = len(all_users) - total_profiles
            await crud.update_scrape_run(run_crm_id, {"profilesToScrape": total_profiles})
            await _progress(crud, run_crm_id, ws_callback, 67,
                            f"{total_profiles} profiles to scrape ({skipped} skipped — scraped within 7 days)",
                            "scraping_profiles")

            start_idx = resume.get("current_profile_index", 0)

            for j in range(start_idx, total_profiles):
                if await _is_paused(crud, run_crm_id):
                    await _save_checkpoint(crud, run_crm_id, ws_callback, "scraping_profiles", {
                        "current_profile_index": j,
                    })
                    return

                user_info = users_to_scrape[j]
                pct = 67 + int((j / max(total_profiles, 1)) * 30)  # 67% to 97%

                name_display = ""
                if isinstance(user_info["name"], dict):
                    name_display = f"{user_info['name'].get('firstName', '')} {user_info['name'].get('lastName', '')}".strip()

                await _progress(crud, run_crm_id, ws_callback, pct,
                                f"Scraping profile {j + 1}/{total_profiles}: {name_display}...", "scraping_profiles")

                page = rotator.get_page()
                person_scraper = PersonScraper(page)
                try:
                    person = await person_scraper.scrape(user_info["profile_url"])
                    mapped = TwentyCRUD.map_person_from_scraper(person)
                    mapped["discoveredFromCompany"] = company_url
                    await crud.update_person(user_info["crm_id"], mapped)

                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Profile {j + 1}/{total_profiles}: {person.name or name_display} saved to CRM",
                                    "scraping_profiles")
                except Exception as e:
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Profile {j + 1}/{total_profiles}: failed ({e})", "scraping_profiles")

                await crud.update_scrape_run(run_crm_id, {
                    "profilesScraped": j + 1,
                    "progressPercent": pct,
                })

                # Human delay with message
                delay = random.uniform(8.0, 18.0)
                await _progress(crud, run_crm_id, ws_callback, pct,
                                f"Profile {j + 1}/{total_profiles} done. Waiting {int(delay)}s before next...",
                                "scraping_profiles")
                await asyncio.sleep(delay)

                if (j + 1) % BATCH_BREAK_EVERY == 0 and j + 1 < total_profiles:
                    pause = random.randint(20, 45)
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Taking a {pause}s break after {j + 1} profiles (human-like behavior)...",
                                    "scraping_profiles")
                    await asyncio.sleep(pause)

            await _progress(crud, run_crm_id, ws_callback, 97,
                            f"All {total_profiles} profiles scraped and saved to CRM", "scraping_profiles")

        # ── Done ──────────────────────────────────────────────────
        await crud.update_scrape_run(run_crm_id, {
            "status": "completed",
            "phase": "done",
            "progressPercent": 100,
            "progressMessage": "All done!",
            "resumeStateJson": "",
        })
        await _progress(crud, run_crm_id, ws_callback, 100, "Scraping complete!", "done")
        logger.info("Company scrape completed: %s", company_url)

    except Exception as e:
        logger.exception("Company scrape failed: %s", company_url)
        await _fail_run(crud, run_crm_id, ws_callback, str(e))


# ── Helpers ───────────────────────────────────────────────────────

async def _progress(crud: TwentyCRUD, run_id: str, ws_callback, pct: int, msg: str, phase: str):
    """Update progress in CRM and send WebSocket notification."""
    await crud.update_scrape_run(run_id, {
        "progressPercent": pct,
        "progressMessage": msg,
        "phase": phase,
    })
    if ws_callback:
        try:
            await ws_callback.on_progress(msg, pct)
        except Exception:
            pass


async def _is_paused(crud: TwentyCRUD, run_crm_id: str) -> bool:
    run = await crud.get_scrape_run(run_crm_id)
    return run.get("status") == "paused" if run else False


async def _save_checkpoint(crud: TwentyCRUD, run_crm_id: str, ws_callback, phase: str, state: dict):
    state["phase"] = phase
    await crud.update_scrape_run(run_crm_id, {
        "status": "paused",
        "resumeStateJson": json.dumps(state),
        "progressMessage": f"Paused at {phase}",
    })
    if ws_callback:
        try:
            await ws_callback.on_progress(f"Paused at {phase}", -1)
        except Exception:
            pass
    logger.info("Checkpoint saved for run %s at phase %s", run_crm_id, phase)


async def _fail_run(crud: TwentyCRUD, run_crm_id: str, ws_callback, error: str):
    await crud.update_scrape_run(run_crm_id, {
        "status": "failed",
        "errorMessage": error[:500],
        "progressMessage": f"Failed: {error[:200]}",
    })
    if ws_callback:
        try:
            await ws_callback.on_error(Exception(error))
        except Exception:
            pass
