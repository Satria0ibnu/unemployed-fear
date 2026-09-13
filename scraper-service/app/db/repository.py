import json
from datetime import datetime

from app.db.connection import get_connection
from app.models.job_listing import ScrapedJobListing


def save_scraped_listing(listing: ScrapedJobListing) -> None:
    """Simpan satu hasil scrape ke database.

    GENERIK untuk ketujuh situs — semua scraper menghasilkan ScrapedJobListing
    dengan struktur field yang sama.

    Belum ada dedup semantik lintas-source (fase AI Layer). Loker sama dari
    situs BERBEDA akan tetap tersimpan sebagai job_postings terpisah untuk
    sekarang — keterbatasan yang disadari, bukan bug.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM job_listing_sources WHERE source_url = %s",
                (listing.source_url,),
            )
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """
                    UPDATE job_listing_sources
                    SET last_checked_at = %s, source_reported_active = %s, status = 'active'
                    WHERE source_url = %s
                    """,
                    (datetime.utcnow(), listing.is_active, listing.source_url),
                )
                conn.commit()
                return

            cur.execute(
                """
                INSERT INTO job_postings
                    (title, company_name, location_city, location_region,
                     job_type, job_level, category, description, qualifications,
                     posted_at, deadline_at, updated_at_source, status,
                     salary_min, salary_max, salary_currency, work_arrangement,
                     skill_tags, education_level, experience_years_min,
                     benefits_raw, gender_requirement_raw, max_age_raw,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active',
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    listing.title, listing.company_name, listing.location_city,
                    listing.location_region, listing.job_type, listing.job_level,
                    listing.category, listing.description_raw, listing.qualifications_raw,
                    listing.posted_at, listing.deadline_at, listing.updated_at_source,
                    listing.salary_min, listing.salary_max, listing.salary_currency,
                    listing.work_arrangement,
                    # skill_tags & benefits_raw adalah kolom json di migrasi — psycopg2
                    # TIDAK otomatis serialize list Python, wajib json.dumps() dulu.
                    # None tetap None (jadi NULL), bukan literal string "null".
                    json.dumps(listing.skill_tags) if listing.skill_tags is not None else None,
                    listing.education_level, listing.experience_years_min,
                    json.dumps(listing.benefits_raw) if listing.benefits_raw is not None else None,
                    listing.gender_requirement_raw,
                    listing.max_age_raw,
                    datetime.utcnow(), datetime.utcnow(),
                ),
            )
            job_posting_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO job_listing_sources
                    (job_posting_id, source_site, source_url, source_native_id,
                     raw_description, source_reported_active, scraped_at,
                     last_checked_at, check_attempts, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 'active', %s, %s)
                """,
                (
                    job_posting_id, listing.source_site, listing.source_url,
                    listing.source_native_id, listing.description_raw,
                    listing.is_active, listing.scraped_at, listing.scraped_at,
                    datetime.utcnow(), datetime.utcnow(),
                ),
            )
            conn.commit()
    finally:
        conn.close()
