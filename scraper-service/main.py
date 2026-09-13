from fastapi import FastAPI

from app.scrapers.kalibrr import KalibrrScraper

app = FastAPI(title="unemployed-fear scraper service")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "unemployed-fear-scraper"}


@app.get("/test-scrape/kalibrr")
def test_scrape_kalibrr(limit: int = 3):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = KalibrrScraper()
    urls = scraper.discover_listing_urls(max_pages=1)[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "listings": results}