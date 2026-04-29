"""Company scraping pipeline — 5 phases with pause/resume and incremental tracking."""

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
BATCH_BREAK_EVERY = 3  # Take a longer pause every N items


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
        rotator = SessionRotator()
        first_page = None
        for entry in session_entries:
            browser = await pool.get_browser(entry["id"], entry["file"])
            rotator.add(entry["id"], browser.page)
            if first_page is None:
                first_page = browser.page

        if not first_page:
            await _fail_run(crud, run_crm_id, "No browser sessions available")
            return

        # Load resume state if any
        run = await crud.get_scrape_run(run_crm_id)
        resume = {}
        if run and run.get("resumeStateJson"):
            try:
                resume = json.loads(run["resumeStateJson"])
            except Exception:
                pass

        start_phase = resume.get("phase", "company_info")

        await crud.update_scrape_run(run_crm_id, {
            "status": "running",
        })
        await _notify(ws_callback, "start", {"phase": start_phase})

        # ── Phase 1: Company Info ─────────────────────────────────
        if start_phase in ("company_info",):
            await _notify(ws_callback, "progress", {"percent": 2, "message": "Scraping company info...", "phase": "company_info"})

            company = await crud.get_company(company_crm_id)
            needs_scrape = not company or not company.get("name")

            if needs_scrape:
                page = rotator.get_page()
                scraper = CompanyScraper(page)
                try:
                    company_data = await scraper.scrape(company_url)
                    mapped = TwentyCRUD.map_company_from_scraper(company_data)
                    mapped["lastPostScrapedAt"] = datetime.now(timezone.utc).isoformat()
                    await crud.update_company(company_crm_id, mapped)
                    logger.info("Scraped and synced company: %s", company_url)
                except Exception as e:
                    logger.warning("Company scrape failed (continuing): %s", e)

            await crud.update_scrape_run(run_crm_id, {"phase": "scraping_posts", "progressPercent": 5})
            start_phase = "scraping_posts"

        # ── Phase 2: Scrape Posts ─────────────────────────────────
        posts_to_process = resume.get("posts_to_process_urns", None)

        if start_phase in ("scraping_posts",):
            await _notify(ws_callback, "progress", {"percent": 5, "message": "Scraping posts...", "phase": "scraping_posts"})

            page = rotator.get_page()
            posts_scraper = CompanyPostsScraper(page)
            try:
                posts = await posts_scraper.scrape(company_url, limit=9999)
            except Exception as e:
                logger.warning("Posts scraping failed: %s", e)
                posts = []

            total_posts = len(posts)
            await crud.update_scrape_run(run_crm_id, {"totalPostsFound": total_posts})

            # Upsert posts into CRM and determine which need user extraction
            now = datetime.now(timezone.utc)
            eligible_urns = []

            for post in posts:
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
                    # Check 7-day rule
                    last_scraped = existing.get("lastScrapedAt")
                    if last_scraped:
                        try:
                            last_dt = datetime.fromisoformat(last_scraped.replace("Z", "+00:00"))
                            if now - last_dt < SEVEN_DAYS:
                                continue  # Skip — scraped recently
                        except Exception:
                            pass
                    eligible_urns.append(post.urn)
                else:
                    await crud.create_post(post_data)
                    eligible_urns.append(post.urn)

            posts_to_process = eligible_urns
            await crud.update_scrape_run(run_crm_id, {
                "phase": "extracting_users",
                "progressPercent": 15,
                "totalPostsFound": total_posts,
            })
            start_phase = "extracting_users"

        # ── Phase 3: Extract Users ────────────────────────────────
        current_post_idx = resume.get("current_post_index", 0)

        if start_phase in ("extracting_users",) and posts_to_process:
            total_eligible = len(posts_to_process)
            total_new_users = 0

            for i in range(current_post_idx, total_eligible):
                # Check pause
                if await _is_paused(crud, run_crm_id):
                    await _save_checkpoint(crud, run_crm_id, "extracting_users", {
                        "posts_to_process_urns": posts_to_process,
                        "current_post_index": i,
                    })
                    await _notify(ws_callback, "paused", {})
                    return

                urn = posts_to_process[i]
                pct = 15 + int((i / max(total_eligible, 1)) * 50)
                await _notify(ws_callback, "progress", {
                    "percent": pct,
                    "message": f"Extracting users from post {i + 1}/{total_eligible}...",
                    "phase": "extracting_users",
                })
                await crud.update_scrape_run(run_crm_id, {
                    "postsProcessed": i + 1,
                    "progressPercent": pct,
                    "progressMessage": f"Post {i + 1}/{total_eligible}",
                })

                # Find the post URL
                post_record = await crud.find_post_by_urn(urn)
                post_url = post_record.get("linkedinUrl") if post_record else None
                if not post_url:
                    post_url = f"https://www.linkedin.com/feed/update/{urn}/"

                # Extract reactions/reposts
                page = rotator.get_page()
                reactions_scraper = PostReactionsScraper(page)
                try:
                    users = await reactions_scraper.scrape(post_url, max_users=200)
                except Exception as e:
                    logger.warning("Failed to extract users from %s: %s", urn, e)
                    users = []

                # Upsert users
                for user in users:
                    if not user.profile_url:
                        continue

                    # Check if person exists
                    existing_person = await crud.find_person_by_linkedin_url(user.profile_url)
                    if existing_person:
                        person_crm_id = existing_person["id"]
                    else:
                        # Create new person
                        parts = user.name.strip().split(None, 1) if user.name else ["", ""]
                        person_data = {
                            "name": {
                                "firstName": parts[0] if parts else "",
                                "lastName": parts[1] if len(parts) > 1 else "",
                            },
                            "linkedinUrl": {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": user.profile_url},
                            "discoveredFromCompany": company_url,
                        }
                        if user.headline:
                            person_data["jobTitle"] = user.headline
                        person_crm_id = await crud.create_person(person_data)
                        total_new_users += 1

                    # Check if engagement already exists
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

                # Update post lastScrapedAt
                if post_record:
                    await crud.update_post(post_record["id"], {
                        "lastScrapedAt": datetime.now(timezone.utc).isoformat(),
                    })

                await crud.update_scrape_run(run_crm_id, {
                    "totalUsersFound": total_new_users,
                    "newUsersFound": total_new_users,
                })

                # Human delays
                await human_between_pages()
                await random_mouse_move(page)

                if (i + 1) % BATCH_BREAK_EVERY == 0 and i + 1 < total_eligible:
                    pause = random.randint(15, 30)
                    await _notify(ws_callback, "progress", {"percent": pct, "message": f"Brief pause after {i + 1} posts..."})
                    await asyncio.sleep(pause)

            await crud.update_scrape_run(run_crm_id, {
                "phase": "scraping_profiles",
                "progressPercent": 65,
                "postsProcessed": len(posts_to_process),
            })
            start_phase = "scraping_profiles"

        # ── Phase 4: Scrape Profiles ──────────────────────────────
        if start_phase in ("scraping_profiles",):
            await _notify(ws_callback, "progress", {"percent": 65, "message": "Scraping user profiles...", "phase": "scraping_profiles"})

            # Get all users discovered for this company that need profile scraping
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

                # 7-day rule
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
            await crud.update_scrape_run(run_crm_id, {"profilesToScrape": total_profiles})

            start_idx = resume.get("current_profile_index", 0)

            for j in range(start_idx, total_profiles):
                if await _is_paused(crud, run_crm_id):
                    await _save_checkpoint(crud, run_crm_id, "scraping_profiles", {
                        "current_profile_index": j,
                    })
                    await _notify(ws_callback, "paused", {})
                    return

                user_info = users_to_scrape[j]
                pct = 65 + int((j / max(total_profiles, 1)) * 25)
                name_display = ""
                if isinstance(user_info["name"], dict):
                    name_display = f"{user_info['name'].get('firstName','')} {user_info['name'].get('lastName','')}".strip()
                await _notify(ws_callback, "progress", {
                    "percent": pct,
                    "message": f"Scraping profile {j + 1}/{total_profiles}: {name_display}",
                    "phase": "scraping_profiles",
                })
                await crud.update_scrape_run(run_crm_id, {
                    "profilesScraped": j,
                    "progressPercent": pct,
                })

                page = rotator.get_page()
                person_scraper = PersonScraper(page)
                try:
                    person = await person_scraper.scrape(user_info["profile_url"])
                    mapped = TwentyCRUD.map_person_from_scraper(person)
                    mapped["discoveredFromCompany"] = company_url
                    await crud.update_person(user_info["crm_id"], mapped)
                except Exception as e:
                    logger.warning("Profile scrape failed %s: %s", user_info["profile_url"], e)

                await human_between_profiles()

                if (j + 1) % BATCH_BREAK_EVERY == 0 and j + 1 < total_profiles:
                    pause = random.randint(20, 45)
                    await _notify(ws_callback, "progress", {"percent": pct, "message": f"Brief pause after {j + 1} profiles..."})
                    await asyncio.sleep(pause)

            await crud.update_scrape_run(run_crm_id, {
                "phase": "done",
                "profilesScraped": total_profiles,
                "progressPercent": 95,
            })
            start_phase = "done"

        # ── Phase 5: Done ─────────────────────────────────────────
        await crud.update_scrape_run(run_crm_id, {
            "status": "completed",
            "phase": "done",
            "progressPercent": 100,
            "progressMessage": "Completed",
            "resumeStateJson": "",
        })
        await _notify(ws_callback, "complete", {})
        logger.info("Company scrape completed: %s", company_url)

    except Exception as e:
        logger.exception("Company scrape failed: %s", company_url)
        await _fail_run(crud, run_crm_id, str(e))
        await _notify(ws_callback, "error", {"message": str(e)})


# ── Helpers ───────────────────────────────────────────────────────

async def _is_paused(crud: TwentyCRUD, run_crm_id: str) -> bool:
    """Check if the run has been paused by the user."""
    run = await crud.get_scrape_run(run_crm_id)
    return run.get("status") == "paused" if run else False


async def _save_checkpoint(crud: TwentyCRUD, run_crm_id: str, phase: str, state: dict) -> None:
    """Save resume checkpoint."""
    state["phase"] = phase
    await crud.update_scrape_run(run_crm_id, {
        "status": "paused",
        "resumeStateJson": json.dumps(state),
        "progressMessage": f"Paused in {phase}",
    })
    logger.info("Checkpoint saved for run %s at phase %s", run_crm_id, phase)


async def _fail_run(crud: TwentyCRUD, run_crm_id: str, error: str) -> None:
    """Mark run as failed."""
    await crud.update_scrape_run(run_crm_id, {
        "status": "failed",
        "errorMessage": error[:500],
    })


async def _notify(ws_callback, event: str, data: dict) -> None:
    """Send WebSocket notification if callback is available."""
    if ws_callback is None:
        return
    try:
        if event == "progress":
            await ws_callback.on_progress(data.get("message", ""), data.get("percent", 0))
        elif event == "complete":
            await ws_callback.on_complete("company_scrape", None)
        elif event == "error":
            await ws_callback.on_error(Exception(data.get("message", "")))
        elif event == "start":
            await ws_callback.on_start("company_scrape", data.get("phase", ""))
        elif event == "paused":
            await ws_callback.on_progress("Paused", -1)
    except Exception:
        pass
