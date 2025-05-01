import os
from scraper import Scraper
import re
import datetime
from dataclasses import dataclass, field
import time
import argparse

RESULTS_DIR = "scraped/"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)


@dataclass
class BumeranScraper(Scraper):
    steel_api_key: str = None
    timeout: int = 1000000
    output_filepath: str = None
    base_url: str = "https://www.bumeran.com.ar/en-buenos-aires/empleos-full-time-modalidad-presencial.html"
    max_page: int = field(init=False, default=1)
    max_page_limit: int = field(default=10)
    current_page: int = field(init=False, default=1)

    def _extract_max_pages(self, pagination_links):
        patt_max_num = re.compile(r"\?page=(\d+)")
        num_pages = []
        for link in pagination_links:
            href = link.get_attribute("href") or ""
            match = patt_max_num.search(href)
            if match:
                self.logger.info(f"Page URL: {match.group(1)}")
                num_pages.append(int(match.group(1)))

        self.max_page = max(num_pages) if max(num_pages) < self.max_page_limit else self.max_page_limit
        self.logger.info(f"Max page: {self.max_page}")

    def _process_job_rows(self, job_rows):
        for job_row in job_rows:
            href = job_row.locator("a").get_attribute("href") or ""
            url = f"https://bumeran.com.ar{href}"
            self.data_store.append({
                "url": url,
                "page_number": self.current_page,
                "html_raw": job_row.inner_html(),
            })
            self.logger.info(f"Job URL: {url}")

    def scrape(self):
        start = time.time()
        try:
            self.logger.info("Navigating to Bumeran...")
            # format page number in URL to include pagination
            page_url = f"{self.base_url}?page={self.current_page}"
            self.logger.info(f"Page URL @ #{self.current_page} : {page_url}")
            self.page.goto(page_url)
            
            self.logger.info("\nWaiting for the page to load...")
            self.page.wait_for_selector("#listado-avisos > div:has(a)", timeout=self.timeout)

            self.logger.info("\nLocating job rows...")
            job_rows = self.page.locator("#listado-avisos > div:has(a)").all()
            pagination_links = job_rows[-1].locator("a").all()
            self.logger.info(f"\nFound {len(pagination_links)} pages.")
            
            # extract max pages only on the first page
            self._extract_max_pages(pagination_links)
            self.logger.info(f"Found {len(job_rows)} job rows.")
            # skip the first two rows (sorting options and pagination footer)
            self._process_job_rows(job_rows[2:-1])

            # repeat for the rest of the pages
            for page_num in range(2, self.max_page + 1):
                self.current_page = page_num
                self.logger.info(f"Scraping page {self.current_page} of {self.max_page}...")
                # move to next page
                page_url = f"{self.base_url}?page={self.current_page}"
                self.logger.info(f"Page URL @ #{self.current_page} : {page_url}")
                self.page.goto(page_url)
                self.page.wait_for_selector("#listado-avisos > div:has(a)", timeout=self.timeout)
                self.logger.info("\nWaiting for the page to load...")
                
                # parse job rows
                job_rows = self.page.locator("#listado-avisos > div:has(a)").all()
                self.logger.info(f"Found {len(job_rows)} job rows.")
                
                # skip the first two rows (sorting options and pagination footer)
                self._process_job_rows(job_rows[2:-1])


            end = time.time()
            self.logger.info(f"Scraping completed in {(end - start) / 60:.2f} minutes.")
            self.logger.info("Reached the maximum page limit.")

        except Exception as e:
            self.logger.error(f"An error occurred during scraping: {e}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape job postings from Bumeran.")
    parser.add_argument("--max_page_limit", type=int, default=10, help="Maximum number of pages to scrape.")
    parser.add_argument("--filename", type=str, default="bumeran_data", help="Output file path for scraped data without extension.")
    args = parser.parse_args()

    # create filepath
    _now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    _output_filepath = os.path.join(RESULTS_DIR, f"{args.filename}_{_now}.json")

    # Initialize the scraper with the specified maximum page limit
    scraper = BumeranScraper(max_page_limit=args.max_page_limit,
                             output_filepath=_output_filepath,
                             logger_name="BumeranScraper",)
    scraper.run()
