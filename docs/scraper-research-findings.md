# Riset Struktur Data Job Board — Temuan Pra-Data-Layer

> Riset saja, bukan implementasi. Tujuan: kumpulkan field yang tersedia dari beberapa
> situs job board selain Kalibrr, supaya skema `job_postings` + `job_listing_sources`
> dikunci berdasarkan data nyata, bukan cuma pas untuk Kalibrr. Semua fetch dilakukan
> dengan `User-Agent` jujur (`unemployed-fear-bot/0.1 (+https://unemployed-fear.poedinglabs.fyi/about)`,
> sama dengan `USER_AGENT` di `app/config.py`) dan jeda 3 detik antar-request ke domain
> yang sama (`DEFAULT_REQUEST_DELAY_SECONDS`). Tidak ada sample HTML/JSON mentah yang
> disimpan di repo ini — semua fetch sementara dibuang di luar git.

## Ringkasan

Dari **19 kandidat** yang dipertimbangkan, **7 lolos saringan robots.txt**. Dari 7 itu,
**6 berhasil diriset lengkap** dan **1 (Himalayas) diblokir infrastruktur anti-bot**
meski robots.txt-nya sendiri mengizinkan.

### Situs yang lolos & diriset

| Situs | Fokus | Status |
|---|---|---|
| [Glints](#glints-glintscom) | Indonesia, magang/entry-level | Data lengkap |
| [loker.id](#lokerid) | Indonesia, umum | Data lengkap |
| [We Work Remotely](#we-work-remotely-weworkremotelycom) | Remote global | Data lengkap |
| [Wellfound](#wellfound-wellfoundcom) | Remote global/startup | Data lengkap (dengan catatan) |
| [RemoteOK](#remoteok-remoteokcom) | Remote global | Data lengkap |
| [Kitalulus](#kitalulus-kitaluluscom) | Indonesia, entry-level/blue-collar | Data lengkap |
| Himalayas (himalayas.app) | Remote global/tech | **Diblokir Cloudflare** — lihat catatan di bawah |

### Situs yang dicoret — dan kenapa

**Karena robots.txt men-disallow path halaman detail loker** (sesuai aturan: langsung
dicoret, tidak diriset lebih lanjut):

| Situs | Bukti disallow |
|---|---|
| karir.com | `Disallow: /jobs/` dan `Disallow: /karir/` untuk `User-agent: *` |
| id.jobstreet.com (JobStreet Indonesia) | `Disallow: */job/` untuk `User-agent: *` — bahkan ada blok khusus `User-agent: anthropic-ai` yang juga eksplisit men-disallow `*/job/` |
| id.indeed.com | `Disallow: /job/`, `Disallow: /viewjob?`, `Disallow: /jobs/ID/` (path khusus Indonesia) |
| id.jora.com | `User-agent: *` → `Disallow: /` (blanket block untuk bot tak dikenal); bot bernama eksplisit pun tetap kena `Disallow: /view-job/`, `/job-search/` |

**Karena larangan otomasi eksplisit di luar Disallow path biasa** (tetap dicoret sesuai
keputusan project "cek robots.txt & ToS"):

| Situs | Alasan |
|---|---|
| www.linkedin.com | robots.txt-nya sendiri memuat notice: *"The use of robots or other automated means to access LinkedIn without the express permission of LinkedIn is strictly prohibited."* Path teknis `/jobs/view/<id>` sebenarnya tidak di-Disallow satu-satu, tapi larangan blanket ini jelas mencakup semua automated access tanpa izin. |

**Tidak bisa diakses sama sekali saat riset** (bukan larangan, tapi situs tidak
merespons — dicoret karena tidak ada yang bisa diriset):

| Situs | Gejala |
|---|---|
| topkarir.com | Connection refused di semua percobaan (curl & WebFetch) |
| urbanhire.com | Cloudflare error 530 (origin DNS error) — kemungkinan situs sudah tidak aktif/dikonfigurasi ulang |
| kampusmerdeka.kemdikbud.go.id | Timeout total, tidak bisa di-resolve dari environment riset ini |

**Diblokir proteksi bot saat baru mencoba baca robots.txt-nya sendiri** (403 di edge,
sebelum sempat cek isi Disallow-nya):

| Situs |
|---|
| techinasia.com / jobs.techinasia.com |
| remotive.com |
| prosple.com |
| jobicy.com |

### Catatan khusus: Himalayas (himalayas.app)

robots.txt Himalayas **mengizinkan** path detail loker (`Allow: /`, hanya query-param
pagination dan `/apply` yang di-disallow), dan sitemap job (`sitemap-jobs.xml.gz`)
berhasil diambil tanpa masalah — termasuk menemukan listing dari perusahaan Indonesia.
Tapi ketiga halaman detail yang dicoba (via `httpx`/`curl` maupun Playwright headless
Chromium, dua-duanya pakai User-Agent jujur yang sama) semuanya mengembalikan halaman
Cloudflare Managed Challenge ("Just a moment...", header `Cf-Mitigated: challenge`),
bukan konten asli. Ini bukan soal client-side rendering (butuh Chromium untuk
menjalankan JS) — ini proteksi anti-bot aktif di level edge yang menahan permintaan
otomatis apa pun, browser asli atau bukan.

Riset dihentikan di titik ini. Tidak dicoba teknik bypass (stealth plugin, fingerprint
spoofing, dst) karena itu masuk ranah evasion anti-bot, di luar scope riset yang
berbasis "robots.txt mengizinkan, maka boleh diteruskan". **Rekomendasi: skip Himalayas
untuk implementasi** sampai ada keputusan eksplisit soal apakah project ini mau
mengejar situs yang secara teknis menolak automated request — ini keputusan produk/etika
tersendiri, bukan keputusan teknis biasa.

---

## Glints (glints.com)

**Sample URL:** 3 halaman `/id/opportunities/jobs/<slug>/<uuid>` (magang & entry-level).

**Metode ekstraksi paling robust:**
Dua sumber JSON di halaman yang sama, tanpa perlu Playwright:
1. `<script id="__NEXT_DATA__">` → `props.pageProps.initialData.data` — objek job
   sangat kaya (30+ field), tapi `descriptionJsonString`-nya berformat **Draft.js JSON
   blocks**, bukan HTML.
2. `<script type="application/ld+json">` (schema.org `JobPosting`) di halaman yang
   sama — `description`-nya sudah **HTML bersih**.

Rekomendasi teknis: pakai `__NEXT_DATA__` untuk field terstruktur, override
`description_raw` dengan `description` dari JSON-LD supaya dapat HTML langsung tanpa
perlu render Draft.js.

**Pemetaan Field ke ScrapedJobListing:**

| Field | Tersedia? | Sumber di Glints | Catatan |
|---|---|---|---|
| title | Ya | `data.title` | |
| company_name | Ya | `data.company.name` | |
| location_city | Ya | `data.location.formattedName` | |
| location_region | Ya | `data.location.parents[]` (cari level provinsi) | Perlu jalan-jalan di array, tidak flat |
| job_type | Ya | `data.type` (enum: `INTERNSHIP`, `CONTRACT`, dst) | Lebih terstruktur dari Kalibrr |
| job_level | Sebagian | `data.educationLevel` + `min/maxYearsOfExperience` | Tidak ada field "level" tunggal, perlu derivasi |
| category | Ya | `data.hierarchicalJobCategory.name` (+ `.parents[]`) | Berjenjang, bukan flat string |
| description_raw | Ya | JSON-LD `description` (HTML) | Hindari `descriptionJsonString` (Draft.js) |
| qualifications_raw | Beda bentuk | `data.JobSkills[]` (nama skill + `mustHave` boolean) | List terstruktur, bukan teks bebas |
| is_active | Ya, beda bentuk | `data.status` (`"OPEN"` dkk) | Perlu mapping `status == "OPEN"` → `True` |
| posted_at | Ya | `data.createdAt` | |
| updated_at_source | Ya | `data.updatedAt` | |
| deadline_at | Ya | `data.expiryDate` | |

**Field unik Glints:**
- `salaries` (minAmount/maxAmount/currency/paymentFrequency)
- `benefits` (list terstruktur: THR, asuransi, dst)
- `minYearsOfExperience` / `maxYearsOfExperience`
- `educationLevel`
- `isRemote` / `workArrangementOption` (ONSITE/REMOTE/HYBRID)
- `closedAt` (timestamp terpisah dari `status`)

**Deteksi aktif/expired:** Field eksplisit `status` (nilai teramati: `"OPEN"`;
`"CLOSED"` untuk yang tutup belum terverifikasi langsung), didukung `closedAt`
(null selagi buka) dan `expiryDate` sebagai sinyal independen kedua.

**Catatan teknis:** Tidak butuh Chromium. Tidak ada Crawl-delay eksplisit. Sitemap
job di-split jadi puluhan file (`sitemap_job_id_*.xml`) — cocok untuk discovery skala
besar tanpa perlu crawl halaman search yang di-disallow.

---

## loker.id

**Sample URL:** 3 halaman `/<kategori>/<subkategori>/<slug>.html`.

**Metode ekstraksi paling robust:**
Framework Remix (React Router v7), tapi halaman detail **server-rendered penuh**.
Data ada di `window.__remixContext`, path
`state.loaderData["routes/<pola-route>"].job` — setara `__NEXT_DATA__` Kalibrr tapi
nama key route terikat pola URL sehingga kurang stabil untuk hardcode; lebih aman
cari entry `loaderData` yang punya key `"job"`. Ada juga JSON-LD `JobPosting`
standar sebagai fallback yang lebih ringkas tapi lebih stabil lintas-versi framework.

**Pemetaan Field ke ScrapedJobListing:**

| Field | Tersedia? | Sumber di loker.id | Catatan |
|---|---|---|---|
| title | Ya | `job.title` | `job.tag.name` kadang lebih deskriptif |
| company_name | Ya | `job.company_name` | |
| location_city | Ya | `job.locations[0].name` | |
| location_region | Ya | `job.locations[0].parent.name` | Level provinsi asli |
| job_type | Ya | `job.types[0].name` | |
| job_level | Ya | `job.level.name` | |
| category | Ya | `job.category` / `job.categories[0].name` | |
| description_raw | Ya | `job.job_description` (HTML) | |
| qualifications_raw | Ya | `job.qualifications` (HTML) | Field terpisah, persis seperti skema |
| is_active | Ya | `job.status == "publish"` | Nilai non-aktif belum teramati langsung |
| posted_at | Ya | `job.post_date` | Ada juga `published_at`, perlu pilih kanonik |
| updated_at_source | Ya | `job.post_modified` | |
| deadline_at | **Tidak ada** | - | Tetap nullable |

**Field unik loker.id:**
- `salary_min`/`salary_max`/`salary` (label) + `is_hide_salary`
- `is_remote` (boolean)
- `need_urgent` (boolean, badge urgent hiring)
- `responsibilities` — blok teks terpisah dari `qualifications` dan `job_description` (3 blok teks, bukan 2)
- `screening_questions` (array pertanyaan pre-screening)
- `educations` — requirement pendidikan terstruktur (id/name/slug)
- Taksonomi kategori berjenjang (`categories[0].parent`)
- `job.id` — identifier numerik native

**Deteksi aktif/expired:** Field eksplisit `job.status` (teramati `"publish"` di
ketiga sample yang masih live; nilai untuk expired belum terverifikasi).

**Catatan teknis:** Tidak butuh Chromium. Tidak ada `sitemap.xml` (404) — discovery
lewat homepage/kategori. Ada Cloudflare Turnstile tapi khusus form apply/login, tidak
menghalangi GET biasa ke halaman detail.

---

## We Work Remotely (weworkremotely.com)

**Sample URL:** 3 halaman `/remote-jobs/<slug>`, ditemukan lewat feed RSS kategori
(`/categories/remote-programming-jobs`) — tidak perlu CSS selector sama sekali untuk
discovery.

**Metode ekstraksi paling robust:**
JSON-LD `schema.org/JobPosting` di `<script type="application/ld+json">` — bukan
`__NEXT_DATA__`/`__NUXT__` (WWR tidak pakai itu). Field utama tinggal `json.loads()`
langsung, HTML sudah server-rendered penuh (tidak butuh eksekusi JS).

**Pemetaan Field ke ScrapedJobListing:**

| Field | Tersedia? | Sumber di WWR | Catatan |
|---|---|---|---|
| title | Ya | `title` | |
| company_name | Ya | `hiringOrganization.name` | |
| location_city | **Tidak** | - | 100% remote, tidak ada kota — selalu `None` |
| location_region | Sebagian | `hiringOrganization.address` | Alamat HQ perusahaan, BUKAN syarat lokasi pelamar |
| job_type | Ya | `employmentType` | Nilai schema.org standar |
| job_level | **Tidak** | - | Tidak ada field level eksplisit |
| category | Ya (meragukan) | `occupationalCategory` | Sama persis di ketiga sample walau job beda — kemungkinan tidak granular per-listing |
| description_raw | Ya | `description` (HTML, ada entity escape) | |
| qualifications_raw | **Tidak terpisah** | - | Menyatu di dalam `description` |
| is_active | **Tidak eksplisit** | - | Harus disimpulkan |
| posted_at | Ya | `datePosted` | |
| updated_at_source | **Tidak** | - | |
| deadline_at | Ya | `validThrough` | Konsisten 30 hari setelah `datePosted` di ketiga sample — kemungkinan default policy, bukan diisi manual |

**Field unik WWR:**
- `baseSalary` (min/max/currency/unit) — sering 0/0 (gaji tidak diumumkan)
- **`applicantLocationRequirements`** — daftar kode negara yang boleh melamar; ketiga
  sample eksplisit mencantumkan `ID` (Indonesia). **Relevan langsung untuk validasi
  "remote realistis dari Indonesia"** — lihat catatan di bagian rekomendasi.
- `jobLocationType` ("TELECOMMUTE")

**Deteksi aktif/expired:** Tidak ada field boolean eksplisit. Kandidat: bandingkan
`validThrough` vs sekarang (asumsi, bukan konfirmasi), atau cek ulang response HTTP
saat recheck — belum terverifikasi langsung karena ketiga sample masih aktif.

**Catatan teknis:** Tidak butuh Chromium. Tidak ada Crawl-delay eksplisit.
`location_city`/`location_region` akan sering `None` untuk sumber ini — sudah sesuai
desain skema yang nullable.

---

## Wellfound (wellfound.com)

**Sample URL:** 3 halaman `/jobs/<id>-<slug>` (path kanonik, bukan `/_jobs/` yang
di-disallow).

**Metode ekstraksi paling robust:**
Halaman detail loker **tidak** punya `__NEXT_DATA__` (beda dari halaman `/browse/*`
yang Next.js+GraphQL client-side, HTML awalnya kosong). Yang ada adalah
`<script type="application/ld+json">` schema.org `JobPosting` — cukup lengkap. **Tapi
1 dari 3 sample sama sekali tidak punya blok JSON-LD ini** meski halaman valid
(kemungkinan template listing "off-platform"/syndicated berbeda) — scraper wajib
punya fallback graceful (return `None`), jangan asumsikan JSON-LD selalu ada.

**Kendala discovery penting:** Tidak ada sitemap job yang berguna (sitemap.xml.gz
hanya berisi halaman marketing). Halaman `/browse/tech-jobs` client-side rendered,
dan setelah di-render Chromium pun cuma berisi link ke `/job-collections/<slug>`
(kurasi), bukan link job langsung — dan sebagian link di situ mengarah ke
`/jobs/signup?...` (disallowed, harus difilter).

**Pemetaan Field ke ScrapedJobListing:**

| Field | Tersedia? | Sumber di Wellfound | Catatan |
|---|---|---|---|
| title | Ya | `title` | Sering ada prefix level (Senior/Lead) |
| company_name | Ya | `hiringOrganization.name` | |
| location_city | Sebagian | `jobLocation[].address.addressLocality` | Null untuk role full-remote |
| location_region | Sebagian | `...addressRegion` | Sama, bisa null |
| job_type | Ya | `employmentType` (enum) | |
| job_level | **Tidak eksplisit** | - | Harus disimpulkan dari `title` |
| category | Beda bentuk | `industry` (string multi-tag deskriptif) | Bukan kategori bersih, perlu normalisasi |
| description_raw | Ya | `description` (HTML) | |
| qualifications_raw | **Tidak terpisah** | - | Menyatu di `description` |
| is_active | **Tidak ada** | - | Belum terverifikasi |
| posted_at | Ya | `datePosted` | |
| updated_at_source | **Tidak ada** | - | |
| deadline_at | **Tidak diisi** | `validThrough` ada di schema tapi kosong di semua sample | |

**Field unik Wellfound:**
- `baseSalary` (currency/minValue/maxValue/unitText) — cukup lengkap, mis. USD 150000-220000/YEAR
- `jobBenefits` (free-text list)
- `experienceRequirements.monthsOfExperience` (hanya di 1 dari 2 sample yang punya JSON-LD)
- `hiringOrganization.logo` + koordinat lokasi kantor
- `directApply` (boolean) — apply langsung di Wellfound vs diarahkan keluar

**Deteksi aktif/expired:** Tidak ditemukan field eksplisit. Kemungkinan lewat HTTP
status (404/redirect) saat listing ditutup — **dugaan, belum terverifikasi**.

**Catatan teknis:** **Butuh Chromium untuk fase discovery** (browse/job-collections
client-side rendered), tapi halaman detail sendiri cukup `httpx` biasa. Desain
discovery terpisah dari scrape detail bisa menghemat concurrency Chromium. Data
condong ke role tech level menengah-atas (Senior/Lead/Principal) — **kurang cocok
untuk fokus magang/entry-level project ini** dibanding Glints/Kitalulus, tapi tetap
relevan untuk kategori remote global.

---

## RemoteOK (remoteok.com)

**Sample:** feed publik `/remote-jobs.json` + 1 halaman detail asli + 1 ID lama untuk
uji deteksi expired (hasil: 404).

**Metode ekstraksi paling robust:**
RemoteOK **mempublikasikan feed JSON publik resmi** di `/remote-jobs.json` (di-link
eksplisit di `<head>` tiap halaman). Jauh lebih robust dari parsing HTML — tinggal
GET + `json.loads()`, entry pertama array adalah metadata, sisanya array job. Halaman
detail HTML sendiri tidak punya `__NEXT_DATA__`/`__NUXT__`; JSON-LD yang ada cuma
`Organization` (bukan `JobPosting`). Fallback berikutnya: `og:title`/`og:description`
meta tag, baru terakhir CSS selector HTML biasa (server-rendered, bukan CSR).

**Batasan:** feed hanya berisi 100 listing terbaru, tanpa pagination — untuk data
historis harus scrape halaman kategori/arsip HTML biasa.

**Ketentuan legal dari feed:** field `"legal"` di entry pertama mewajibkan backlink
**dofollow** ke RemoteOK dan atribusi sumber setiap menampilkan datanya — selaras
dengan keputusan "Transparansi Data" project ini, tapi pastikan link dofollow.

**Content-Signal robots.txt:** `ai-train=no` — jangan pakai konten RemoteOK untuk
melatih model AI (riset ini hanya baca struktur, aman; tapi jadi batasan untuk
implementasi AI layer nanti).

**Pemetaan Field ke ScrapedJobListing:**

| Field | Tersedia? | Sumber di RemoteOK | Catatan |
|---|---|---|---|
| title | Ya | `position` | |
| company_name | Ya | `company` | |
| location_city | **Tidak** | `location` | Sering string kosong (remote-only) |
| location_region | **Tidak** | `location` | Sama, tidak granular |
| job_type | Tidak terstruktur | `tags[]` | Kadang ada tag "full time"/"contract", campur dengan tag lain |
| job_level | **Tidak** | - | Tidak ada field eksplisit |
| category | Tidak 1:1 | `tags[]` | Multi-tag skill/topik, bukan kategori tunggal |
| description_raw | Ya | `description` (HTML) | |
| qualifications_raw | **Tidak** | - | Menyatu di `description` |
| is_active | Implisit | - | Job hilang dari feed + halaman detail 404 → expired |
| posted_at | Ya | `date` (ISO8601) / `epoch` | Dua representasi sekaligus |
| updated_at_source | **Tidak** | - | |
| deadline_at | **Tidak ada konsepnya** | - | Listing evergreen sampai ditutup manual |

**Field unik RemoteOK:**
- `salary_min`/`salary_max` (sering 0/0 kalau tidak diisi)
- `tags[]` (skill/topik, berguna untuk matching/kategorisasi AI layer)
- `apply_url` (bisa sama dengan `url` atau ATS eksternal)
- `id`/`slug` (identifier native, untuk dedup level-source)
- `company_logo`

**Deteksi aktif/expired:** Tidak ada field eksplisit. Verifikasi langsung: ID lama
mengembalikan **404** (bukan redirect/halaman "closed") — job yang masih di feed
100-terbaru dianggap aktif.

**Catatan teknis:** Tidak butuh Chromium sama sekali (feed + HTML statis). Tidak ada
Crawl-delay eksplisit. Berpotensi paling ringan resource-nya dari semua situs di
riset ini karena tidak perlu parse HTML untuk data utama.

---

## Kitalulus (kitalulus.com)

**Sample URL:** 3 halaman `/lowongan/detail/<slug>`, ditemukan lewat sitemap
(`sitemap.xml` → `sitemap/sitemap-jobs/job-detail-N.xml`).

**Metode ekstraksi paling robust:**
Bukan `__NEXT_DATA__` klasik — Kitalulus pakai **Next.js App Router dengan React
Server Components streaming**. Data disuntik lewat banyak tag
`<script>self.__next_f.push([1,"..."])</script>` tersebar di HTML (11 chunk pada
sample ini). Objek `"vacancy":{...}` muncul setelah semua chunk digabung &
di-unescape; beberapa field teks panjang (`description`, `formattedDescription`)
adalah referensi `"$1f"`/`"$20"` yang menunjuk ke chunk lain berpola
`1f:T<panjang>,<teks>` — perlu resolve dua tahap. Tidak butuh CSS selector, tidak
butuh Chromium (semua ada di initial HTML response), tapi parser harus lebih tahan
banting dari `json.loads` sederhana ala Kalibrr.

**Pemetaan Field ke ScrapedJobListing:**

| Field | Tersedia? | Sumber di Kitalulus | Catatan |
|---|---|---|---|
| title | Ya | `vacancy.positionName` | |
| company_name | Ya | `vacancy.company.name` | |
| location_city | Ya | `vacancy.city.name` | |
| location_region | Ya | `vacancy.province.name` | |
| job_type | Ya | `vacancy.typeStr` | "Kontrak"/"Full-Time"/"Freelance"/kemungkinan "Magang" |
| job_level | **Tidak eksplisit** | - | Perlu disimpulkan dari `typeStr`/`educationLevelStr` |
| category | Ya (mendekati) | `vacancy.jobRole.displayName` | |
| description_raw | Ya, tapi isinya nyasar | `vacancy.formattedDescription` (HTML) | Isinya justru daftar Kualifikasi, bukan narasi tugas terpisah |
| qualifications_raw | Ya, field sama dgn description_raw | `vacancy.formattedDescription`/`description` | Cuma SATU field gabungan — isi keduanya akan duplikat |
| is_active | Ya, lebih eksplisit dari Kalibrr | `!vacancy.isClosed && vacancy.isPublished` | Dua flag boolean terpisah |
| posted_at | **Tidak ditemukan** | - | Tetap nullable |
| updated_at_source | Ya | `vacancy.updatedAt` (unix microseconds) | Satuan beda dari ISO string |
| deadline_at | Ya | `vacancy.closeDate` (unix microseconds) | |

**Field unik Kitalulus:**
- `salaryLowerBound`/`salaryUpperBound` (0/0 di sample ini, kemungkinan besar berarti "tidak diungkap")
- `educationLevelStr` (mis. "Minimal D3/S1")
- `genderStr` (mis. "Perempuan") — **catatan sensitif**, lihat bagian rekomendasi
- `maxAge`/`maxAgeStr` — **catatan sensitif**, lihat bagian rekomendasi
- `minExperience`/`minExperienceStr`
- `locationSiteStr` (WFO/Hybrid/kemungkinan WFH)
- `workingDayStartStr`/`workingDayEndStr`, `workingHourStartStr`/`workingHourEndStr`
- `skillTags` (array skill/tools)
- `company.companyIndustry.name`, `company.description`

**Deteksi aktif/expired:** Eksplisit — `isPublished == true && isClosed == false`.
**Catatan penting:** ketiga sample dari sitemap kebetulan semuanya `isClosed: true` —
sitemap job-detail Kitalulus berisi juga loker lama/tertutup, jadi kehadiran di
sitemap TIDAK menjamin aktif; recheck/filter status tetap wajib di layer scraper.

**Catatan teknis:** Tidak butuh Chromium meski pakai RSC (semua data sudah di
response HTML awal). Tidak ada Crawl-delay eksplisit. Kompleksitas parsing lebih
tinggi dari Kalibrr — kalau diimplementasikan, sebaiknya dibuat helper reusable
"resolve Next.js flight reference" karena pola ini kemungkinan muncul lagi di situs
Next.js App Router modern lain.

---

## Rekomendasi Perubahan ke `ScrapedJobListing`

Field baru direkomendasikan hanya kalau muncul di **minimal 2 situs** (di luar
Kalibrr), sesuai arahan. Field yang cuma ditemukan di 1 situs dicatat sebagai temuan,
bukan rekomendasi.

### Direkomendasikan ditambahkan (nullable semua)

| Field baru | Ditemukan di | Alasan |
|---|---|---|
| `salary_min`, `salary_max`, `salary_currency` | Glints, loker.id, RemoteOK, Kitalulus, Wellfound, WWR (**6 dari 7 situs**) | Sinyal paling kuat di seluruh riset — hampir semua situs selain Kalibrr expose rentang gaji terstruktur, meski sering kosong/0 kalau perusahaan tidak mengisi. Simpan sebagai numerik + currency terpisah, bukan string bebas, supaya bisa dipakai filter/sort nanti. |
| `is_remote` atau `work_arrangement` (onsite/remote/hybrid) | Glints (`workArrangementOption`), loker.id (`is_remote`), Kitalulus (`locationSiteStr`), WWR (implisit — semua listing remote) | Relevan langsung untuk kebutuhan matching ("saya cari kerja remote/WFH"), dan project ini eksplisit menyasar campuran situs lokal + remote global. |
| `skill_tags` (array/JSON text, terpisah dari `qualifications_raw`) | Glints (`JobSkills[]`), RemoteOK (`tags[]`), Kitalulus (`skillTags`) | Data terstruktur untuk matching berbasis skill akan lebih akurat lewat field ini dibanding parsing NLP dari `qualifications_raw` bebas teks. |
| `education_level` | Glints (`educationLevel`), Kitalulus (`educationLevelStr`) | Sinyal penting untuk fokus magang/entry-level yang jadi prioritas project — banyak loker entry-level punya syarat pendidikan eksplisit. |
| `experience_years_min` | Glints (`minYearsOfExperience`), Kitalulus (`minExperience`), Wellfound (`monthsOfExperience`, parsial) | Berguna untuk filter "cocok untuk fresh graduate" (0 tahun) vs yang butuh pengalaman. |
| `benefits_raw` (text/array) | Glints (`benefits`), Wellfound (`jobBenefits`) | Nilai tambah untuk user membandingkan loker, meski prioritas lebih rendah dari field di atas. |

### Dipertimbangkan tapi bukan rekomendasi kuat

- **`source_native_id`** (ID/slug asli dari situs sumber, terpisah dari `source_url`):
  RemoteOK (`id`), loker.id (`job.id`), dan Glints/Kitalulus punya ID di dalam
  slug URL-nya. Berguna untuk dedup level-source yang lebih stabil daripada
  cocok-cocokan URL (URL bisa berubah format, ID biasanya tidak) — tapi ini lebih ke
  keputusan arsitektur `job_listing_sources` daripada field konten `ScrapedJobListing`
  itu sendiri. Layak dipikirkan saat desain tabel, bukan urgent untuk skema loker.
- **`apply_url`** (terpisah dari `source_url`, kalau apply diarahkan ke ATS eksternal):
  disinggung RemoteOK (`apply_url`) dan Wellfound (`directApply` boolean). Prioritas
  rendah — `source_url` sudah cukup untuk transparansi dasar, ini nice-to-have.

### Catatan khusus — bukan rekomendasi otomatis, tapi perlu keputusan sadar

- **`applicant_location_requirements`** (daftar negara yang boleh melamar) — cuma
  ditemukan eksplisit di **1 situs (We Work Remotely)**, jadi secara aturan "minimal
  2 situs" belum lolos threshold rekomendasi. Tapi ini field yang paling langsung
  menjawab kriteria "remote realistis dilamar dari Indonesia" dari brief riset ini —
  WWR eksplisit mencantumkan kode negara `ID` di listingnya. Sebaiknya jadi bahan
  diskusi terpisah: apakah worth ditambahkan sekarang berdasarkan nilai strategisnya,
  atau ditunda sampai situs remote lain (kalau nanti ditambah) juga terbukti punya
  field serupa.
- **Field syarat gender & usia maksimum** (`genderStr`, `maxAge` — ditemukan di
  Kitalulus): ini syarat yang secara sosial/hukum sensitif (berpotensi diskriminatif),
  dan sengaja tidak dimasukkan ke rekomendasi skema di atas. Kalaupun disimpan sebagai
  data mentah apa adanya (sekadar merefleksikan apa yang situs sumber tampilkan),
  perlu keputusan eksplisit dari kamu soal apakah field ini disimpan sama sekali, dan
  kalau iya, apakah boleh dipakai untuk filtering/ranking hasil matching atau hanya
  ditampilkan sebagai informasi read-only. Ini keputusan produk, bukan keputusan
  teknis.

### Field yang tetap harus nullable (dikonfirmasi lintas situs)

Semua field opsional yang sudah ada di skema sekarang **terbukti benar nullable**
lewat riset ini — tidak ada satu pun situs baru yang tersedia 100% untuk field-field
ini:

- `deadline_at` — tidak ada di RemoteOK, WWR (nilainya kelihatan default +30 hari,
  bukan diisi manual), Wellfound (field ada di schema tapi selalu kosong), loker.id.
- `job_level` — tidak ada satupun situs (termasuk Kalibrr) yang punya field level
  eksplisit yang bersih; semua butuh inferensi dari field lain atau dari kategori URL.
- `updated_at_source` — tidak ada di WWR, Wellfound, dan RemoteOK.
- `posted_at` — tidak ditemukan di Kitalulus.
- `category` — tersedia di semua situs tapi bentuknya sangat bervariasi (flat string
  di Kalibrr, hierarchical di Glints, multi-tag deskriptif di Wellfound) — tetap
  disimpan sebagai string bebas per-source, normalisasi ke kategori standar jadi
  tanggung jawab AI/normalisasi layer (sesuai keputusan project yang sudah ada), bukan
  scraper.
- `qualifications_raw` — WWR dan Wellfound tidak memisahkan kualifikasi dari
  deskripsi utama sama sekali (menyatu jadi satu field), dan Kitalulus punya
  duplikasi (field yang sama dipakai untuk `description_raw` maupun
  `qualifications_raw`) — konfirmasi field ini memang harus tetap opsional, bukan
  wajib diisi scraper tiap situs.

### Ringkasan kebutuhan teknis per situs (untuk keputusan prioritas implementasi)

| Situs | Butuh Chromium? | Kompleksitas parsing | Cocok fokus magang/entry-level? |
|---|---|---|---|
| Glints | Tidak | Sedang (2 sumber JSON digabung) | Sangat cocok |
| loker.id | Tidak | Sedang (resolve route key di `__remixContext`) | Cocok |
| Kitalulus | Tidak | Tinggi (RSC chunk streaming, perlu resolver reusable) | Cocok (fokus entry-level/blue-collar) |
| We Work Remotely | Tidak | Rendah (JSON-LD standar) | Kurang (fokus profesional remote) |
| RemoteOK | Tidak | Rendah (feed JSON resmi) | Kurang (campuran level, condong tech) |
| Wellfound | **Ya, untuk discovery saja** (detail-nya tidak) | Sedang, plus fallback wajib (1/3 sample tanpa JSON-LD) | Kurang cocok (condong Senior/Lead/Principal) |
| Himalayas | Diblokir Cloudflare — tidak relevan sampai ada keputusan lain | - | Tidak diketahui (data tidak pernah didapat) |
