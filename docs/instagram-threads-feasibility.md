# Feasibility Check — Instagram & Threads sebagai Sumber Loker

> Riset kelayakan, bukan riset struktur data. Kesimpulan: **berhenti di Langkah 1**
> (cek robots.txt/ToS) untuk kedua platform — tidak lanjut ke pengecekan teknis
> apapun, sesuai batasan tugas ini.

## Hasil Cek robots.txt / ToS

Dicek: `instagram.com`, `threads.net`, dan `threads.com` (domain resmi saat ini —
`threads.net` dan `threads.com` mengembalikan **robots.txt yang identik byte-per-byte**;
sitemap yang dirujuk di dalamnya semua memakai `www.threads.com`, jadi itu domain
kanoniknya sekarang).

Kedua platform (Instagram & Threads, keduanya properti Meta) punya robots.txt dengan
pola yang sama persis dan lebih tegas dibanding LinkedIn di riset sebelumnya:

**1. Notice ToS eksplisit di baris paling atas file**, sebelum satu pun aturan
`Disallow` ditulis:

> *"Collection of data on [Instagram/Threads] through automated means is prohibited
> unless you have express written permission from [Instagram/Threads] and may only
> be conducted for the limited purpose contained in said permission. All authorized
> user-agents listed on this page must comply with Meta's Automated Data Collection
> Terms available at: https://www.facebook.com/legal/automated_data_collection_terms"*

**2. Bot generik/tak-dikenal (`User-agent: *`) di-block total:** `Disallow: /` —
bukan sekadar beberapa path, tapi **seluruh situs**, tanpa pengecualian path publik
apapun (halaman profil publik, halaman post individual, semuanya ikut ter-disallow
karena tidak ada aturan Allow terpisah untuk grup ini).

**3. Bahkan bot bernama eksplisit pun mayoritas di-block total**, termasuk
`ClaudeBot` (crawler resmi Anthropic) yang secara spesifik dicantumkan dengan
`Disallow: /` — sejajar dengan `Amazonbot`, `GPTBot`, `PerplexityBot`, `Google-Extended`,
dan crawler AI besar lain. Bot bernama yang masih dapat sedikit akses (Googlebot,
Bingbot, facebookexternalhit, dst) hanya diizinkan untuk keperluan indexing
search-engine/social-preview — bukan scraping konten untuk dipakai ulang, dan tetap
kena banyak Disallow spesifik (`/accounts/`, `/direct/`, `/query/`, dst).

Kombinasi ini — notice ToS eksplisit **plus** blanket `Disallow: /` untuk bot generik
— lebih tegas dari kasus LinkedIn di riset sebelumnya (LinkedIn cuma punya notice
ToS, tanpa blanket block teknis untuk semua path). Untuk `unemployed-fear-bot` yang
bukan salah satu bot bernama di daftar itu, ini dua alasan independen yang
masing-masing sudah cukup untuk menghentikan riset.

## Kenapa Riset Berhenti di Sini

Sesuai aturan yang sudah dipakai konsisten sejak riset job board pertama: begitu
robots.txt secara eksplisit melarang (baik lewat `Disallow` teknis maupun notice ToS
tertulis), situs dicoret tanpa lanjut ke pengecekan struktur data, discovery, atau
kelayakan teknis lainnya — sama seperti perlakuan ke LinkedIn, karir.com, JobStreet,
dan Jora sebelumnya. Instagram dan Threads memenuhi *kedua* kriteria pencoretan
sekaligus, jadi Langkah 2 dan Langkah 3 (cek akses tanpa login, struktur data,
kelayakan OCR untuk poster loker, dst) tidak dijalankan sama sekali — tidak ada fetch
lain yang dilakukan ke domain manapun milik Meta selain mengambil ketiga file
robots.txt di atas.

## Rekomendasi

**Skip.** Instagram dan Threads sebaiknya tidak masuk daftar sumber `unemployed-fear`,
dengan tingkat keyakinan lebih tinggi dibanding keputusan skip untuk Himalayas/JobStreet/
LinkedIn sebelumnya — di sana setidaknya ada celah teknis atau path yang secara
formal tidak dilarang. Di sini, Meta secara eksplisit dan sengaja menutup pintu untuk
kedua alasan sekaligus (hukum/ToS dan teknis), termasuk secara spesifik menyebut nama
`ClaudeBot`.

Kalau data loker dari Instagram/Threads tetap dianggap penting untuk coverage
project ini, satu-satunya jalur yang konsisten dengan prinsip project ("wajib cek
robots.txt & ToS") adalah mencari cara yang memang diizinkan Meta secara resmi —
misalnya Instagram Graph API/Content Publishing API untuk akun yang kamu (atau
komunitas mitra) kelola dan hubungkan sendiri secara sah, bukan scraping akun pihak
ketiga. Itu di luar scope riset kelayakan ini dan butuh keputusan produk terpisah
(apakah realistis mendapat kerja sama dari akun-akun info-loker yang relevan).
