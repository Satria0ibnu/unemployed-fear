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
        Schema::create('job_listing_sources', function (Blueprint $table) {
            $table->id();
            $table->foreignId('job_posting_id')->constrained()->cascadeOnDelete();
            $table->string('source_site');   // "kalibrr", "glints", "remoteok", "weworkremotely", "lokerid", "wellfound", "kitalulus"
            $table->string('source_url')->unique();
            $table->string('source_native_id')->nullable();  // ID/slug asli dari situs sumber — lebih stabil untuk dedup daripada cocok-cocokan URL
            $table->text('raw_description')->nullable();
            $table->boolean('source_reported_active')->nullable();
            $table->timestampTz('scraped_at');
            $table->timestampTz('last_checked_at');
            $table->unsignedSmallInteger('check_attempts')->default(0);
            $table->enum('status', ['active', 'possibly_expired', 'expired'])->default('active');
            $table->timestampsTz();

            $table->index(['source_site', 'status']);
            $table->index('last_checked_at');
            $table->index('source_native_id');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('job_listing_sources');
    }
};
