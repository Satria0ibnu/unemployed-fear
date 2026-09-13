# unemployed-fear — Overview & Keputusan Project

> Project keempat di VPS Cloudbread. Code name: **0004** (0003 = Bloomday).
> Nama project: **unemployed-fear** — dipakai konsisten untuk folder, database, dan nama service (tidak pakai singkatan terpisah, nama ini sendiri sudah cukup singkat).
> Path VPS: `/home/poeding/projects/unemployed-fear`.

## 1. Tujuan Project

Web dashboard yang mengumpulkan lowongan kerja & magang dari banyak situs sumber, lalu mencocokkan hasilnya dengan kebutuhan spesifik user (free text, form, atau CV) — bukan sekadar list mentah, tapi hasil yang benar-benar relevan, transparan soal sumber & usia data, dan otomatis menjaga kesegaran data lewat recheck berkala.

Dipakai personal + teman-teman (bukan cuma untuk diri sendiri).

## 2. Keputusan Inti (Decision Log)

### Sumber & Scope
- Target: **banyak situs sekaligus dari awal**, bukan MVP 1-2 situs dulu.
- Sumber data masih perlu di-explore lebih lanjut (kandidat: job board resmi via API, portal loker lokal seperti Kalibrr/Glints, karir page perusahaan spesifik).
- Wajib cek `robots.txt` & ToS tiap situs sebelum masuk daftar scrape target. Rate limiting per situs + user-agent yang jujur/identifiable.

### Pola Scraping: Hybrid (bukan pilih salah satu)
- **Scrape harian/berkala** → base data pool, sumber utama isi dashboard & bahan matching.
- **On-demand** bukan berarti scrape real-time saat user cari — tapi **search/match on-demand** terhadap data yang sudah ada di database (embedding similarity).
- Data yang tidak ketemu match bagus bisa jadi sinyal untuk expand scope scraper nanti (best-effort, bukan real-time).

### Model Data: Pisahkan "Job" dan "Listing"
Untuk menangani kasus sumber berbeda tapi pekerjaan sama (dengan kelengkapan info berbeda):
- **`job_postings`** — entitas pekerjaan hasil merge (title kanonik, company, location, requirements gabungan, salary jika ada).
- **`job_listing_sources`** — one-to-many ke `job_postings`, satu row per kemunculan di satu situs sumber (source_url, source_site, scraped_at, raw_fields).
- Dedup pakai **semantic similarity (embedding)**, bukan exact-match hash, karena judul kerja sering ditulis beda meski posisi sama.
- Merge strategy per field: field kosong di kanonik diisi dari sumber manapun yang punya; field yang konflik (misal deskripsi) ambil versi paling lengkap, atau prioritas ke sumber yang lebih terpercaya (misal karir page resmi > agregator).
- Listing dianggap benar-benar hilang hanya jika **semua** source-nya expired — bukan begitu satu sumber hilang.

### Matching (Free Text / Form / CV)
- Semua jenis input (free text, form, CV) di-normalize ke structured profile → di-generate embedding-nya → dibandingkan (similarity search) ke embedding tiap `job_postings`.
- CV: OCR via Gemini vision (baca gambar/PDF langsung, sekaligus extract data terstruktur), dengan **Tesseract** sebagai fallback lokal gratis kalau Gemini gagal/limit.
- Hasil match idealnya disertai skor + alasan singkat ("kenapa cocok") — bukan cuma angka.

### CV Disimpan Permanen
- File CV asli disimpan (path/reference di DB, file di disk VPS) — bukan proses-lalu-buang.
- Hasil parsing (structured profile + embedding) disimpan terpisah dari file mentah: `cv_uploads` (file asli) vs `cv_parsed_profiles` (hasil ekstraksi).
- Karena PII dan multi-user: butuh `user_id` ownership dari awal skema (meski UI login/auth dibangun belakangan), user harus bisa hapus CV mereka sendiri kapan saja, dan versioning CV (simpan histori, tandai `is_active`).

### Transparansi Data
- Tiap hasil wajib menampilkan **link sumber** (`source_url`).
- Wajib jujur soal **kapan data discrape** (`scraped_at`), idealnya juga tanggal asli posting (`posted_at`) jika situs sumber menyediakan.

### Recheck Availability
- Threshold waktu (contoh: 1-2 bulan) — listing yang melewati threshold **wajib** direcheck.
- Kalau ditemukan lagi → update `last_checked_at`.
- Kalau tidak ditemukan → **jangan langsung hapus** (grace period + retry beberapa kali dulu, pakai `check_attempts`, untuk menghindari false-positive dari situs sumber yang sedang down). Baru dihapus/soft-delete kalau konsisten gagal.
- Karena model data dipisah job/listing: recheck dilakukan per **source**, job utuh baru dianggap hilang kalau semua source-nya expired.

### AI/LLM Layer
- AI dipakai di dua tempat utama:
  1. **Extraction** — raw HTML/text → structured JSON (title, company, location, salary, requirements), lebih tahan banting dibanding CSS selector yang mudah break.
  2. **Normalisasi & kategorisasi** — menyamakan istilah beda-beda antar situs (Remote/WFH, Magang/Internship/PKL) ke kategori standar.
- Model gratis, multi-layer fallback: **Gemini free tier sebagai utama**, fallback ke provider gratis lain kalau gagal/limit (rate limit, timeout, error).
- Orkestrasi fallback pakai **LiteLLM** (library gratis, open-source) — unify banyak provider di balik satu interface, built-in fallback routing.
- Rule-based (regex/exact-match) tetap dipakai untuk hal yang tidak butuh LLM: dedup exact-match, scheduling/orchestration, filter tanggal/lokasi terstruktur.
- Kesadaran biaya: free tier tetap rate-limited (RPM/TPM/RPD, reset harian tengah malam Pacific time) — bukan unlimited. Perlu throttling di scrape job supaya tidak habis quota harian dalam sekali run.

