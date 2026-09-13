# unemployed-fear — Setup Infrastruktur

> Bagian ini KHUSUS setup/instalasi environment. Belum ada logic development di sini — itu ada di file step-by-step development (menyusul di request berikutnya).
> Project ini dikerjakan **lebih dulu** dibanding project bigbrain (memory MCP server).
> Nama project: **unemployed-fear**, code `0004` (0003 = Bloomday). Dipakai apa adanya (tanpa singkatan terpisah) untuk folder, database, dan nama service.
> Setiap langkah ditandai **[LAPTOP]** (dikerjakan di komputer development kamu) atau **[VPS]** (dikerjakan via SSH di Cloudbread).

## 0. Sebelum Mulai — Checklist

- [ ] **[LAPTOP]** Repo git untuk project ini sudah/akan dibuat (lokal dulu, push nanti setelah ada isi)
- [ ] **[VPS]** Akses SSH ke Cloudbread sudah siap
- [ ] Nama & code project final: **unemployed-fear**, code `0004`
- [ ] Sadar RAM VPS saat ini 956Mi — strategi hemat RAM dipakai dulu sebagai default, upgrade ke 2-4GB jadi opsi kalau kurang (lihat bagian 6 file overview)

## ⚠️ Catatan Penting: Yang Disesuaikan dari Rencana Awal

- **PostgreSQL + pgvector SUDAH terpasang di VPS** (PostgreSQL 18, pgvector 0.8.1, paket `postgresql-18-pgvector`). Di VPS, cukup buat database & user baru — tidak install ulang.
- **Pola deploy Laravel: tetap pakai symlink**, konsisten dengan pola project static-build sebelumnya (0001/0002) — bedanya target symlink adalah folder `public/` Laravel (bukan `dist/` hasil build, karena Laravel tidak punya build step yang menghasilkan folder tunggal seperti itu). Root Nginx tetap tidak pernah menunjuk langsung ke source project mentah.
- **DNS Cloudflare: boleh mulai DNS-only dulu** untuk subdomain project ini, ikuti pola debug awal seperti md-2-discord, baru dipindah ke Proxied setelah dikonfirmasi jalan normal.
- **Process manager: systemd** (bukan Supervisor) — dipakai untuk mengelola Python/FastAPI service dan Laravel queue worker, konsisten dengan Nginx/PostgreSQL/Redis yang sudah dikelola systemd di VPS ini. Ini keputusan yang berlaku terlepas dari RAM VPS ke depannya.
- **RAM 956Mi** — strategi hemat resource (concurrency Chromium dibatasi) tetap default, upgrade paket VPS jadi opsi cadangan kalau di praktik ternyata kurang.
- **Hasil cek dependency VPS (langkah 4): hanya Python 3.14.4 yang sudah terpasang** — PHP, Composer, dan Redis semuanya belum ada, perlu diinstall dari nol (lihat langkah 4a-4d).
- **Python 3.14 sangat baru** — beberapa library yang dipakai perlu versi minimum tertentu supaya kompatibel: `psycopg2-binary` baru dapat dukungan resmi Python 3.14 di versi **2.9.11+** (dirilis untuk itu). Wajib pin versi ini secara eksplisit, jangan biarkan resolver auto-pilih versi lama yang bisa gagal build dari source di 3.14.
- **Package manager Python: `uv`** (bukan `venv`+`pip` manual) — jauh lebih cepat untuk resolve & install dependency (relevan karena stack ini lumayan banyak dependency: Playwright, google-generativeai, dst), sekaligus punya database kompatibilitas package yang lebih up-to-date untuk Python versi baru seperti 3.14.

## 1. [LAPTOP] Struktur Folder Project (Development Lokal)

Project ini dikembangkan di laptop dulu, baru di-push ke VPS lewat git (pola yang sama seperti 0001/0002) — bukan dikerjakan langsung di VPS.

```bash
mkdir unemployed-fear
cd unemployed-fear
mkdir dashboard scraper-service
git init
```

`.gitignore` di root:

```
dashboard/vendor/
dashboard/node_modules/
dashboard/.env
scraper-service/.venv/
scraper-service/.env
scraper-service/__pycache__/
*.log
```

