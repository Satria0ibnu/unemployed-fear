<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
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
            $table->timestampTz('posted_at')->nullable();
            $table->timestampTz('deadline_at')->nullable();  // sering kosong (WWR/Wellfound/loker.id) — tetap nullable
            $table->timestampTz('updated_at_source')->nullable();
            $table->enum('status', ['active', 'possibly_expired', 'expired'])->default('active');

            // --- Field baru dari riset 7-situs ---
            $table->unsignedBigInteger('salary_min')->nullable();
            $table->unsignedBigInteger('salary_max')->nullable();
            $table->string('salary_currency', 10)->nullable();
            $table->enum('work_arrangement', ['onsite', 'remote', 'hybrid'])->nullable();
            $table->json('skill_tags')->nullable();          // list string, dari Glints/RemoteOK/Kitalulus
            $table->string('education_level')->nullable();   // dari Glints/Kitalulus
            $table->unsignedSmallInteger('experience_years_min')->nullable();
            // Bentuk asli Python (ScrapedJobListing.benefits_raw) adalah list[str],
            // bukan teks bebas — json (bukan text) supaya tidak perlu konversi tipe
            // yang lossy di salah satu sisi. Lihat catatan penyesuaian field di ringkasan.
            $table->json('benefits_raw')->nullable();

            // --- Field sensitif: DISPLAY-ONLY, tidak boleh dipakai filter/ranking ---
            // Ditemukan eksplisit di Kalibrr dan Glints (gender, min/maxAge).
            // JANGAN buat index di kolom ini, dan JANGAN referensikan di query
            // WHERE/ORDER BY manapun di fase Matching nanti — lihat catatan di
            // bawah tabel ini.
            $table->string('gender_requirement_raw')->nullable();
            // Python (ScrapedJobListing.max_age_raw) bertipe int, bukan string —
            // unsignedTinyInteger cukup untuk usia (maks 255). Tetap display-only,
            // perubahan tipe ini tidak membuka pintu untuk dipakai filter/sort.
            $table->unsignedTinyInteger('max_age_raw')->nullable();

            // Embedding untuk semantic similarity search (dedup & matching).
            $table->vector('embedding', dimensions: 768)->nullable();
            $table->timestampsTz();

            $table->index('status');
            $table->index('job_type');
            $table->index('work_arrangement');
        });

        DB::statement('CREATE INDEX job_postings_embedding_idx ON job_postings USING hnsw (embedding vector_cosine_ops)');
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('job_postings');
    }
};
