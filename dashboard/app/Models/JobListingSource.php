<?php

declare(strict_types=1);

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