## 2. [LAPTOP] Inisialisasi Laravel (Dashboard)

```bash
cd unemployed-fear
composer create-project laravel/laravel dashboard
cd dashboard
composer require livewire/livewire
```

`.env` lokal untuk development di laptop — koneksi database lokal dulu (misal Postgres lokal di laptop, atau SQLite untuk development cepat), **bukan kredensial VPS**. Kredensial VPS diisi terpisah nanti langsung di VPS (lihat langkah 8), tidak pernah di-commit ke git.

## 3. [LAPTOP] Inisialisasi Python Scraper/AI Service

Install `uv` dulu kalau belum ada (sekali saja per mesin):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # Windows: lihat astral.sh/uv untuk installer PowerShell
```

```bash
cd unemployed-fear/scraper-service
uv init --no-workspace
uv add "psycopg2-binary>=2.9.11" fastapi "uvicorn[standard]" playwright litellm google-generativeai redis pytesseract pillow
uv run playwright install --with-deps chromium
```

> `uv` otomatis membuat virtual environment (`.venv/`) dan file `pyproject.toml` + `uv.lock` untuk mengunci versi dependency — ini menggantikan peran `requirements.txt` dari `pip` biasa. Tidak perlu `python3 -m venv` atau `pip install` manual lagi.
> `uv` juga bisa kelola versi Python itu sendiri kalau perlu (`uv python install 3.14`), tapi kalau laptop kamu sudah punya Python terpasang, `uv` otomatis mendeteksi dan memakainya.
> Jangan bawa `pyproject.toml`/`uv.lock` dari laptop untuk dipakai apa adanya di VPS kalau versi Python berbeda — `uv` akan re-resolve otomatis saat `uv sync` dijalankan di VPS (lihat langkah 9), jadi ini sebenarnya lebih aman dibanding era `pip freeze` manual.

`.env` lokal (API key Gemini bisa dipakai yang sama untuk development, atau buat key terpisah kalau mau pisahkan quota dev vs production):

```env
GEMINI_API_KEY=isi_dengan_api_key_dari_ai.google.dev
DATABASE_URL=postgresql://user_lokal:password_lokal@127.0.0.1:5432/nama_db_lokal
REDIS_URL=redis://127.0.0.1:6379
```

Kalau di laptop belum ada Postgres+pgvector untuk development lokal, bisa install versi lokal (di luar scope dokumen ini, tergantung OS laptop kamu) — atau develop langsung terhubung ke VPS lewat SSH tunnel setelah bagian VPS di bawah selesai (opsional, lebih advanced).

## 4. [VPS] Cek & Install Dependency yang Belum Ada

Hasil cek aktual di VPS Cloudbread: **hanya Python 3.14.4 yang sudah terpasang.** PHP, Composer, dan Redis semuanya perlu diinstall dari nol — ini beda dari asumsi awal (dikira PHP sudah ada dari project 0001/0002, ternyata belum, karena project sebelumnya static-build yang tidak butuh PHP runtime di server).

### 4a. Install PHP + ekstensi yang dibutuhkan Laravel

```bash
sudo apt update
sudo apt install -y php-fpm php-cli php-pgsql php-mbstring php-xml php-curl php-zip php-bcmath
php -v
```

### 4b. Install Composer

```bash
curl -sS https://getcomposer.org/installer | php
sudo mv composer.phar /usr/local/bin/composer
composer -V
```

### 4c. Install Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
```

**Cara cek Redis cuma bisa diakses dari localhost (2 metode, keduanya sebaiknya dilakukan):**

**Metode 1 — cek isi file config** (memastikan directive `bind` sudah benar tertulis):
```bash
grep "^bind" /etc/redis/redis.conf
```
Harus muncul baris seperti `bind 127.0.0.1 -::1` (biasanya sudah default begini). Kalau `grep` tidak mengembalikan apa-apa, berarti baris `bind` tidak aktif (ke-comment atau tidak ada) — edit manual (`sudo nano /etc/redis/redis.conf`) untuk menambahkan baris itu, lalu `sudo systemctl restart redis-server`.

