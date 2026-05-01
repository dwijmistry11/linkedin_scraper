"""Company scraping pipeline — batch-based: scrape 5 posts, extract users, repeat."""

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
BATCH_SIZE = 1  # Process 1 post at a time: scrape post → extract users → scrape profiles → next post
PROFILE_BATCH_SIZE = 3  # Scrape 3 profiles then take a break


async def run_company_scrape(
    pool: BrowserPool,
    crud: TwentyCRUD,
    run_crm_id: str,
    company_crm_id: str,
    company_url: str,
    session_entries: list[dict],
    ws_callback=None,
) -> None:
    """Main pipeline — batch-based approach."""
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
        await _update_run(crud, run_crm_id, {"status": "running"})

        # ── Phase 1: Company Info ─────────────────────────────────
        if start_phase == "company_info":
            await _progress(crud, run_crm_id, ws_callback, 2,
                            "Step 1: Checking company information...", "company_info")

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
                    mapped["lastPostScrapedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    await crud.update_company(company_crm_id, mapped)
                    await _progress(crud, run_crm_id, ws_callback, 5,
                                    f"Company info saved: {company_data.name}", "company_info")
                except Exception as e:
                    await _progress(crud, run_crm_id, ws_callback, 5,
                                    f"Company scrape failed ({e}), continuing...", "company_info")
            else:
                await _progress(crud, run_crm_id, ws_callback, 5,
                                f"Company already in CRM: {company.get('name', 'Unknown')}", "company_info")

            start_phase = "scraping_posts"

        # ── Phase 2+3: Batch loop — scrape 5 posts, extract users, repeat ──
        batch_number = resume.get("batch_number", 0)
        total_posts_found = resume.get("total_posts_found", 0)
        total_new_users = resume.get("total_new_users", 0)
        all_processed_urns = set(resume.get("processed_urns", []))

        # Load existing posts from CRM to avoid re-scraping
        existing_posts = await crud.list_posts_for_company(company_url)
        fully_done_urns = set()  # posts with lastScrapedAt (users already extracted)
        known_urns = set()       # all posts in CRM (may still need user extraction)
        pending_posts_from_crm = []  # posts in CRM but users not yet extracted

        for ep in existing_posts:
            urn = ep.get("urn")
            if not urn:
                continue
            known_urns.add(urn)
            if ep.get("lastScrapedAt"):
                fully_done_urns.add(urn)
                all_processed_urns.add(urn)
            else:
                # Post exists but users never extracted — queue for extraction
                pending_posts_from_crm.append(ep)

        if fully_done_urns:
            await _progress(crud, run_crm_id, ws_callback, 7,
                            f"{len(fully_done_urns)} posts fully done, {len(pending_posts_from_crm)} pending user extraction",
                            "scraping_posts")

        if start_phase in ("scraping_posts", "extracting_users"):
            # First: process any pending posts from CRM that need user extraction
            if pending_posts_from_crm:
                await _progress(crud, run_crm_id, ws_callback, 8,
                                f"Processing {len(pending_posts_from_crm)} posts pending from previous run...",
                                "extracting_users")

                for i, ep in enumerate(pending_posts_from_crm):
                    if await _is_paused(crud, run_crm_id):
                        await _save_checkpoint(crud, run_crm_id, ws_callback, "scraping_posts", {
                            "batch_number": 0, "total_posts_found": total_posts_found,
                            "total_new_users": total_new_users, "processed_urns": list(all_processed_urns),
                        })
                        return

                    urn = ep.get("urn", "")
                    post_url = ep.get("linkedinUrl") or f"https://www.linkedin.com/feed/update/{urn}/"
                    await _progress(crud, run_crm_id, ws_callback, 10,
                                    f"Pending post {i+1}/{len(pending_posts_from_crm)}: Extracting users...",
                                    "extracting_users")

                    page = rotator.get_page()
                    reactions_scraper = PostReactionsScraper(page)
                    try:
                        users = await reactions_scraper.scrape(post_url, max_users=200)
                        await _progress(crud, run_crm_id, ws_callback, 10,
                                        f"Pending post {i+1}/{len(pending_posts_from_crm)}: Saving {len(users)} users to CRM...",
                                        "extracting_users")
                        new = await _upsert_users_to_crm(crud, users, urn, company_url)
                        total_new_users += new
                    except Exception as e:
                        logger.warning("Failed extracting users from pending post %s: %s", urn, e)

                    await crud.update_post(ep["id"], {"lastScrapedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
                    all_processed_urns.add(urn)
                    await _update_run(crud, run_crm_id, {
                        "postsProcessed": len(all_processed_urns), "totalUsersFound": total_new_users,
                        "newUsersFound": total_new_users,
                    })
                    delay = random.uniform(20.0, 40.0)
                    await _progress(crud, run_crm_id, ws_callback, 10,
                                    f"Pending post {i+1}/{len(pending_posts_from_crm)} done. Waiting {int(delay)}s...",
                                    "extracting_users")
                    await asyncio.sleep(delay)
                    await random_mouse_move(page)

                # Scrape profiles for pending batch
                batch_profiles = await _scrape_batch_profiles(crud, run_crm_id, ws_callback, rotator, company_url, 0)

            await _progress(crud, run_crm_id, ws_callback, 12,
                            "Discovering new posts...", "scraping_posts")

            page = rotator.get_page()
            posts_scraper = CompanyPostsScraper(page)

            # Scrape posts in batches
            keep_going = True
            while keep_going:
                batch_number += 1

                # Check pause
                if await _is_paused(crud, run_crm_id):
                    await _save_checkpoint(crud, run_crm_id, ws_callback, "scraping_posts", {
                        "batch_number": batch_number - 1,
                        "total_posts_found": total_posts_found,
                        "total_new_users": total_new_users,
                        "processed_urns": list(all_processed_urns),
                    })
                    return

                # Scrape next batch of posts
                await _progress(crud, run_crm_id, ws_callback, 10,
                                f"Batch {batch_number}: Scrolling for posts (loading {BATCH_SIZE} more)...",
                                "scraping_posts")

                try:
                    # Scrape posts — we get all visible posts, but only process new ones
                    posts = await posts_scraper.scrape(company_url, limit=BATCH_SIZE * batch_number)
                except Exception as e:
                    await _progress(crud, run_crm_id, ws_callback, 10,
                                    f"Post scraping failed: {e}", "scraping_posts")
                    posts = []
                    keep_going = False
                    continue

                # Filter to only truly new posts (not in CRM at all, not already processed)
                new_posts = [p for p in posts if p.urn and p.urn not in all_processed_urns and p.urn not in known_urns]

                if not new_posts:
                    await _progress(crud, run_crm_id, ws_callback, 15,
                                    f"No more new posts found. Total: {total_posts_found} posts discovered.",
                                    "scraping_posts")
                    keep_going = False
                    continue

                total_posts_found += len(new_posts)
                await _progress(crud, run_crm_id, ws_callback, 12,
                                f"Batch {batch_number}: Found {len(new_posts)} new posts (total: {total_posts_found}). Saving...",
                                "scraping_posts")
                await _update_run(crud, run_crm_id, {"totalPostsFound": total_posts_found})

                # Save posts to CRM and determine which need user extraction
                now = datetime.now(timezone.utc)
                eligible_posts = []

                for post in new_posts:
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
                                    all_processed_urns.add(post.urn)
                                    continue
                            except Exception:
                                pass
                        eligible_posts.append(post)
                    else:
                        await crud.create_post(post_data)
                        eligible_posts.append(post)

                    all_processed_urns.add(post.urn)

                # ── Extract users from this batch's posts ──
                if eligible_posts:
                    await _progress(crud, run_crm_id, ws_callback, 15,
                                    f"Batch {batch_number}: Extracting users from {len(eligible_posts)} posts...",
                                    "extracting_users")

                    for i, post in enumerate(eligible_posts):
                        if await _is_paused(crud, run_crm_id):
                            await _save_checkpoint(crud, run_crm_id, ws_callback, "scraping_posts", {
                                "batch_number": batch_number,
                                "total_posts_found": total_posts_found,
                                "total_new_users": total_new_users,
                                "processed_urns": list(all_processed_urns),
                            })
                            return

                        post_url = post.linkedin_url or f"https://www.linkedin.com/feed/update/{post.urn}/"
                        await _progress(crud, run_crm_id, ws_callback, 20,
                                        f"Batch {batch_number}, post {i+1}/{len(eligible_posts)}: Opening reactions...",
                                        "extracting_users")

                        # Extract reactions
                        page = rotator.get_page()
                        reactions_scraper = PostReactionsScraper(page)
                        try:
                            users = await reactions_scraper.scrape(post_url, max_users=200)
                            await _progress(crud, run_crm_id, ws_callback, 22,
                                            f"Batch {batch_number}, post {i+1}/{len(eligible_posts)}: Found {len(users)} engaged users",
                                            "extracting_users")
                        except Exception as e:
                            await _progress(crud, run_crm_id, ws_callback, 22,
                                            f"Batch {batch_number}, post {i+1}: extraction failed ({e})",
                                            "extracting_users")
                            users = []

                        # Upsert users with pacing
                        await _progress(crud, run_crm_id, ws_callback, 22,
                                        f"Batch {batch_number}, post {i+1}/{len(eligible_posts)}: Saving {len(users)} users to CRM...",
                                        "extracting_users")
                        new = await _upsert_users_to_crm(crud, users, post.urn, company_url)
                        total_new_users += new

                        # Update post lastScrapedAt
                        post_record = await crud.find_post_by_urn(post.urn)
                        if post_record:
                            await crud.update_post(post_record["id"], {"lastScrapedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})

                        await _update_run(crud, run_crm_id, {
                            "postsProcessed": len(all_processed_urns),
                            "totalUsersFound": total_new_users,
                            "newUsersFound": total_new_users,
                            # Save progress so crashes don't lose state
                            "resumeStateJson": json.dumps({
                                "phase": "scraping_posts",
                                "batch_number": batch_number,
                                "total_posts_found": total_posts_found,
                                "total_new_users": total_new_users,
                                "processed_urns": list(all_processed_urns),
                            }),
                        })

                        # Human delay
                        delay = random.uniform(20.0, 40.0)
                        await _progress(crud, run_crm_id, ws_callback, 25,
                                        f"Post done ({total_new_users} new users total). Waiting {int(delay)}s...",
                                        "extracting_users")
                        await asyncio.sleep(delay)
                        await random_mouse_move(page)

                # ── Scrape profiles for this batch's new users ──
                batch_profiles = await _scrape_batch_profiles(
                    crud, run_crm_id, ws_callback, rotator, company_url, batch_number
                )
                total_profiles_scraped = resume.get("total_profiles_scraped", 0) + batch_profiles
                await _update_run(crud, run_crm_id, {"profilesScraped": total_profiles_scraped})

                # Break between batches
                if keep_going:
                    pause = random.randint(30, 60)
                    await _progress(crud, run_crm_id, ws_callback, 30,
                                    f"Batch {batch_number} complete ({total_new_users} users, {total_profiles_scraped} profiles). "
                                    f"Taking {pause}s break...",
                                    "scraping_posts")
                    await asyncio.sleep(pause)

            await _progress(crud, run_crm_id, ws_callback, 95,
                            f"All done: {total_posts_found} posts, {total_new_users} new users, {total_profiles_scraped} profiles",
                            "scraping_profiles")

        # ── Standalone Company Scraping ────────────────────────────
        if start_phase == "scraping_companies":
            await _progress(crud, run_crm_id, ws_callback, 5,
                            "Fetching all companies from CRM that need scraping...", "scraping_companies")

            all_companies = await crud.list_companies(limit=500)
            companies_to_scrape = []
            for c in all_companies:
                lu = c.get("linkedinUrl")
                comp_url = lu.get("primaryLinkUrl", "") if isinstance(lu, dict) else (lu or "")
                if not comp_url or "/company/" not in comp_url and "/showcase/" not in comp_url:
                    continue
                # Skip if already has industry/about (already scraped)
                if c.get("industry") or c.get("aboutUs"):
                    continue
                companies_to_scrape.append({"crm_id": c["id"], "url": comp_url, "name": c.get("name", "")})

            total = len(companies_to_scrape)
            skipped = len(all_companies) - total
            await _progress(crud, run_crm_id, ws_callback, 10,
                            f"{total} companies to scrape ({skipped} already have details)", "scraping_companies")

            for j, comp in enumerate(companies_to_scrape):
                if await _is_paused(crud, run_crm_id):
                    await _save_checkpoint(crud, run_crm_id, ws_callback, "scraping_companies", {
                        "current_company_index": j,
                    })
                    return

                pct = 10 + int((j / max(total, 1)) * 85)
                await _progress(crud, run_crm_id, ws_callback, pct,
                                f"Company {j + 1}/{total}: {comp['name']}...", "scraping_companies")

                page = rotator.get_page()
                try:
                    comp_scraper = CompanyScraper(page)
                    comp_data = await comp_scraper.scrape(comp["url"])
                    mapped = TwentyCRUD.map_company_from_scraper(comp_data)
                    await crud.update_company(comp["crm_id"], mapped)
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Company {j + 1}/{total}: {comp_data.name} — {comp_data.industry or 'saved'}",
                                    "scraping_companies")
                except Exception as e:
                    await _progress(crud, run_crm_id, ws_callback, pct,
                                    f"Company {j + 1}/{total}: {comp['name']} failed ({e})", "scraping_companies")

                delay = random.uniform(30.0, 60.0)
                await _progress(crud, run_crm_id, ws_callback, pct,
                                f"Company {j + 1}/{total} done. Waiting {int(delay)}s...", "scraping_companies")
                await asyncio.sleep(delay)

            await _progress(crud, run_crm_id, ws_callback, 95,
                            f"Company scraping complete: {total} companies processed", "scraping_companies")

        # ── Standalone Profile Scraping (when jumping directly) ──
        if start_phase == "scraping_profiles":
            await _progress(crud, run_crm_id, ws_callback, 10,
                            "Profile-only mode: scraping unscraped user profiles...", "scraping_profiles")
            profiles_done = await _scrape_batch_profiles(crud, run_crm_id, ws_callback, rotator, company_url, 0)
            await _progress(crud, run_crm_id, ws_callback, 95,
                            f"Profile scraping complete: {profiles_done} profiles scraped", "scraping_profiles")

        # ── Done ──────────────────────────────────────────────────
        from ..routers.companies import _run_cache
        await _update_run(crud, run_crm_id, {
            "status": "completed",
            "phase": "done",
            "progressPercent": 100,
            "progressMessage": "All done!",
            "resumeStateJson": "",
        })
        _run_cache[run_crm_id] = {**_run_cache.get(run_crm_id, {}), "id": run_crm_id, "status": "completed", "phase": "done", "progressPercent": 100, "progressMessage": "All done!"}
        logger.info("Company scrape completed: %s", company_url)

    except Exception as e:
        logger.exception("Company scrape failed: %s", company_url)
        await _fail_run(crud, run_crm_id, ws_callback, str(e))


# ── CRM update with cache ─────────────────────────────────────────

async def _update_run(crud: TwentyCRUD, run_id: str, data: dict):
    """Update run in CRM and in-memory cache."""
    from ..routers.companies import _run_cache
    _run_cache[run_id] = {**_run_cache.get(run_id, {}), "id": run_id, **data}
    await crud.update_scrape_run(run_id, data)


# ── User upsert helper ────────────────────────────────────────────

async def _upsert_users_to_crm(
    crud: TwentyCRUD, users: list, urn: str, company_url: str
) -> int:
    """Upsert users + engagements to CRM with pacing. Returns new user count."""
    new_count = 0
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
            new_count += 1

        if person_crm_id:
            if not existing_person:
                await crud.create_engagement({
                    "name": f"{user.name} - {user.engagement_type} - {urn[-12:]}",
                    "postUrn": urn, "userProfileUrl": user.profile_url,
                    "engagementType": user.engagement_type, "companyLinkedinUrl": company_url,
                })
            else:
                existing_eng = await crud.find_engagement(urn, user.profile_url, user.engagement_type)
                if not existing_eng:
                    await crud.create_engagement({
                        "name": f"{user.name} - {user.engagement_type} - {urn[-12:]}",
                        "postUrn": urn, "userProfileUrl": user.profile_url,
                        "engagementType": user.engagement_type, "companyLinkedinUrl": company_url,
                    })
        # Pace: ~2s between users to stay under 100 req/min with 2-3 calls each
        await asyncio.sleep(2.0)
    return new_count


# ── Batch profile scraping ────────────────────────────────────────

async def _scrape_batch_profiles(
    crud: TwentyCRUD, run_crm_id: str, ws_callback,
    rotator: SessionRotator, company_url: str, batch_number: int,
) -> int:
    """Scrape full profiles for users discovered in this batch that haven't been scraped yet."""
    now = datetime.now(timezone.utc)
    all_users = await crud.list_users_for_company(company_url)

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

    if not users_to_scrape:
        await _progress(crud, run_crm_id, ws_callback, 28,
                        f"Batch {batch_number}: No new profiles to scrape", "scraping_profiles")
        return 0

    total = len(users_to_scrape)
    await _progress(crud, run_crm_id, ws_callback, 28,
                    f"Batch {batch_number}: Scraping {total} new profiles...", "scraping_profiles")

    scraped = 0
    for j, user_info in enumerate(users_to_scrape):
        if await _is_paused(crud, run_crm_id):
            return scraped

        name_display = ""
        if isinstance(user_info["name"], dict):
            name_display = f"{user_info['name'].get('firstName', '')} {user_info['name'].get('lastName', '')}".strip()

        await _progress(crud, run_crm_id, ws_callback, 28,
                        f"Batch {batch_number}, profile {j + 1}/{total}: {name_display}...", "scraping_profiles")

        page = rotator.get_page()
        person_scraper = PersonScraper(page)
        try:
            person = await person_scraper.scrape(user_info["profile_url"])
            mapped = TwentyCRUD.map_person_from_scraper(person)
            mapped["discoveredFromCompany"] = company_url
            logger.info("Saving profile %s: name=%s, jobTitle=%s, city=%s, url=%s",
                        user_info["crm_id"][:8], mapped.get("name"), mapped.get("jobTitle"),
                        mapped.get("city"), mapped.get("linkedinUrl", {}).get("primaryLinkUrl", "?") if isinstance(mapped.get("linkedinUrl"), dict) else "?")
            success = await crud.update_person(user_info["crm_id"], mapped)
            if not success:
                logger.warning("CRM update_person returned False for %s", user_info["crm_id"][:8])
            scraped += 1

            # Extract current company, create if needed, scrape info, link
            company_info = TwentyCRUD.extract_current_company(person)
            company_label = ""
            if company_info:
                company_label = f" at {company_info['name']}"
                try:
                    comp_linkedin_url = company_info.get("linkedin_url")
                    comp_crm_id = await crud.find_or_create_company(
                        company_info["name"], comp_linkedin_url
                    )
                    if comp_crm_id:
                        await crud.link_person_to_company(user_info["crm_id"], comp_crm_id)

                        # Scrape company details if it has a LinkedIn URL and hasn't been scraped
                        if comp_linkedin_url and "/company/" in comp_linkedin_url:
                            comp_record = await crud.get_company(comp_crm_id)
                            needs_scrape = comp_record and not comp_record.get("industry") and not comp_record.get("aboutUs")
                            if needs_scrape:
                                await _progress(crud, run_crm_id, ws_callback, 28,
                                                f"Scraping company: {company_info['name']}...", "scraping_profiles")
                                try:
                                    comp_page = rotator.get_page()
                                    comp_scraper = CompanyScraper(comp_page)
                                    comp_data = await comp_scraper.scrape(comp_linkedin_url)
                                    comp_mapped = TwentyCRUD.map_company_from_scraper(comp_data)
                                    await crud.update_company(comp_crm_id, comp_mapped)
                                    await _progress(crud, run_crm_id, ws_callback, 28,
                                                    f"Company saved: {comp_data.name} ({comp_data.industry or 'N/A'})",
                                                    "scraping_profiles")
                                    await human_delay(3.0, 6.0)
                                except Exception as cse:
                                    logger.warning("Company scrape failed for %s: %s", company_info["name"], cse)
                except Exception as ce:
                    logger.warning("Company link failed for %s: %s", company_info["name"], ce)

            await _progress(crud, run_crm_id, ws_callback, 28,
                            f"Batch {batch_number}, profile {j + 1}/{total}: {person.name or name_display}{company_label} saved",
                            "scraping_profiles")
        except Exception as e:
            await _progress(crud, run_crm_id, ws_callback, 28,
                            f"Batch {batch_number}, profile {j + 1}/{total}: failed ({e})", "scraping_profiles")

        # Human delay
        delay = random.uniform(30.0, 60.0)
        await _progress(crud, run_crm_id, ws_callback, 28,
                        f"Profile {j + 1}/{total} done. Waiting {int(delay)}s...", "scraping_profiles")
        await asyncio.sleep(delay)

        if (j + 1) % PROFILE_BATCH_SIZE == 0 and j + 1 < total:
            pause = random.randint(60, 120)
            await _progress(crud, run_crm_id, ws_callback, 28,
                            f"Break after {j + 1} profiles ({pause}s)...", "scraping_profiles")
            await asyncio.sleep(pause)

    await _progress(crud, run_crm_id, ws_callback, 30,
                    f"Batch {batch_number}: {scraped}/{total} profiles scraped", "scraping_profiles")
    return scraped


# ── Helpers ───────────────────────────────────────────────────────

async def _progress(crud: TwentyCRUD, run_id: str, ws_callback, pct: int, msg: str, phase: str):
    # Update in-memory cache (for poll endpoint — no CRM API call needed)
    from ..routers.companies import _run_cache
    _run_cache[run_id] = {
        **_run_cache.get(run_id, {}),
        "id": run_id,
        "progressPercent": pct,
        "progressMessage": msg,
        "phase": phase,
        "status": "running",
    }
    # Update CRM less frequently — only every 5% change or phase change
    cached = _run_cache.get(run_id, {})
    last_crm_pct = cached.get("_last_crm_pct", -10)
    last_crm_phase = cached.get("_last_crm_phase", "")
    if abs(pct - last_crm_pct) >= 5 or phase != last_crm_phase:
        await crud.update_scrape_run(run_id, {
            "progressPercent": pct,
            "progressMessage": msg,
            "phase": phase,
        })
        _run_cache[run_id]["_last_crm_pct"] = pct
        _run_cache[run_id]["_last_crm_phase"] = phase
    if ws_callback:
        try:
            await ws_callback.on_progress(msg, pct)
        except Exception:
            pass


async def _is_paused(crud: TwentyCRUD, run_crm_id: str) -> bool:
    run = await crud.get_scrape_run(run_crm_id)
    return run.get("status") == "paused" if run else False


async def _save_checkpoint(crud: TwentyCRUD, run_crm_id: str, ws_callback, phase: str, state: dict):
    from ..routers.companies import _run_cache
    state["phase"] = phase
    await _update_run(crud, run_crm_id, {
        "status": "paused",
        "resumeStateJson": json.dumps(state),
        "progressMessage": f"Paused at {phase}",
    })
    _run_cache[run_crm_id] = {**_run_cache.get(run_crm_id, {}), "id": run_crm_id, "status": "paused", "progressMessage": f"Paused at {phase}"}
    if ws_callback:
        try:
            await ws_callback.on_progress(f"Paused at {phase}", -1)
        except Exception:
            pass


async def _fail_run(crud: TwentyCRUD, run_crm_id: str, ws_callback, error: str):
    from ..routers.companies import _run_cache
    await _update_run(crud, run_crm_id, {
        "status": "failed",
        "errorMessage": error[:500],
        "progressMessage": f"Failed: {error[:200]}",
    })
    _run_cache[run_crm_id] = {**_run_cache.get(run_crm_id, {}), "id": run_crm_id, "status": "failed", "errorMessage": error[:500], "progressMessage": f"Failed: {error[:200]}"}
    if ws_callback:
        try:
            await ws_callback.on_error(Exception(error))
        except Exception:
            pass
