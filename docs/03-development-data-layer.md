# unemployed-fear — Development 2: Data Layer (Revisi: 6 Situs)

> Melanjutkan dari `02-development-scraper-engine.md` — asumsi 7 scraper
> (Kalibrr, RemoteOK, We Work Remotely, loker.id, Glints, Wellfound, Kitalulus)
> sudah tervalidasi lokal di laptop lewat endpoint tes masing-masing.
> Fase ini: skema tabel `job_postings` + `job_listing_sources` yang menampung
> field dari SEMUA situs (bukan cuma Kalibrr), migrasi Laravel sebagai pemilik
> skema, dan fungsi simpan hasil scrape dari sisi Python.
> Semua langkah ditandai **[LAPTOP]** atau **[VPS]**.
> ⚠️ Ini revisi dari draf awal yang cuma berdasarkan Kalibrr. Skema di bawah
> sudah memasukkan 12 field baru hasil riset + implementasi 6 situs tambahan
> (lihat `docs/scraper-research-findings.md` dan ringkasan implementasi Claude
> Code untuk detail asal tiap field).

## 0. Prinsip Pembagian Tanggung Jawab

- **Laravel (`dashboard/`) = pemilik skema.** Migrasi Laravel yang membuat/mengubah struktur tabel. Python **tidak pernah** menjalankan `CREATE TABLE`/`ALTER TABLE` — hanya `INSERT`/`SELECT`/`UPDATE` lewat koneksi database yang sudah ada.
- Konsekuensi praktis: kalau field baru dibutuhkan Python, **tambahkan dulu migrasi di Laravel**, baru Python mulai menulis ke kolom itu.

## 1. [LAPTOP] Migrasi: `job_postings`

```bash
cd unemployed-fear/dashboard
php artisan make:migration create_job_postings_table
```

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('job_postings', function (Blueprint $table) {
            $table->id();

            // --- Field inti, sudah ada sejak draf Kalibrr ---
            $table->string('title');
            $table->string('company_name');
            $table->string('location_city')->nullable();
            $table->string('location_region')->nullable();
            $table->string('job_type')->nullable();   // "Contractual", "Full-time", "TELECOMMUTE", dst — istilah beda-beda per situs
            $table->string('job_level')->nullable();  // hampir selalu nullable — TIDAK ada satupun dari 7 situs yang punya field level eksplisit bersih
            $table->string('category')->nullable();   // string bebas apa adanya per-source; normalisasi ke kategori standar adalah tugas AI Layer, BUKAN di sini
            $table->text('description')->nullable();  // hasil merge/pilihan terbaik dari semua sumber
            $table->text('qualifications')->nullable();
            $table->timestamp('posted_at')->nullable();
            $table->timestamp('deadline_at')->nullable();  // sering kosong (WWR/Wellfound/loker.id) — tetap nullable
            $table->timestamp('updated_at_source')->nullable();
            $table->enum('status', ['active', 'possibly_expired', 'expired'])->default('active');

            // --- Field baru dari riset 6-situs ---
            $table->unsignedBigInteger('salary_min')->nullable();
            $table->unsignedBigInteger('salary_max')->nullable();
            $table->string('salary_currency', 10)->nullable();
            $table->enum('work_arrangement', ['onsite', 'remote', 'hybrid'])->nullable();
            $table->json('skill_tags')->nullable();          // list string, dari Glints/RemoteOK/Kitalulus
            $table->string('education_level')->nullable();   // dari Glints/Kitalulus
            $table->unsignedSmallInteger('experience_years_min')->nullable();
            $table->text('benefits_raw')->nullable();         // dari Glints/Wellfound, disimpan apa adanya (belum dinormalisasi)

            // --- Field sensitif: DISPLAY-ONLY, tidak boleh dipakai filter/ranking ---
            // Ditemukan eksplisit di Kalibrr dan Glints (gender, min/maxAge).
            // JANGAN buat index di kolom ini, dan JANGAN referensikan di query
            // WHERE/ORDER BY manapun di fase Matching nanti — lihat catatan di
            // bawah tabel ini.
            $table->string('gender_requirement_raw')->nullable();
            $table->string('max_age_raw')->nullable();

            // Embedding untuk semantic similarity search (dedup & matching).
            $table->vector('embedding', dimensions: 768)->nullable();
            $table->timestamps();

            $table->index('status');
            $table->index('job_type');
            $table->index('work_arrangement');
        });

        DB::statement('CREATE INDEX job_postings_embedding_idx ON job_postings USING hnsw (embedding vector_cosine_ops)');
    }

    public function down(): void
    {
        Schema::dropIfExists('job_postings');
    }
};
```

> **`gender_requirement_raw` dan `max_age_raw` — PERINGATAN KERAS, bukan sekadar catatan.**
> Field ini WAJIB tetap read-only/display-only selamanya, sesuai keputusan yang sudah
> diambil sebelum implementasi scraper dimulai. Larangan ini berlaku untuk SEMUA kode
> yang ditulis setelah ini — fase Matching, Dashboard, API publik, apapun. Kalau nanti
> ada kebutuhan filter/sort yang "kebetulan" ingin memakai field ini, itu harus jadi
> diskusi produk eksplisit dulu, bukan diam-diam ditambahkan ke query karena kelihatan
> praktis.
> **`experience_years_min`** cuma representasi minimum — laporan implementasi mencatat
> Wellfound kadang mengirim `experienceRequirements` sebagai string bebas (bukan angka
> bersih); kalau parsing situs tertentu gagal mengekstrak angka, biarkan `null`, jangan
> dipaksakan tebak angka dari teks.
> **`work_arrangement`** dipilih sebagai enum tunggal (bukan boolean `is_remote`)
> supaya bisa merepresentasikan hybrid juga.

## 2. [LAPTOP] Migrasi: `job_listing_sources`

```bash
php artisan make:migration create_job_listing_sources_table
```

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('job_listing_sources', function (Blueprint $table) {
            $table->id();
            $table->foreignId('job_posting_id')->constrained()->cascadeOnDelete();
            $table->string('source_site');   // "kalibrr", "glints", "remoteok", "weworkremotely", "lokerid", "wellfound", "kitalulus"
            $table->string('source_url')->unique();
            $table->string('source_native_id')->nullable();  // ID/slug asli dari situs sumber — lebih stabil untuk dedup daripada cocok-cocokan URL
            $table->text('raw_description')->nullable();
            $table->boolean('source_reported_active')->nullable();
            $table->timestamp('scraped_at');
            $table->timestamp('last_checked_at');
            $table->unsignedSmallInteger('check_attempts')->default(0);
            $table->enum('status', ['active', 'possibly_expired', 'expired'])->default('active');
            $table->timestamps();

            $table->index(['source_site', 'status']);
            $table->index('last_checked_at');
            $table->index('source_native_id');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('job_listing_sources');
    }
};
```