**Metode 2 — cek port yang benar-benar sedang didengarkan** (lebih pasti, karena mengecek kondisi aktual yang berjalan, bukan cuma isi file):
```bash
sudo ss -tlnp | grep redis
```
Harus muncul `127.0.0.1:6379` — kalau yang muncul `0.0.0.0:6379` atau `*:6379`, berarti Redis bisa diakses dari luar VPS (belum aman), meski file config sudah benar (biasanya artinya service belum di-restart setelah edit, atau ada config lain yang menimpa).

### 4d. Python — sudah ada (3.14.4), tinggal install `uv`

```bash
python3 --version
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

> **Catatan penting soal Python 3.14:** ini rilis yang sangat baru, dan tidak semua library punya wheel/binary yang matang untuknya. Yang paling krusial: `psycopg2-binary` baru resmi mendukung Python 3.14 mulai **versi 2.9.11**. `uv` akan resolve versi yang kompatibel secara otomatis asal kita pin batas minimumnya (`psycopg2-binary>=2.9.11`) — lihat langkah 9.
> Library lain (`fastapi`, `uvicorn`, `litellm`, `google-generativeai`, `pillow`, `pytesseract`) umumnya lebih cepat menyusul dukungan versi Python baru, tapi tetap perhatikan kalau ada error saat instalasi di langkah 9 — kemungkinan besar isunya sama (versi kurang baru).

## 5. [VPS] Database — Buat DB & User Baru (pgvector Sudah Terpasang)

Tidak perlu install PostgreSQL/pgvector ulang — cukup buat database & role baru mengikuti pola `<project>_app` / `<project>`.

Generate password 32 karakter:

```bash
openssl rand -base64 32
```

```bash
sudo -u postgres psql
```

```sql
CREATE ROLE unemployed_fear_app WITH LOGIN PASSWORD 'TEMPEL_PASSWORD_32_KARAKTER';
CREATE DATABASE unemployed_fear OWNER unemployed_fear_app;
REVOKE ALL ON DATABASE unemployed_fear FROM PUBLIC;
GRANT CONNECT ON DATABASE unemployed_fear TO unemployed_fear_app;
\c unemployed_fear
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

> Catatan: nama role/database pakai underscore (`unemployed_fear_app`) karena PostgreSQL tidak menerima dash (`-`) tanpa quoting berulang — beda dari nama folder yang boleh pakai dash.

Verifikasi:

```bash
sudo -u postgres psql -d unemployed_fear -c "\dx"
```

## 6. [VPS] Verifikasi Redis (Sudah Diinstall di Langkah 4c)

```bash
redis-cli ping
sudo ss -tlnp | grep redis
```

Pastikan hasil kedua command di atas seperti yang dijelaskan di langkah 4c (`PONG`, dan listen di `127.0.0.1:6379`) sebelum lanjut.

## 7. [VPS] Clone Project dari Git

```bash
cd ~/projects
git clone <url-repo-kamu> unemployed-fear
cd unemployed-fear
```

## 8. [VPS] Install Dependency & Konfigurasi Laravel

```bash
cd ~/projects/unemployed-fear/dashboard
composer install --no-dev --optimize-autoloader
```

Kalau ekstensi `pdo_pgsql` belum ada:
```bash
sudo apt install -y php-pgsql
sudo systemctl restart php*-fpm
```

Buat `.env` **langsung di VPS** (jangan copy dari laptop — isinya beda, ini kredensial production):

```env
DB_CONNECTION=pgsql
DB_HOST=127.0.0.1
DB_PORT=5432
DB_DATABASE=unemployed_fear
DB_USERNAME=unemployed_fear_app
DB_PASSWORD=TEMPEL_PASSWORD_32_KARAKTER

QUEUE_CONNECTION=redis
CACHE_STORE=redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
```

```bash
php artisan key:generate
php artisan migrate:status
```

## 9. [VPS] Install Dependency Python Service

Kalau folder `scraper-service` sudah punya `pyproject.toml`/`uv.lock` dari laptop (hasil git clone di langkah 7), `uv` tinggal sync ulang — resolvernya otomatis menyesuaikan ke Python 3.14.4 yang terpasang di VPS, tidak perlu regenerate manual:

```bash
cd ~/projects/unemployed-fear/scraper-service
uv sync
```

Kalau belum ada `pyproject.toml` (misal baru mulai dari VPS tanpa lewat laptop dulu), inisialisasi manual:

