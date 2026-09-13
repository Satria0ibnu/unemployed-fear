from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScrapedJobListing:
    """Hasil scrape mentah satu halaman loker dari satu sumber.
    Belum melalui proses dedup/merge — itu tanggung jawab data layer,
    bukan scraper.
    """

    source_site: str          # contoh: "kalibrr"
    source_url: str           # URL lengkap halaman loker
    title: str
    company_name: str
    location_city: str | None
    location_region: str | None
    job_type: str | None      # "tenure" di Kalibrr, contoh: "Contractual", "Full-time"
    job_level: str | None     # "Internship / OJT", dst — beda dari job_type
    category: str | None      # "function" di Kalibrr, contoh: "Human Resources"
    description_raw: str      # HTML deskripsi mentah, belum diringkas AI
    qualifications_raw: str | None  # HTML kualifikasi mentah, kalau ada
    is_active: bool | None    # status loker langsung dari sumber (True=masih buka, False=expired)
    posted_at: datetime | None    # tanggal asli posting, dari createdAt situs
    updated_at_source: datetime | None  # kapan situs sumber terakhir update listing ini
    deadline_at: datetime | None  # applicationEndDate, kalau ada
    scraped_at: datetime = field(default_factory=datetime.utcnow)