> `source_native_id` ditambahkan di sini (bukan di `job_postings`) sesuai
> rekomendasi laporan riset — ini atribut "kemunculan di satu sumber", bukan
> atribut job itu sendiri.
> `source_reported_active` — perlu diingat: sitemap Kitalulus ternyata didominasi
> listing `isClosed: true` (5 dari 5 sample) — jangan berasumsi kemunculan di
> sitemap berarti aktif untuk situs ini khususnya.

## 3. [LAPTOP] Install Package `pgvector` untuk Laravel

```bash
composer require pgvector/pgvector
php artisan migrate
```

> Ini jalan ke database `.env` **laptop** (lokal). Migrasi ke VPS terpisah di langkah 9.

## 4. [LAPTOP] Eloquent Model: `JobPosting` & `JobListingSource`

```bash
php artisan make:model JobPosting
php artisan make:model JobListingSource
```

`app/Models/JobPosting.php`:

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Pgvector\Laravel\Vector;
use Pgvector\Laravel\HasNeighbors;

class JobPosting extends Model
{
    use HasNeighbors;

    protected $fillable = [
        'title', 'company_name', 'location_city', 'location_region',
        'job_type', 'job_level', 'category', 'description', 'qualifications',
        'posted_at', 'deadline_at', 'updated_at_source', 'status',
        'salary_min', 'salary_max', 'salary_currency', 'work_arrangement',
        'skill_tags', 'education_level', 'experience_years_min', 'benefits_raw',
        'gender_requirement_raw', 'max_age_raw', 'embedding',
    ];

    protected $casts = [
        'posted_at' => 'datetime',
        'deadline_at' => 'datetime',
        'updated_at_source' => 'datetime',
        'skill_tags' => 'array',
        'embedding' => Vector::class,
    ];

    public function sources(): HasMany
    {
        return $this->hasMany(JobListingSource::class);
    }