```bash
uv init --no-workspace
uv add "psycopg2-binary>=2.9.11" fastapi "uvicorn[standard]" playwright litellm google-generativeai redis pytesseract pillow
```

> Pin `psycopg2-binary>=2.9.11` tetap wajib eksplisit (lihat catatan di langkah 4d) — ini yang memastikan `uv` tidak mencoba resolve ke versi lama yang belum mendukung Python 3.14.

**Soal Playwright + RAM 956Mi:**

```bash
uv run playwright install --with-deps chromium
```

Chromium headless bisa makan 200-300MB+ RAM per instance. Dengan RAM 956Mi dan banyak service lain jalan bersamaan (Laravel-FPM, PostgreSQL, Redis), strategi default:
- Batasi concurrency scraper job ke 1 instance Chromium aktif dalam satu waktu (bukan paralel per-situs)
- Prioritaskan scraper berbasis HTTP request biasa untuk situs yang tidak butuh JS rendering; Chromium/Playwright hanya untuk situs yang benar-benar butuh itu
- Pantau `free -h` dan `swapon --show` selama scrape run pertama kali
- **Kalau setelah dicoba ternyata tetap kekurangan RAM secara konsisten** (bukan cuma sesekali spike), upgrade paket VPS ke 2GB atau 4GB adalah opsi yang sudah dipertimbangkan dan disetujui sebagai langkah lanjutan — bukan berarti arsitektur project ini salah

```bash
sudo apt install -y tesseract-ocr
```

`.env` production di VPS (terpisah dari `.env` laptop, jangan di-commit):

```env
GEMINI_API_KEY=isi_dengan_api_key_dari_ai.google.dev
DATABASE_URL=postgresql://unemployed_fear_app:TEMPEL_PASSWORD_32_KARAKTER@127.0.0.1:5432/unemployed_fear
REDIS_URL=redis://127.0.0.1:6379
```

## 10. [VPS] Symlink Public Folder (Pola Deploy Konsisten)

Sesuai keputusan: tetap pakai symlink seperti project static-build sebelumnya, target-nya folder `public/` Laravel.

```bash
sudo mkdir -p /var/www/apps
sudo ln -s /home/poeding/projects/unemployed-fear/dashboard/public /var/www/apps/unemployed-fear
```

Root Nginx nanti menunjuk ke `/var/www/apps/unemployed-fear` (symlink ini), bukan langsung ke folder project mentah.

> Catatan teknis: karena PHP tetap butuh mengakses file di luar `public/` (routes, `.env`, `vendor/`, dst) saat memproses request, `fastcgi_pass` di Nginx config nanti tetap perlu path lengkap ke file PHP yang benar (lihat langkah 12) — symlink ini menyelesaikan bagian "root/document root", bukan seluruh working directory PHP-FPM.

## 11. [VPS] Setup systemd untuk Python Service

Buat unit file:

```bash
sudo nano /etc/systemd/system/unemployed-fear-scraper.service
```

Isi:

```ini
[Unit]
Description=unemployed-fear scraper/AI service (FastAPI)
After=network.target redis-server.service postgresql.service

[Service]
Type=simple
User=poeding
WorkingDirectory=/home/poeding/projects/unemployed-fear/scraper-service
ExecStart=/home/poeding/.local/bin/uv run uvicorn main:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> Path `uv` di atas (`/home/poeding/.local/bin/uv`) adalah lokasi default installer `uv`. Cek lokasi sebenarnya dengan `which uv` setelah instalasi di langkah 4d, sesuaikan kalau berbeda. `uv run` otomatis menjalankan command di dalam virtual environment `.venv/` project tanpa perlu `activate` manual — cocok untuk dipanggil systemd yang tidak punya shell interaktif.

Aktifkan (penuh setelah `main.py` ada di tahap development):

```bash
sudo systemctl daemon-reload
sudo systemctl enable unemployed-fear-scraper
sudo systemctl start unemployed-fear-scraper
sudo systemctl status unemployed-fear-scraper
```

Cek log kalau ada masalah:
```bash
journalctl -u unemployed-fear-scraper -f
```

## 12. [VPS] Setup systemd untuk Laravel Queue Worker

```bash
sudo nano /etc/systemd/system/unemployed-fear-queue.service
```

```ini
[Unit]
Description=unemployed-fear Laravel queue worker
After=network.target redis-server.service postgresql.service

