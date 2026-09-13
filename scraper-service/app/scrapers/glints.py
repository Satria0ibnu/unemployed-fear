import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase


class GlintsScraper(ScraperBase):
    site_name = "glints"

    BASE_URL = "https://glints.com"
    SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"
    # Sitemap job di-split jadi ratusan file (sitemap_job_id_1.xml, _2.xml, dst)
    # — dipakai untuk discovery karena halaman search (/opportunities/jobs/explore)
    # eksplisit di-disallow robots.txt.
    JOB_SITEMAP_PATTERN = "sitemap_job_id_{n}.xml"

    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        # max_pages di sini berarti "berapa file sub-sitemap job yang diambil",
        # bukan halaman listing biasa — tiap sub-sitemap berisi ratusan URL.
        urls: list[str] = []
        for n in range(1, max_pages + 1):
            sitemap_url = f"{self.BASE_URL}/{self.JOB_SITEMAP_PATTERN.format(n=n)}"
            response = self._client.get(sitemap_url)
            time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

            if response.status_code != 200:
                break

            try:
                root = ET.fromstring(response.text)
            except ET.ParseError:
                break

            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//sm:loc", ns):
                url = (loc.text or "").strip()
                # Tiap job punya 2 varian locale (/opportunities/jobs/... dan
                # /en/opportunities/jobs/...) — ambil satu locale saja (default,
                # tanpa /en/) supaya tidak scrape job yang sama dua kali.
                if "/opportunities/jobs/" in url and "/en/opportunities/jobs/" not in url:
                    urls.append(url)

        return list(dict.fromkeys(urls))

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return None

        job = self._extract_next_data_job(response.text)
        if not job:
            return None

        description = self._extract_json_ld_description(response.text)
        if not description:
            # JSON-LD tidak ketemu — fallback ke descriptionJsonString (Draft.js
            # blocks) dikonversi jadi paragraf HTML sederhana, supaya tidak
            # kehilangan seluruh listing hanya karena satu sumber deskripsi hilang.
            description = self._draftjs_to_html(job.get("descriptionJsonString"))

        return self._map_to_listing(job, description, source_url=url)

    def _extract_next_data_job(self, html: str) -> dict | None:
        tree = HTMLParser(html)
        script_node = tree.css_first("script#__NEXT_DATA__")
        if not script_node:
            return None
        try:
            next_data = json.loads(script_node.text())
            return next_data["props"]["pageProps"]["initialData"]["data"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _extract_json_ld_description(self, html: str) -> str | None:
        tree = HTMLParser(html)
        for script_node in tree.css("script[type='application/ld+json']"):
            try:
                data = json.loads(script_node.text())
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                return data.get("description")
        return None

    def _draftjs_to_html(self, json_string: str | None) -> str | None:
        if not json_string:
            return None
        try:
            data = json.loads(json_string)
        except (ValueError, TypeError):
            return None
        blocks = data.get("blocks") or []
        paragraphs = [b.get("text", "") for b in blocks if b.get("text")]
        return "".join(f"<p>{p}</p>" for p in paragraphs) or None

    def _map_to_listing(self, job: dict, description: str | None, source_url: str) -> ScrapedJobListing | None:
        title = job.get("title")
        if not title or not description:
            return None

        company = job.get("company") or {}
        location = job.get("location") or {}
        category = job.get("hierarchicalJobCategory") or {}
        skills_field = job.get("skills") or job.get("JobSkills") or []
        skill_tags = [
            s["skill"]["name"]
            for s in skills_field
            if isinstance(s, dict) and s.get("skill", {}).get("name")
        ] or None

        salary_min, salary_max, salary_currency = self._pick_salary(job.get("salaries"))

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(company.get("name") or "Unknown").strip(),
            location_city=location.get("formattedName"),
            location_region=self._find_province_name(location),
            job_type=job.get("type"),
            # Glints tidak punya field "level" tunggal yang bersih (perlu derivasi
            # dari educationLevel + min/maxYearsOfExperience) — sengaja dibiarkan
            # None daripada menebak kategori level yang tidak dinyatakan sumber.
            job_level=None,
            category=category.get("name"),
            description_raw=description,
            # JobSkills/skills Glints berbentuk list skill terstruktur (nama +
            # mustHave), bukan teks kualifikasi bebas — datanya masuk skill_tags,
            # bukan dipaksakan jadi qualifications_raw.
            qualifications_raw=None,
            is_active=job.get("status") == "OPEN",
            posted_at=self._parse_datetime(job.get("createdAt")),
            updated_at_source=self._parse_datetime(job.get("updatedAt")),
            deadline_at=self._parse_date_only(job.get("expiryDate")),
            source_native_id=job.get("id"),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            work_arrangement=(job.get("workArrangementOption") or "").lower() or None,
            skill_tags=skill_tags,
            education_level=job.get("educationLevel"),
            experience_years_min=job.get("minYearsOfExperience"),
            benefits_raw=self._extract_benefit_titles(job.get("benefits")),
            gender_requirement_raw=job.get("gender"),
            max_age_raw=job.get("maxAge"),
            scraped_at=datetime.utcnow(),
        )

    def _extract_benefit_titles(self, benefits: list | None) -> list[str] | None:
        # benefits_raw bertipe list[str] di skema (konsisten dengan Wellfound
        # jobBenefits) — ambil label title-nya saja, bukan seluruh dict mentah
        # (benefit code/logo/description tidak dipakai di manapun saat ini).
        if not benefits:
            return None
        titles = [b.get("title") for b in benefits if isinstance(b, dict) and b.get("title")]
        return titles or None

    def _find_province_name(self, location: dict) -> str | None:
        for parent in location.get("parents") or []:
            if parent.get("administrativeLevelName") == "Province":
                return parent.get("name")
        return None

    def _pick_salary(self, salaries: list | None) -> tuple[int | None, int | None, str | None]:
        if not salaries:
            return None, None, None
        basic = next((s for s in salaries if s.get("salaryType") == "BASIC"), salaries[0])
        min_amount = basic.get("minAmount") or None
        max_amount = basic.get("maxAmount") or None
        if min_amount is None and max_amount is None:
            return None, None, None
        return min_amount, max_amount, basic.get("CurrencyCode")

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _parse_date_only(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
