import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase
from app.scrapers.utils.nextjs_flight_parser import extract_flight_chunks, find_value_with_key


class KitalulusScraper(ScraperBase):
    site_name = "kitalulus"

    BASE_URL = "https://www.kitalulus.com"
    SITEMAP_INDEX_URL = "https://kitalulus.com/sitemap.xml"
    # Nama file sub-sitemap job (job-detail-1.xml, _2.xml, dst) — ada 148 file
    # saat riset. Dipakai langsung karena bisa diprediksi, tanpa perlu parse
    # ulang sitemap index tiap kali.
    JOB_SITEMAP_PATTERN = "https://www.kitalulus.com/sitemap/sitemap-jobs/job-detail-{n}.xml"

    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        # max_pages = berapa file sub-sitemap job-detail-N.xml yang diambil.
        # CATATAN (terverifikasi lewat riset & tes manual di beberapa file
        # berbeda): sitemap job Kitalulus tampaknya berisi banyak loker yang
        # SUDAH ditutup (isClosed=true), bukan cuma yang aktif — discovery
        # lewat sitemap saja tidak menjamin hasilnya loker aktif, filter
        # status tetap wajib dilakukan di layer setelah scrape (is_active).
        urls: list[str] = []
        for n in range(1, max_pages + 1):
            response = self._client.get(self.JOB_SITEMAP_PATTERN.format(n=n))
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
                if url:
                    urls.append(url)

        return list(dict.fromkeys(urls))

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return None

        chunks = extract_flight_chunks(response.text)
        vacancy = find_value_with_key(chunks, "vacancy")
        if not vacancy:
            # Struktur RSC berubah / halaman tidak valid — lewati, jangan crash.
            return None

        return self._map_to_listing(vacancy, source_url=url)

    def _map_to_listing(self, vacancy: dict, source_url: str) -> ScrapedJobListing | None:
        title = vacancy.get("positionName")
        # formattedDescription (HTML) dipakai sebagai description_raw, bukan
        # `description` (plain text dengan newline mentah) — konsisten dengan
        # format description_raw HTML di scraper lain. Tapi terverifikasi lewat
        # tes: tidak semua listing punya formattedDescription — sebagian cuma
        # punya description plain text, perlu fallback dikonversi jadi HTML
        # sederhana daripada kehilangan seluruh listing.
        description = vacancy.get("formattedDescription")
        if not description and vacancy.get("description"):
            description = self._plain_text_to_html(vacancy["description"])
        if not title or not description:
            return None

        company = vacancy.get("company") or {}
        city = vacancy.get("city") or {}
        province = vacancy.get("province") or {}
        job_role = vacancy.get("jobRole") or {}

        salary_min = vacancy.get("salaryLowerBound") or None
        salary_max = vacancy.get("salaryUpperBound") or None

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(company.get("name") or "Unknown").strip(),
            location_city=city.get("name"),
            location_region=province.get("name"),
            job_type=vacancy.get("typeStr"),
            job_level=None,
            category=job_role.get("displayName"),
            description_raw=description,
            # Kitalulus tidak memisahkan kualifikasi dari deskripsi tugas —
            # keduanya satu field (formattedDescription) — jangan duplikasi
            # isi yang sama ke qualifications_raw.
            qualifications_raw=None,
            is_active=bool(vacancy.get("isPublished")) and not bool(vacancy.get("isClosed")),
            posted_at=None,  # tidak ada field tanggal posting eksplisit (terverifikasi riset)
            updated_at_source=self._parse_micro_timestamp(vacancy.get("updatedAt")),
            deadline_at=self._parse_micro_timestamp(vacancy.get("closeDate")),
            source_native_id=vacancy.get("id"),
            salary_min=salary_min,
            salary_max=salary_max,
            # Tidak ada field currency eksplisit — Kitalulus situs Indonesia
            # saja, salary selalu Rupiah (konvensi situs, sama seperti asumsi
            # USD untuk RemoteOK).
            salary_currency="IDR" if (salary_min or salary_max) else None,
            work_arrangement=self._parse_work_arrangement(vacancy.get("locationSiteStr")),
            skill_tags=vacancy.get("skillTags") or None,
            education_level=vacancy.get("educationLevelStr"),
            experience_years_min=vacancy.get("minExperience"),
            benefits_raw=self._parse_benefits(vacancy.get("benefits")),
            gender_requirement_raw=vacancy.get("genderStr"),
            max_age_raw=vacancy.get("maxAge"),
            scraped_at=datetime.utcnow(),
        )

    def _plain_text_to_html(self, text: str) -> str:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "".join(f"<p>{line}</p>" for line in lines)

    def _parse_work_arrangement(self, value: str | None) -> str | None:
        if not value:
            return None
        lowered = value.lower()
        if "wfh" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        if "wfo" in lowered:
            return "onsite"
        return None

    def _parse_benefits(self, value) -> list[str] | None:
        # Bentuk asli field ini belum ketemu terisi di sample manapun saat
        # riset maupun tes (selalu null) — tangani beberapa kemungkinan
        # bentuk secara defensif daripada mengasumsikan satu bentuk tertentu.
        if not value:
            return None
        if isinstance(value, list):
            if all(isinstance(item, str) for item in value):
                return value or None
            titles = [
                item.get("name") or item.get("title") or item.get("label")
                for item in value
                if isinstance(item, dict)
            ]
            titles = [t for t in titles if t]
            return titles or None
        return None

    def _parse_micro_timestamp(self, value: int | None) -> datetime | None:
        # Timestamp Kitalulus dalam mikrodetik sejak epoch (bukan detik atau
        # milidetik) — terverifikasi lewat cross-check manual terhadap
        # updatedAtStr yang human-readable di riset.
        if not value:
            return None
        try:
            return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