[Service]
Type=simple
User=poeding
WorkingDirectory=/home/poeding/projects/unemployed-fear/dashboard
ExecStart=/usr/bin/php artisan queue:work --sleep=3 --tries=3
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable unemployed-fear-queue
sudo systemctl start unemployed-fear-queue
```

> Kedua unit file di atas baru benar-benar jalan tanpa error setelah kode aplikasi (main.py, route Laravel) sudah ada — di tahap setup ini cukup disiapkan, `systemctl start` boleh ditunda ke tahap development kalau mau menghindari log error yang belum relevan.

## 13. [VPS] Nginx — Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/unemployed-fear.conf
```

> Nama subdomain masih draft — ganti sesuai keputusan final (lihat bagian 5 file overview).

```nginx
server {
    listen 80;
    server_name unemployed-fear.poedinglabs.fyi;
    root /var/www/apps/unemployed-fear;
    index index.php;

    include snippets/security-headers.conf;
    limit_req zone=general_limit burst=20 nodelay;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php-fpm.sock; # sesuaikan dengan socket PHP-FPM yang benar-benar terpasang, cek: ls /run/php/
    }

    location ~ /\.(?!well-known).* {
        deny all;
    }
}
```

> Blok di atas sengaja **belum pakai HTTPS/443** dulu — konsisten dengan keputusan DNS-only untuk debug awal. Blok 443 + include `ssl-params.conf` + `ssl_certificate` (pakai wildcard cert yang sudah ada di `/etc/letsencrypt/live/poedinglabs.fyi/`) ditambahkan setelah subdomain dikonfirmasi jalan normal di HTTP, sebelum dipindah ke Proxied.

```bash
sudo ln -s /etc/nginx/sites-available/unemployed-fear.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 14. Cloudflare DNS — Mulai DNS-Only

Tambahkan DNS record untuk subdomain project ini sebagai **DNS only** (awan abu-abu, bukan proxied) — sesuai keputusan, ikuti pola debug awal seperti md-2-discord. Pindah ke Proxied nanti setelah dikonfirmasi jalan normal (baru saat itu tambahkan blok 443 + TLS di Nginx menggunakan wildcard cert yang sudah ada).

## 15. [VPS] Baseline RAM Sebelum Development

```bash
free -h
swapon --show
```

Catat angkanya sebagai baseline pembanding nanti setelah semua service jalan bersamaan saat development/testing scraper.

## Checklist Akhir Setup

- [ ] **[LAPTOP]** Struktur folder + git init + Laravel + Livewire + `uv` + Python project tersiapkan
- [ ] **[VPS]** PHP + ekstensi (`pdo_pgsql` dst), Composer, Redis diinstall dari nol (belum ada sebelumnya di VPS ini)
- [ ] **[VPS]** Redis terverifikasi cuma listen di `127.0.0.1:6379` (dicek dengan `grep "^bind"` dan `ss -tlnp`)
- [ ] **[VPS]** `uv` terinstall (`uv --version`)
- [ ] **[VPS]** Database `unemployed_fear` + role `unemployed_fear_app` dibuat, ekstensi `vector` aktif
- [ ] **[VPS]** Project di-clone dari git, dependency Laravel & Python (`uv sync`) terpasang (psycopg2-binary dipin ≥2.9.11 untuk kompatibilitas Python 3.14.4), `.env` production diisi langsung di VPS
- [ ] **[VPS]** Tesseract terpasang
- [ ] Symlink `public/` → `/var/www/apps/unemployed-fear` dibuat
- [ ] Unit file systemd untuk Python service & Laravel queue worker disiapkan
- [ ] Nginx config dibuat (HTTP dulu, belum HTTPS), `include` ke snippet global yang sudah ada
- [ ] DNS record Cloudflare dibuat sebagai DNS only
- [ ] Baseline RAM (`free -h`, `swapon --show`) dicatat sebelum development dimulai

Setelah semua checklist ini selesai, lanjut ke file step-by-step **development** (menyusul di request berikutnya) — mulai dari scraper engine.