    /**
     * Sengaja TIDAK ada scope/accessor untuk filter berdasarkan
     * gender_requirement_raw atau max_age_raw. Field ini display-only —
     * lihat catatan di migrasi job_postings. Jangan tambahkan scope
     * seperti scopeMaxAge() atau scopeGender() ke model ini.
     */
}
```

`app/Models/JobListingSource.php`:

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class JobListingSource extends Model
{
    protected $fillable = [
        'job_posting_id', 'source_site', 'source_url', 'source_native_id',
        'raw_description', 'source_reported_active', 'scraped_at',
        'last_checked_at', 'check_attempts', 'status',
    ];

    protected $casts = [
        'scraped_at' => 'datetime',
        'last_checked_at' => 'datetime',
    ];

    public function jobPosting(): BelongsTo
    {
        return $this->belongsTo(JobPosting::class);
    }
}
```

## 5. [LAPTOP] Verifikasi `ScrapedJobListing` Sinkron dengan Skema

```bash
cd unemployed-fear/scraper-service
grep -A 30 "class ScrapedJobListing" app/models/job_listing.py
```

Field yang wajib ada (di luar field inti sejak Kalibrr): `salary_min`,
`salary_max`, `salary_currency`, `work_arrangement` (cek nama persisnya — kalau
Claude Code menamakannya beda, misal `is_remote` boolean, **sesuaikan salah satu
sisi**: ubah migrasi Laravel di atas atau kode Python, jangan biarkan dua sisi
berbeda nama/tipe untuk data yang sama), `skill_tags`, `education_level`,
`experience_years_min`, `benefits_raw`, `gender_requirement_raw`, `max_age_raw`,
`source_native_id`.

## 6. [LAPTOP] Fungsi Simpan dari Sisi Python

Taruh di file baru **`app/db/repository.py`** (bukan ditumpuk di `connection.py`).

```python
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
                    # skill_tags perlu di-serialize ke JSON string untuk kolom json —
                    # sesuaikan dengan cara psycopg2 kamu handle tipe list/JSON
                    listing.skill_tags,
                    listing.education_level, listing.experience_years_min,
                    listing.benefits_raw, listing.gender_requirement_raw,
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
```

> **Catatan penting soal `skill_tags` (JSON):** cara paling aman menulis list
> Python ke kolom `json` PostgreSQL lewat `psycopg2` adalah `json.dumps(listing.skill_tags)`
> sebelum masuk parameter query (atau pakai `psycopg2.extras.Json(...)`) — jangan
> kirim list Python mentah, `psycopg2` tidak otomatis serialize itu ke JSON.
> **Field baru yang bisa `None` untuk banyak situs** (`salary_min/max`, `skill_tags`,
> dst) — `INSERT` di atas tetap jalan normal dengan `None` (jadi `NULL`), karena
> semua kolom baru sudah `nullable()` di migrasi.
> `conn.commit()` dipanggil manual di tiap cabang supaya error di satu listing
> tidak ikut me-rollback listing lain yang sudah berhasil diproses sebelumnya.

## 7. [LAPTOP] Update `main.py` — Endpoint Tes Simpan ke Database

Fungsi `save_scraped_listing` generik, tapi cara memasang endpoint untuk ketujuh
situs (satu endpoint generik dengan parameter nama situs, atau tetap satu endpoint
per situs seperti pola `/test-scrape/kalibrr` yang sudah ada) **diserahkan ke
penilaian Claude Code saat implementasi** — sesuaikan dengan pola paling konsisten
dari endpoint yang sudah dibuat di fase scraper engine. Contoh minimal untuk satu
situs:

```python
from fastapi import FastAPI

from app.scrapers.kalibrr import KalibrrScraper
from app.db.repository import save_scraped_listing

app = FastAPI(title="unemployed-fear scraper service")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "unemployed-fear-scraper"}


@app.get("/test-scrape/kalibrr")
def test_scrape_kalibrr(limit: int = 3, save: bool = False):
    scraper = KalibrrScraper()
    urls = scraper.discover_listing_urls(max_pages=1)[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}
```

Ulangi pola yang sama (atau versi generiknya) untuk keenam situs lain.

## 8. [LAPTOP] Uji Coba Lokal

