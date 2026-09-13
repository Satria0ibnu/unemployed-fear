<?php

declare(strict_types=1);

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
        'benefits_raw' => 'array',
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
