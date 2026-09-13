from abc import ABC, abstractmethod

from app.models.job_listing import ScrapedJobListing


class ScraperBase(ABC):
    """Kontrak yang wajib dipenuhi setiap scraper situs.
    Menambah situs baru = bikin class baru yang extend ini,
    tanpa mengubah kode yang sudah ada di tempat lain (Open/Closed Principle).
    """

    site_name: str  # contoh: "kalibrr" — dipakai sebagai source_site

    @abstractmethod
    def discover_listing_urls(self, max_pages: int = 1) -> list[str]:
        """Kembalikan daftar URL halaman detail loker yang perlu di-scrape.
        Implementasi tiap situs beda: bisa dari halaman listing/search,
        sitemap, atau API internal situs (kalau ada dan diizinkan).
        """
        raise NotImplementedError

    @abstractmethod
    def scrape_listing(self, url: str) -> ScrapedJobListing | None:
        """Ambil & parse satu halaman detail loker.
        Kembalikan None kalau halaman tidak valid/sudah dihapus/gagal parse
        — jangan lempar exception untuk kasus ini, karena satu halaman
        gagal tidak boleh menghentikan seluruh batch scraping.
        """
        raise NotImplementedError