```bash
cd unemployed-fear/scraper-service
uv run uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Uji **setiap** situs satu per satu:

```bash
curl "http://127.0.0.1:8001/test-scrape/kalibrr?limit=2&save=true"
curl "http://127.0.0.1:8001/test-scrape/glints?limit=2&save=true"
curl "http://127.0.0.1:8001/test-scrape/remoteok?limit=2&save=true"
curl "http://127.0.0.1:8001/test-scrape/weworkremotely?limit=2&save=true"
curl "http://127.0.0.1:8001/test-scrape/lokerid?limit=2&save=true"
curl "http://127.0.0.1:8001/test-scrape/wellfound?limit=2&save=true"
curl "http://127.0.0.1:8001/test-scrape/kitalulus?limit=2&save=true"
```

Verifikasi ke database (lokal):
```bash
psql -d <nama_db_lokal> -c "SELECT id, title, company_name, work_arrangement, salary_min, status FROM job_postings;"
psql -d <nama_db_lokal> -c "SELECT id, job_posting_id, source_site, source_native_id, status FROM job_listing_sources;"
```

Hal spesifik yang perlu dicek per situs (dari laporan implementasi kemarin):
- **Kitalulus**: sitemap didominasi `isClosed: true` — jangan kaget banyak row
  yang tersimpan seharusnya berstatus tidak aktif; pastikan `source_reported_active`
  terisi `false` untuk listing tertutup, bukan `null`/`true`.
- **Wellfound**: yield discovery cuma ~50% — jangan kaget `discovered` jauh lebih
  besar dari `scraped`.
- **`skill_tags`**: `SELECT skill_tags FROM job_postings WHERE skill_tags IS NOT NULL LIMIT 3;` — pastikan JSON array valid, bukan string mentah/error insert.

Jalankan lagi endpoint yang sama dengan `limit` sama — pastikan **tidak insert
dobel**, untuk tiap situs, bukan cuma Kalibrr.

## 9. [LAPTOP] Commit & Push, lalu [VPS] Deploy

**[LAPTOP]**
```bash
cd unemployed-fear
git add .
git commit -m "add job_postings & job_listing_sources schema for 7 sites, save logic"
git push
```

**[VPS]**
```bash
cd ~/projects/unemployed-fear
git pull
cd dashboard
composer install --no-dev --optimize-autoloader
php artisan migrate
```

> `php artisan migrate` di VPS akan minta konfirmasi karena `APP_ENV` production — jawab "yes" setelah yakin migrasi sudah teruji di laptop.

```bash
cd ../scraper-service
uv sync
sudo systemctl restart unemployed-fear-scraper
sudo systemctl status unemployed-fear-scraper
```

Verifikasi (beberapa situs, tidak perlu semua):
```bash
curl "http://127.0.0.1:8001/test-scrape/kalibrr?limit=1&save=true"
curl "http://127.0.0.1:8001/test-scrape/glints?limit=1&save=true"
sudo -u postgres psql -d unemployed_fear -c "SELECT title, company_name, work_arrangement FROM job_postings;"
```

Setelah data layer tervalidasi untuk ketujuh situs, lanjut ke file development
berikutnya: **Queue & Scheduling** — di titik ini juga jadi momen yang tepat
memikirkan strategi discovery Kitalulus ulang (mengingat temuan sitemap didominasi
listing tertutup), sebelum dijadwalkan jalan otomatis berkala.

## Checklist Fase Ini

- [ ] **[LAPTOP]** Migrasi `job_postings` (12 field baru) & `job_listing_sources` (`source_native_id`) berhasil `php artisan migrate` di database lokal
- [ ] **[LAPTOP]** Package `pgvector/pgvector` terpasang di Laravel
- [ ] **[LAPTOP]** Model `JobPosting` & `JobListingSource` dibuat, `$fillable` mencakup semua field baru
- [ ] **[LAPTOP]** Nama & tipe field di `ScrapedJobListing` (Python) dan migrasi Laravel dicocokkan
- [ ] **[LAPTOP]** `save_scraped_listing` di `app/db/repository.py`, berhasil dites untuk **ketujuh** situs
- [ ] **[LAPTOP]** Data terverifikasi manual lewat `psql` per situs — `skill_tags` valid JSON, field sensitif tidak dipakai di query manapun
- [ ] **[LAPTOP]** Idempotency diverifikasi untuk tiap situs
- [ ] **[LAPTOP]** Perubahan di-commit & di-push
- [ ] **[VPS]** Migrasi dijalankan ke production, dependency Python di-sync, service direstart dan diverifikasi
