from fastapi import FastAPI

from app.db.repository import save_scraped_listing
from app.scrapers.glints import GlintsScraper
from app.scrapers.kalibrr import KalibrrScraper
from app.scrapers.kitalulus import KitalulusScraper
from app.scrapers.lokerid import LokerIdScraper
from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.wellfound import WellfoundScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper

app = FastAPI(title="unemployed-fear scraper service")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "unemployed-fear-scraper"}


@app.get("/test-scrape/kalibrr")
def test_scrape_kalibrr(limit: int = 3, save: bool = False):
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
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}


@app.get("/test-scrape/remoteok")
def test_scrape_remoteok(limit: int = 3, save: bool = False):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = RemoteOKScraper()
    urls = scraper.discover_listing_urls()[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}


@app.get("/test-scrape/weworkremotely")
def test_scrape_weworkremotely(limit: int = 3, save: bool = False):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = WeWorkRemotelyScraper()
    urls = scraper.discover_listing_urls()[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}


@app.get("/test-scrape/lokerid")
def test_scrape_lokerid(limit: int = 3, save: bool = False):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = LokerIdScraper()
    urls = scraper.discover_listing_urls()[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}


@app.get("/test-scrape/glints")
def test_scrape_glints(limit: int = 3, save: bool = False):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = GlintsScraper()
    urls = scraper.discover_listing_urls()[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}


@app.get("/test-scrape/wellfound")
def test_scrape_wellfound(limit: int = 3, save: bool = False):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = WellfoundScraper()
    urls = scraper.discover_listing_urls()[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}


@app.get("/test-scrape/kitalulus")
def test_scrape_kitalulus(limit: int = 3, save: bool = False):
    """Endpoint sementara untuk validasi manual pipeline scraping.
    TIDAK untuk produksi — endpoint ini dihapus/diganti setelah
    Data Layer & Queue selesai (fase development berikutnya), digantikan
    oleh job terjadwal, bukan dipicu manual lewat HTTP.
    """
    scraper = KitalulusScraper()
    urls = scraper.discover_listing_urls()[:limit]

    results = []
    for url in urls:
        listing = scraper.scrape_listing(url)
        if listing:
            if save:
                save_scraped_listing(listing)
            results.append(listing.__dict__)

    return {"discovered": len(urls), "scraped": len(results), "saved": save, "listings": results}