### Fitur Tambahan yang Disepakati Masuk Pertimbangan
- User feedback loop (relevan/tidak relevan) di tiap hasil match — data untuk improve matching nanti.
- Saved search / alert (notifikasi listing baru yang match, bisa reuse Discord webhook dari [[discord-greeting-bot]]).
- Explainability hasil match (bukan cuma skor, tapi alasan singkat).

## 3. Tech Stack Final (Semua Gratis untuk Mulai)

| Komponen | Pilihan | Alasan |
|---|---|---|
| Dashboard & orchestration | Laravel + Livewire | Ekosistem sudah dikuasai, satu bahasa dengan project lain, minim context-switching untuk frontend |
| Scraper & AI service | Python (FastAPI sebagai wrapper API internal), microservice terpisah | Ekosistem scraping lebih matang (Playwright/Scrapy untuk situs JS-heavy) + Python adalah bahasa dominan ekosistem AI/LLM — align dengan [[applied-ai-upskilling]] |
| Database | PostgreSQL + pgvector | Wajib untuk semantic similarity search (dedup, matching); reuse skill yang sama dengan [[memory-mcp-server]] |
| Queue/Cache | Redis | Throughput lebih baik dari database driver untuk scraping paralel banyak situs, plus cache embedding |
| LLM orchestration | LiteLLM (gratis) + Gemini API free tier | Fallback chain antar provider gratis |
| OCR fallback | Tesseract | Gratis, self-hosted, tanpa batas request, untuk kasus Gemini vision gagal/limit |
| Process manager | **systemd** (native, bukan Supervisor) | Sudah dipakai untuk Nginx/PostgreSQL/Redis di VPS ini — satu sistem manajemen proses yang konsisten untuk semua service, tanpa daemon tambahan yang makan RAM. Berlaku terlepas dari ukuran RAM VPS (lihat bagian 6) |
| Deployment | Native di VPS (bukan Docker) | Belum familiar Docker — dihindari dulu supaya tidak menambah beban belajar yang tidak esensial di fase awal |

Komunikasi Laravel ↔ Python service: REST API internal atau lewat queue Redis yang sama (Laravel dispatch job → Python service consume).

## 4. Urutan Prioritas Pembangunan (High-Level)

Berdasarkan diskusi, urutan MVP yang disarankan:

1. Scraper engine (interface seragam + registry situs)
2. Data layer (`job_postings` + `job_listing_sources`, dedup semantik)
3. Queue & scheduling
4. AI layer (extraction + embedding + fallback chain)
5. Matching (free text/form/CV → hasil relevan)
6. Dashboard (Livewire)
7. Recheck availability system
8. Monitoring & maintenance (log scrape run, alert kegagalan)
9. Auth (terakhir, sesuai keputusan user — tapi `user_id` ownership tetap disiapkan di skema sejak awal karena CV disimpan permanen)

## 5. Belum Diputuskan / Perlu Dibahas Lebih Lanjut

- Daftar final situs sumber yang akan di-scrape (masih explore).
- Detail retensi CV (berapa lama versi lama disimpan sebelum benar-benar dihapus, jika ada).
- Detail UI/UX form input matching (free text vs form terstruktur vs upload CV — apakah ketiganya opsi sejajar atau ada alur bertahap).
- Nama subdomain final untuk project ini (draft: `unemployed-fear.poedinglabs.fyi`, cukup panjang untuk subdomain — pertimbangkan alternatif lebih pendek kalau mau).

## 6. Prioritas & Constraint VPS

- Project ini dikerjakan **lebih dulu** dibanding project [[memory-mcp-server]] (bigbrain).
- VPS Cloudbread RAM saat ini **956Mi total**, dengan swap 2GB (vm.swappiness=10) sebagai pengaman level VPS. Upgrade ke 2GB atau 4GB **dipertimbangkan sebagai opsi** kalau ternyata RAM kurang di praktik — bukan diasumsikan dari awal. Strategi hemat RAM (lihat file setup) tetap jadi pendekatan default sampai terbukti perlu upgrade.
- Stack project ini (Laravel-FPM + Python/FastAPI + PostgreSQL + Redis + Playwright/Chromium untuk scraping JS-heavy) tergolong berat untuk RAM 956Mi — Chromium headless saja bisa makan 200-300MB+ per instance.
  - Implikasi: hindari menjalankan banyak instance Chromium/Playwright bersamaan; batasi concurrency scraper job di level queue.
  - Pantau pemakaian RAM aktual selama development, terutama saat scraper + AI layer jalan bersamaan dengan Laravel-FPM.
  - Kalau upgrade RAM terjadi nanti, batasan concurrency ini bisa dilonggarkan — tapi pilihan systemd sebagai process manager tetap tidak berubah (alasan pilihan itu soal konsistensi arsitektur, bukan soal hemat RAM semata).
- PostgreSQL 18 + ekstensi pgvector (versi 0.8.1, paket `postgresql-18-pgvector`) **sudah terpasang di level VPS** (bagian dari setup bigbrain sebelumnya) — bukan perlu install/build dari source lagi untuk project ini. Tuning `postgresql.conf` (max_connections, shared_buffers, work_mem, dst) juga sudah dilakukan di level VPS.
- Pola user/database PostgreSQL per-project yang berlaku: role `<project>_app`, database `<project>`, akses PUBLIC di-revoke, password 32 karakter dari generator.
