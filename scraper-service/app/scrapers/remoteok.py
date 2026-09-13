import html
import time
from datetime import datetime

import httpx
from selectolax.parser import HTMLParser

from app.config import USER_AGENT, DEFAULT_REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS
from app.models.job_listing import ScrapedJobListing
from app.scrapers.base import ScraperBase


class RemoteOKScraper(ScraperBase):
    site_name = "remoteok"

    FEED_URL = "https://remoteok.com/remote-jobs.json"

    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        # Cache entri feed per source_url supaya scrape_listing() tidak perlu
        # fetch ulang HTML kalau URL-nya baru saja ditemukan lewat discovery —
        # feed sudah berisi data lengkap, HTML detail cuma dipakai sebagai
        # fallback untuk URL yang tidak ada di feed (lihat scrape_listing).
        self._feed_by_url: dict[str, dict] = {}

    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        # RemoteOK tidak punya konsep halaman/pagination untuk feed ini — selalu
        # mengembalikan ~100 listing terbaru dalam satu response. Parameter
        # max_pages diabaikan, dipertahankan cuma untuk memenuhi kontrak ScraperBase.
        response = self._client.get(self.FEED_URL)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            return []

        try:
            entries = response.json()
        except ValueError:
            return []

        # Entri pertama array selalu metadata ("legend"), bukan job — lewati.
        urls: list[str] = []
        for entry in entries[1:]:
            url = entry.get("url")
            if not url:
                continue
            self._feed_by_url[url] = entry
            urls.append(url)

        return urls

    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        entry = self._feed_by_url.get(url)
        if entry is not None:
            return self._map_feed_entry(entry, source_url=url)

        # URL tidak ada di feed (mis. scrape_listing dipanggil sendiri tanpa
        # discover_listing_urls dulu, atau untuk recheck listing lama yang
        # sudah keluar dari 100-terbaru) — fallback ke fetch halaman detail
        # langsung. Kalibrr/Glints/dst punya __NEXT_DATA__ untuk kasus ini;
        # RemoteOK tidak, jadi fallback di sini cuma og:meta tag (lihat
        # docs/scraper-research-findings.md bagian RemoteOK).
        return self._fetch_and_map_detail_page(url)

    def _map_feed_entry(self, entry: dict, source_url: str) -> ScrapedJobListing | None:
        title = entry.get("position")
        description = entry.get("description")
        if not title or not description:
            return None

        salary_min = entry.get("salary_min") or None
        salary_max = entry.get("salary_max") or None

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=source_url,
            title=title.strip(),
            company_name=(entry.get("company") or "Unknown").strip(),
            location_city=None,
            location_region=None,
            job_type=None,
            job_level=None,
            category=None,
            # Feed RemoteOK tidak konsisten: sebagian entry punya HTML mentah
            # (<p>...), sebagian lagi HTML yang di-escape sebagai entity teks
            # (&lt;p&gt;...) — unescape supaya description_raw selalu HTML asli,
            # bukan campuran dua format. Aman dipanggil dua kali (no-op kalau
            # sudah HTML asli, tidak ada &...; untuk di-decode).
            description_raw=html.unescape(description),
            qualifications_raw=None,
            is_active=True,  # ada di feed 100-terbaru = masih aktif
            posted_at=self._parse_datetime(entry.get("date")),
            updated_at_source=None,
            deadline_at=None,
            source_native_id=entry.get("id"),
            salary_min=salary_min,
            salary_max=salary_max,
            # RemoteOK tidak punya field currency eksplisit di feed, tapi platform ini
            # menormalkan semua salary ke USD tahunan secara konsisten (konvensi situs,
            # bukan asumsi kosong) — hanya diisi kalau memang ada angka salary.
            salary_currency="USD" if (salary_min or salary_max) else None,
            # RemoteOK 100% remote-only by design (nama situsnya sendiri) — bukan
            # inferensi per-listing seperti Kalibrr hardcode job_level dari kategori URL.
            work_arrangement="remote",
            skill_tags=entry.get("tags") or None,
            education_level=None,
            experience_years_min=None,
            benefits_raw=None,
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _fetch_and_map_detail_page(self, url: str) -> ScrapedJobListing | None:
        response = self._client.get(url)
        time.sleep(DEFAULT_REQUEST_DELAY_SECONDS)

        if response.status_code == 404:
            # Terverifikasi lewat riset: listing yang sudah hilang/expired
            # mengembalikan 404, bukan redirect atau halaman "closed".
            return None
        if response.status_code != 200:
            return None

        tree = HTMLParser(response.text)
        title_node = tree.css_first("meta[property='og:title']")
        description_node = tree.css_first("meta[property='og:description']")
        title = title_node.attributes.get("content") if title_node else None
        description = description_node.attributes.get("content") if description_node else None
        if not title or not description:
            return None

        return ScrapedJobListing(
            source_site=self.site_name,
            source_url=url,
            title=title.strip(),
            company_name="Unknown",
            location_city=None,
            location_region=None,
            job_type=None,
            job_level=None,
            category=None,
            description_raw=description,
            qualifications_raw=None,
            # Halaman masih bisa diakses (200) tapi listing ini di luar feed
            # 100-terbaru — tidak bisa dipastikan masih aktif atau tidak dari
            # og:meta saja, jangan menebak True.
            is_active=None,
            posted_at=None,
            updated_at_source=None,
            deadline_at=None,
            source_native_id=None,
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            work_arrangement="remote",
            skill_tags=None,
            education_level=None,
            experience_years_min=None,
            benefits_raw=None,
            gender_requirement_raw=None,
            max_age_raw=None,
            scraped_at=datetime.utcnow(),
        )

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
