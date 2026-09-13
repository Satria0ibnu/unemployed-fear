import json
import re
import time
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase

_LEADING_NUMBER = re.compile(r"(\d+)")


class LokerIdScraper(ScraperBase):
    site_name = "lokerid"

    BASE_URL = "https://www.loker.id"

    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        # loker.id tidak punya sitemap.xml (404 saat riset) — homepage sendiri
        # sudah langsung memuat link ke halaman detail loker (pola /*/*/*.html),
        # tanpa perlu render JS. max_pages diabaikan untuk sekarang karena
        # belum ada pola pagination homepage yang terverifikasi.
        response = self._client.get(f"{self.BASE_URL}/")
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return []

        tree = HTMLParser(response.text)
        urls: list[str] = []
        for anchor in tree.css("a[href]"):
            href = anchor.attributes.get("href")
            if href and href.startswith("/") and href.endswith(".html") and href.count("/") >= 2:
                urls.append(f"{self.BASE_URL}{href}")

        return list(dict.fromkeys(urls))  # dedup sambil pertahankan urutan

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return None

        job = self._extract_remix_job(response.text)
        if job:
            listing = self._map_remix_job(job, source_url=url)
            if listing:
                return listing

        # __remixContext tidak ketemu/gagal parse (kemungkinan struktur route
        # Remix berubah), atau job dict-nya tidak lengkap — coba JSON-LD
        # standalone sebagai fallback yang lebih stabil lintas-versi framework,
        # meski field yang didapat lebih sedikit (lihat docs/scraper-research-findings.md).
        job_ld = self._extract_json_ld_job(response.text)
        if job_ld:
            return self._map_json_ld_job(job_ld, source_url=url)

        return None

    def _extract_remix_job(self, html: str) -> dict | None:
        tree = HTMLParser(html)
        for script_node in tree.css("script"):
            text = script_node.text() or ""
            if "window.__remixContext" not in text:
                continue
            try:
                json_text = text.split("=", 1)[1].strip()
                if json_text.endswith(";"):
                    json_text = json_text[:-1]
                data = json.loads(json_text)
            except (IndexError, ValueError):
                return None

            loader_data = (data.get("state") or {}).get("loaderData") or {}
            # Nama key route (mis. "routes/$parent_category...") terikat pola
            # URL Remix dan bisa berubah — cari entry yang punya key "job"
            # daripada hardcode string route-nya persis (saran riset).
            for entry in loader_data.values():
                if isinstance(entry, dict) and "job" in entry:
                    return entry["job"]
            return None
        return None

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

    def _map_remix_job(self, job: dict, source_url: str) -> ScrapedJobListing | None:
        title = job.get("title")
        description = job.get("job_description")
        if not title or not description:
            return None

        locations = job.get("locations") or []
        location = locations[0] if locations else {}
        types = job.get("types") or []
        job_type = types[0].get("name") if types else None
        level = job.get("level") or {}
        educations = job.get("educations") or []
        education = educations[0].get("name") if educations else None
        ld_json = job.get("ld_json") or {}
        base_salary = (ld_json.get("baseSalary") or {})

        salary_min = job.get("salary_min") or None
        salary_max = job.get("salary_max") or None

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(job.get("company_name") or "Unknown").strip(),
            location_city=location.get("name"),
            location_region=(location.get("parent") or {}).get("name"),
            job_type=job_type,
            job_level=level.get("name"),
            category=job.get("category"),
            description_raw=description,
            qualifications_raw=job.get("qualifications"),
            is_active=job.get("status") == "publish",
            posted_at=self._parse_datetime(job.get("post_date")),
            updated_at_source=self._parse_datetime(job.get("post_modified")),
            deadline_at=None,  # tidak ada field deadline eksplisit (terverifikasi riset)
            source_native_id=str(job["id"]) if job.get("id") is not None else None,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=base_salary.get("currency") if (salary_min or salary_max) else None,
            work_arrangement="remote" if job.get("is_remote") else "onsite",
            skill_tags=None,
            education_level=education,
            experience_years_min=self._parse_experience_years(ld_json.get("experienceRequirements")),
            benefits_raw=None,
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _map_json_ld_job(self, job: dict, source_url: str) -> ScrapedJobListing | None:
        title = job.get("title")
        description = job.get("description")
        if not title or not description:
            return None

        hiring_org = job.get("hiringOrganization") or {}
        address = (job.get("jobLocation") or {}).get("address") or {}
        base_salary = job.get("baseSalary") or {}
        salary_value = base_salary.get("value") or {}
        salary_min = salary_value.get("minValue") or None
        salary_max = salary_value.get("maxValue") or None

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(hiring_org.get("name") or "Unknown").strip(),
            location_city=address.get("addressLocality"),
            # JSON-LD loker.id menduplikasi city ke addressRegion (bukan
            # provinsi asli) — terverifikasi salah saat riset, jangan dipakai.
            location_region=None,
            job_type=job.get("employmentType"),
            job_level=None,
            category=job.get("occupationalCategory"),
            description_raw=description,
            qualifications_raw=None,
            is_active=None,
            posted_at=self._parse_date_only(job.get("datePosted")),
            updated_at_source=None,
            deadline_at=None,
            source_native_id=str((job.get("identifier") or {}).get("value") or "") or None,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=base_salary.get("currency") if (salary_min or salary_max) else None,
            work_arrangement=None,
            skill_tags=None,
            education_level=job.get("educationRequirements"),
            experience_years_min=self._parse_experience_years(job.get("experienceRequirements")),
            benefits_raw=None,
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _parse_experience_years(self, value: str | None) -> int | None:
        # Contoh nilai sumber: "1-2 Tahun" -> ambil angka minimum di depan.
        if not value:
            return None
        match = _LEADING_NUMBER.search(value)
        return int(match.group(1)) if match else None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def _parse_date_only(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
