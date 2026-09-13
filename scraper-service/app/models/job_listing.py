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

    source_native_id: str | None   # ID/slug asli dari situs sumber (bukan source_url) —
                                    # dipakai job_listing_sources nanti untuk dedup yang
                                    # lebih stabil daripada cocok-cocokan URL
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None    # kode mata uang, contoh: "IDR", "USD" — None kalau
                                    # salary_min/salary_max juga None
    work_arrangement: str | None   # "onsite" | "remote" | "hybrid" | None (tidak diketahui).
                                    # Dipetakan per-situs dari sinyal terbaik yang tersedia:
                                    # field tri-state eksplisit (Glints, Kitalulus), boolean
                                    # eksplisit (loker.id: True->"remote", False->"onsite"),
                                    # atau hardcode kalau seluruh situs memang remote-only
                                    # (RemoteOK, We Work Remotely). None kalau situs sama
                                    # sekali tidak expose sinyal ini (jangan menebak).
    skill_tags: list[str] | None   # daftar skill/tools, dari field terstruktur situs sumber
                                    # (bukan hasil parsing NLP dari qualifications_raw)
    education_level: str | None    # syarat pendidikan minimum, apa adanya dari situs sumber
    experience_years_min: int | None
    benefits_raw: list[str] | None

    # Field sensitif dari Kitalulus (genderStr, maxAge) — DISPLAY-ONLY, apa adanya dari
    # situs sumber. JANGAN PERNAH dipakai untuk filtering, ranking, atau logic matching
    # apapun (di scraper ini maupun layer manapun setelahnya) — ini murni informasi yang
    # ditampilkan situs sumber, bukan kriteria yang boleh dipakai sistem untuk menyaring
    # atau mengurutkan hasil.
    gender_requirement_raw: str | None
    max_age_raw: int | None

    scraped_at: datetime = field(default_factory=datetime.utcnow)