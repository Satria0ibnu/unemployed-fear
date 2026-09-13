import html
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase


class WeWorkRemotelyScraper(ScraperBase):
    site_name = "weworkremotely"

    BASE_URL = "https://weworkremotely.com"
    # Satu kategori dipakai dulu untuk validasi awal, sama seperti pendekatan
    # Kalibrr — bisa diperluas ke kategori lain (design, marketing, dst) setelah
    # pipeline terbukti jalan.
    CATEGORY_RSS_PATH = "/categories/remote-programming-jobs.rss"

    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        # WWR tidak expose halaman listing biasa untuk kategori (butuh CSS
        # selector fragile) — dipakai RSS feed kategori yang sudah eksplisit
        # diizinkan robots.txt dan langsung berisi <link> ke tiap halaman detail.
        # max_pages diabaikan: RSS ini tidak dipaginasi, selalu mengembalikan
        # listing terbaru dalam satu response.
        response = self._client.get(f"{self.BASE_URL}{self.CATEGORY_RSS_PATH}")
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return []

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            return []

        urls = [
            link.text.strip()
            for link in root.findall(".//item/link")
            if link.text
        ]
        return list(dict.fromkeys(urls))  # dedup sambil pertahankan urutan

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return None

        job_data = self._extract_json_ld_job(response.text)
        if not job_data:
            # Terverifikasi lewat riset: sebagian listing WWR (template
            # off-platform/syndicated) tidak punya blok JSON-LD sama sekali
            # meski halamannya valid — lewati, jangan crash.
            return None

        return self._map_to_listing(job_data, source_url=url)

    def _extract_json_ld_job(self, html: str) -> dict | None:
        tree = HTMLParser(html)
        for script_node in tree.css("script[type='application/ld+json']"):
            try:
                data = json.loads(script_node.text())
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                return data
        return None

    def _map_to_listing(self, job: dict, source_url: str) -> ScrapedJobListing | None:
        title = job.get("title")
        description = job.get("description")
        if not title or not description:
            return None

        hiring_org = job.get("hiringOrganization") or {}
        salary_min, salary_max, salary_currency = self._parse_salary(job.get("baseSalary"))

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(hiring_org.get("name") or "Unknown").strip(),
            location_city=None,
            # hiringOrganization.address itu alamat HQ perusahaan, BUKAN syarat
            # lokasi pelamar — WWR job selalu remote tanpa lokasi kerja tetap,
            # jadi sengaja dibiarkan None daripada diisi data yang menyesatkan.
            location_region=None,
            job_type=job.get("employmentType"),
            job_level=None,
            # occupationalCategory kadang bernilai sama di banyak listing berbeda
            # dalam satu kategori RSS (ditemukan saat riset) — tetap dipetakan
            # apa adanya, normalisasi kategori jadi tanggung jawab AI layer nanti.
            category=job.get("occupationalCategory"),
            # JSON-LD WWR menyimpan description sebagai HTML yang di-escape jadi
            # entity teks (&lt;p&gt; dst) — unescape dulu supaya description_raw
            # konsisten HTML asli seperti field sejenis di scraper lain.
            description_raw=html.unescape(description),
            qualifications_raw=None,
            is_active=None,
            posted_at=self._parse_datetime(job.get("datePosted")),
            updated_at_source=None,
            deadline_at=self._parse_datetime(job.get("validThrough")),
            source_native_id=self._extract_native_id(job, source_url),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            work_arrangement="remote" if job.get("jobLocationType") == "TELECOMMUTE" else None,
            skill_tags=None,
            education_level=None,
            experience_years_min=None,
            benefits_raw=None,
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _extract_native_id(self, job: dict, source_url: str) -> str | None:
        identifier = job.get("identifier") or {}
        value = identifier.get("value")
        if value:
            return value
        # Fallback: slug terakhir di URL (identifier.value biasanya sama persis
        # dengan ini, tapi kalau field identifier tidak ada sama sekali).
        return source_url.rstrip("/").rsplit("/", 1)[-1] or None

    def _parse_salary(self, base_salary: dict | None) -> tuple[int | None, int | None, str | None]:
        if not base_salary:
            return None, None, None

        currency = base_salary.get("currency")
        value = base_salary.get("value") or {}
        try:
            min_value = int(value.get("minValue")) or None
            max_value = int(value.get("maxValue")) or None
        except (TypeError, ValueError):
            min_value, max_value = None, None

        if min_value is None and max_value is None:
            return None, None, None
        return min_value, max_value, currency

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            # Format WWR: "2026-08-18 20:33:08 UTC" — bukan ISO8601 standar
            # (spasi bukan 'T', "UTC" literal bukan offset) — normalisasi dulu.
            cleaned = value.replace(" UTC", "+00:00").replace(" ", "T", 1)
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
