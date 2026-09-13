import json
import re
import time
from datetime import datetime

import httpx
from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase

_LEADING_NUMBER = re.compile(r"(\d+)")


class WellfoundScraper(ScraperBase):
    site_name = "wellfound"

    BASE_URL = "https://wellfound.com"
    BROWSE_PATH = "/browse/tech-jobs"

    # Path yang eksplisit di-disallow robots.txt Wellfound untuk halaman
    # job/apply — dipakai untuk filter link hasil render Playwright.
    _DISALLOWED_JOB_PATH_MARKERS = ("/jobs/signup", "/jobs/applications", "?")

    def __init__(self):
        # httpx dipakai khusus untuk scrape_listing (halaman detail loker
        # server-rendered, tidak butuh Chromium). Playwright cuma dipakai di
        # discover_listing_urls dan browser-nya ditutup begitu discovery
        # selesai — RAM VPS 956Mi tidak boleh menahan Chromium menyala lebih
        # lama dari yang diperlukan (lihat docs/01-setup-infrastruktur.md).
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        # Wellfound tidak punya sitemap job yang berguna, dan /browse/* +
        # /job-collections/* sepenuhnya client-side rendered (link job tidak
        # ada di HTML mentah) — satu-satunya cara discovery publik yang
        # ketemu saat riset. max_pages = berapa job-collection yang dibuka
        # (tiap collection biasanya cuma menyumbang 0-2 link job publik,
        # sisanya digembok di balik /jobs/signup untuk user anonim).
        job_urls: list[str] = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(
                    f"{self.BASE_URL}{self.BROWSE_PATH}",
                    wait_until="domcontentloaded",
                    timeout=REQUEST_TIMEOUT_SECONDS * 1000,
                )
                page.wait_for_timeout(3000)
                collection_links = page.eval_on_selector_all(
                    "a[href*='/job-collections/']",
                    "els => els.map(e => e.getAttribute('href'))",
                )
                collections = list(dict.fromkeys(l for l in collection_links if l))

                for collection_path in collections[:max_pages]:
                    time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)
                    page.goto(
                        f"{self.BASE_URL}{collection_path}",
                        wait_until="domcontentloaded",
                        timeout=REQUEST_TIMEOUT_SECONDS * 1000,
                    )
                    page.wait_for_timeout(3000)
                    raw_links = page.eval_on_selector_all(
                        "a[href^='/jobs/']",
                        "els => els.map(e => e.getAttribute('href'))",
                    )
                    for href in raw_links:
                        if not href or any(marker in href for marker in self._DISALLOWED_JOB_PATH_MARKERS):
                            continue
                        job_urls.append(f"{self.BASE_URL}{href}")
            finally:
                browser.close()

        return list(dict.fromkeys(job_urls))

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return None

        job = self._extract_json_ld_job(response.text)
        if not job:
            # Terverifikasi lewat riset: sebagian listing (template
            # off-platform/syndicated) tidak punya JSON-LD sama sekali meski
            # halamannya valid — tidak ada sumber data lain yang reliable
            # untuk kasus ini, jadi lewati saja.
            return None

        return self._map_to_listing(job, source_url=url)

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
        job_locations = job.get("jobLocation") or []
        address = (job_locations[0].get("address") if job_locations else None) or {}
        salary_min, salary_max, salary_currency = self._parse_salary(job.get("baseSalary"))

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(hiring_org.get("name") or "Unknown").strip(),
            location_city=address.get("addressLocality"),
            location_region=address.get("addressRegion"),
            job_type=job.get("employmentType"),
            job_level=None,
            # industry Wellfound berupa string multi-tag deskriptif (mis. "Startups,
            # Software, Fin Tech, ..."), bukan kategori tunggal bersih — tetap
            # dipetakan apa adanya, sama seperti occupationalCategory WWR.
            category=job.get("industry"),
            description_raw=description,
            qualifications_raw=None,
            is_active=None,
            posted_at=self._parse_datetime(job.get("datePosted")),
            updated_at_source=None,
            deadline_at=self._parse_datetime(job.get("validThrough")),
            source_native_id=(job.get("identifier") or {}).get("value"),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            # Tidak ada sinyal remote/onsite eksplisit di JSON-LD Wellfound —
            # alamat kantor kosong TIDAK berarti remote (satu sample yang
            # dicek saat riset justru job onsite tapi field city-nya kosong),
            # jadi sengaja None daripada menebak salah.
            work_arrangement=None,
            skill_tags=None,
            education_level=None,
            experience_years_min=self._parse_experience_years(job.get("experienceRequirements")),
            benefits_raw=self._parse_benefits(job.get("jobBenefits")),
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _parse_salary(self, base_salary: dict | None) -> tuple[int | None, int | None, str | None]:
        if not base_salary:
            return None, None, None

        currency = base_salary.get("currency")
        value = base_salary.get("value") or {}
        try:
            min_value = int(float(value.get("minValue"))) or None
        except (TypeError, ValueError):
            min_value = None
        try:
            max_value = int(float(value.get("maxValue"))) or None
        except (TypeError, ValueError):
            max_value = None

        if min_value is None and max_value is None:
            return None, None, None
        return min_value, max_value, currency

    def _parse_benefits(self, value: str | None) -> list[str] | None:
        # jobBenefits Wellfound berupa satu string dipisah " - ", bukan array
        # (beda dari benefits_raw Glints yang sudah list) — pecah jadi list[str]
        # supaya tipe konsisten lintas situs.
        if not value:
            return None
        benefits = [item.strip() for item in value.split(" - ") if item.strip()]
        return benefits or None

    def _parse_experience_years(self, value: str | dict | None) -> int | None:
        # schema.org membolehkan experienceRequirements berupa string bebas
        # ("7+ years") ATAU object OccupationalExperienceRequirements dengan
        # monthsOfExperience — Wellfound ternyata memakai keduanya tergantung
        # listing (terverifikasi lewat crash saat tes, bukan cuma dugaan).
        if not value:
            return None
        if isinstance(value, dict):
            months = value.get("monthsOfExperience")
            return months // 12 if isinstance(months, (int, float)) else None
        match = _LEADING_NUMBER.search(value)
        return int(match.group(1)) if match else None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
