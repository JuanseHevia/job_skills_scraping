import os

from tqdm import tqdm
from scraper import Scraper
import re
import datetime
from dataclasses import dataclass, field
import time
import argparse
import asyncio

RESULTS_DIR = "scraped/"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)


@dataclass
class BumeranScraper(Scraper):
    timeout: int = 50000000
    base_url: str = "https://www.bumeran.com.ar/en-buenos-aires/empleos-full-time-modalidad-presencial.html"
    max_page: int = field(init=False, default=1)
    max_page_limit: int = field(default=10)
    current_page: int = field(init=False, default=1)

    async def _extract_max_pages(self, pagination_links):
        patt_max_num = re.compile(r"\?page=(\d+)")
        num_pages = []
        for link in pagination_links:
            href = await link.get_attribute("href") or ""
            match = patt_max_num.search(href)
            if match:
                self.logger.info(f"Page URL: {match.group(1)}")
                num_pages.append(int(match.group(1)))

        self.max_page = max(num_pages) if max(num_pages) < self.max_page_limit else self.max_page_limit
        self.logger.info(f"Max page: {self.max_page}")

    async def _process_job_rows(self, job_rows):
        for job_row in job_rows:
            href = await job_row.locator("a").get_attribute("href") or ""
            url = f"https://bumeran.com.ar{href}"
            # self.data_store.append({
            #     "url": url,
            #     "page_number": self.current_page,
            # })
            # write to a text file, appending to last line
            with open(self.temp_textfile_path, "a") as f:
                f.write(f"{url}\n")
            self.logger.info(f"Job URL: {url}")

    async def scrape(self):
        self.temp_textfile_path = self.output_filepath.replace(".json", ".txt")
        # create a temporary text file to store the URLs
        with open(self.temp_textfile_path, "w") as f:
            f.write("")
        self.logger.info(f"Temporary text file created at: {self.temp_textfile_path}")

        start = time.time()
        try:
            self.logger.info("Navigating to Bumeran...")
            # format page number in URL to include pagination
            page_url = f"{self.base_url}?page={self.current_page}"
            self.logger.info(f"Page URL @ #{self.current_page} : {page_url}")
            await self.page.goto(page_url)
            
            self.logger.info("\nWaiting for the page to load...")
            await self.page.wait_for_selector("#listado-avisos > div:has(a)", timeout=self.timeout)

            self.logger.info("\nLocating job rows...")
            job_rows = await self.page.locator("#listado-avisos > div:has(a)").all()
            pagination_links = await job_rows[-1].locator("a").all()
            self.logger.info(f"\nFound {len(pagination_links)} pages.")
            
            # extract max pages only on the first page
            await self._extract_max_pages(pagination_links)
            self.logger.info(f"Found {len(job_rows)} job rows.")
            # skip the first two rows (sorting options and pagination footer)
            await self._process_job_rows(job_rows[2:-1])

            # repeat for the rest of the pages
            for page_num in tqdm(range(2, self.max_page + 1)):
                self.current_page = page_num
                self.logger.info(f"Scraping page {self.current_page} of {self.max_page}...")
                # move to next page
                page_url = f"{self.base_url}?page={self.current_page}"
                self.logger.info(f"Page URL @ #{self.current_page} : {page_url}")
                await self.page.goto(page_url)
                await self.page.wait_for_selector("#listado-avisos > div:has(a)", timeout=self.timeout)
                self.logger.info("\nWaiting for the page to load...")
                
                # parse job rows
                job_rows = await self.page.locator("#listado-avisos > div:has(a)").all()
                self.logger.info(f"Found {len(job_rows)} job rows.")
                
                # skip the first two rows (sorting options and pagination footer)
                await self._process_job_rows(job_rows[2:-1])


            end = time.time()
            self.logger.info(f"Scraping completed in {(end - start) / 60:.2f} minutes.")
            self.logger.info("Reached the maximum page limit.")

        except Exception as e:
            self.logger.error(f"An error occurred during scraping: {e}")
            raise

async def run_scraper(args, _output_filepath):
    """
    Run the Bumeran scraper with the specified arguments.
    Args:
        args (argparse.Namespace): The command line arguments.
        _output_filepath (str): The output file path for scraped data.
    """
    # Initialize the scraper with the specified maximum page limit
    scraper = BumeranScraper(max_page_limit=args.max_page_limit,
                             output_filepath=_output_filepath,
                             logger_name="BumeranScraper",)
    await scraper.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape job postings from Bumeran.")
    parser.add_argument("--max_page_limit", type=int, default=10, help="Maximum number of pages to scrape.")
    parser.add_argument("--filename", type=str, default="bumeran_data", help="Output file path for scraped data without extension.")
    args = parser.parse_args()

    # create filepath
    _now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    _output_filepath = os.path.join(RESULTS_DIR, f"{args.filename}_{_now}.json")

    asyncio.run(run_scraper(args, _output_filepath))
