import json
import time
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase


class KalibrrScraper(ScraperBase):
    site_name = "kalibrr"

    BASE_URL = "https://www.kalibrr.id"
    # Kategori magang dipakai dulu untuk validasi awal — bisa diperluas
    # ke kategori lain setelah pipeline terbukti jalan.
    LISTING_PATH = "/home/w/100-internship-or-ojt"

    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        urls: list[str] = []
        for page in range(1, max_pages + 1):
            listing_page_url = f"{self.BASE_URL}{self.LISTING_PATH}?page={page}"
            response = self._client.get(listing_page_url)
            time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

            if response.status_code != 200:
                # Halaman listing gagal diambil — hentikan discovery,
                # jangan asal lanjut ke halaman berikutnya.
                break

            tree = HTMLParser(response.text)
            # Untuk discovery URL (halaman listing/search), CSS selector masih
            # dipakai karena __NEXT_DATA__ di halaman *listing* berisi struktur
            # berbeda dari halaman *detail* — cukup ambil href-nya saja di sini,
            # tidak perlu data terstruktur lengkap. Perlu diverifikasi ulang
            # manual kalau discovery ternyata mengembalikan 0 URL.
            for anchor in tree.css("a[href*='/c/'][href*='/jobs/']"):
                href = anchor.attributes.get("href")
                if href and href.startswith("/"):
                    urls.append(f"{self.BASE_URL}{href}")

        return list(dict.fromkeys(urls))  # dedup sambil pertahankan urutan

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return None

        job_data = self._extract_next_data_job(response.text)
        if not job_data:
            # Blok __NEXT_DATA__ tidak ketemu atau strukturnya beda dari
            # yang diharapkan — kemungkinan situs berubah format. Lewati,
            # jangan crash, supaya satu halaman bermasalah tidak menghentikan
            # seluruh batch.
            return None

        return self._map_to_listing(job_data, source_url=url)

    def _extract_next_data_job(self, html: str) -> dict | None:
        tree = HTMLParser(html)
        script_node = tree.css_first("script#__NEXT_DATA__")
        if not script_node:
            return None

        try:
            next_data = json.loads(script_node.text())
            return next_data["props"]["pageProps"]["job"]
        except (json.JSONDecodeError, KeyError, TypeError):
            # Struktur JSON berubah dari yang diharapkan — lebih baik gagal
            # senyap di sini (return None) daripada crash seluruh batch scrape.
            return None

    def _map_to_listing(self, job: dict, source_url: str) -> ScrapedJobListing | None:
        title = job.get("name")
        description = job.get("description")
        if not title or not description:
            # Field paling wajib tidak ada — anggap data tidak valid.
            return None

        company = job.get("company") or {}
        location = job.get("googleLocation") or {}
        address = location.get("addressComponents") or {}

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(company.get("name") or "Unknown").strip(),
            location_city=address.get("city"),
            location_region=address.get("region"),
            job_type=job.get("tenure"),
            job_level=self._map_work_experience_to_level(job),
            category=job.get("function"),
            description_raw=description,
            qualifications_raw=job.get("qualifications"),
            is_active=job.get("active"),
            posted_at=self._parse_datetime(job.get("createdAt")),
            updated_at_source=self._parse_datetime(job.get("updatedAt")),
            deadline_at=self._parse_datetime(job.get("applicationEndDate")),
            source_native_id=job.get("id"),
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            work_arrangement=None,
            skill_tags=None,
            education_level=None,
            experience_years_min=None,
            benefits_raw=None,
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _map_work_experience_to_level(self, job: dict) -> str | None:
        # Kalibrr tidak selalu punya field "job level" eksplisit yang rapi di
        # JSON ini — untuk sekarang ambil dari URL kategori yang sudah pasti
        # ada di listing magang (LISTING_PATH). Disempurnakan nanti kalau
        # menambah kategori selain magang.
        return "Internship / OJT"

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None