import json
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
    # base_url: str = "https://www.bumeran.com.ar/en-buenos-aires/empleos-full-time-modalidad-presencial.html"
    province_prefix: str = field(default="en-buenos-aires", init=True)
    base_url: str = field(default="https://www.bumeran.com.ar/{}/empleos.html", init=False)
    max_page: int = field(init=False, default=1)
    max_page_limit: int = field(default=10)
    current_page: int = field(init=False, default=1)

    def __post_init__(self, province_prefix: str = "en-buenos-aires"):
        super().__post_init__()
        self.base_url = self.base_url.format(province_prefix)
        self.logger.info(f"Base URL set to: {self.base_url}")
        

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

            # populate data store with job URL and page number
            self.data_store.append({
                "url": url,
                "page_number": self.current_page,
            })
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

async def run_scraper(max_page_limit : int, province_prefix: str, output_filepath: str):
    """
    Runs the Bumeran job scraper asynchronously with the specified parameters.
    Args:
        max_page_limit (int): The maximum number of pages to scrape.
        province_prefix (str): The prefix representing the province to filter job listings.
        output_filepath (str): The file path where the scraped data will be saved.
    Returns:
        None
    Raises:
        Any exceptions raised by the BumeranScraper during execution.
    Example:
        await run_scraper(10, "en-catamarca", "jobs_test")
    """
    # Initialize the scraper with the specified maximum page limit
    scraper = BumeranScraper(max_page_limit=max_page_limit,
                             province_prefix=province_prefix,
                             output_filepath=output_filepath,
                             logger_name="BumeranScraper",)
    await scraper.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape job postings from Bumeran.")
    parser.add_argument("--max_page_limit", type=int, default=10, help="Maximum number of pages to scrape.")
    parser.add_argument("--all_provinces", action="store_true", help="Scrape all provinces.")
    parser.add_argument("--filename", type=str, default="bumeran_data", help="Output file path for scraped data without extension.")
    args = parser.parse_args()


    # create filepath
    _now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    _output_filepath = os.path.join(RESULTS_DIR, f"{args.filename}_{_now}.json")


    # prompt the user to choose the province
    with open("src/province_prefix.json", "r") as f:
        province_prefixes = json.load(f)

    if not args.all_provinces:

        print("Available provinces:")
        for i, province in enumerate(province_prefixes.keys(), start=0):
            print(f"{i}. {province}")

        choice = input("Enter the number of the province to scrape: ")

        if choice.isdigit() and int(choice) in range(len(province_prefixes)):
            province_choice = list(province_prefixes.keys())[int(choice)]
            print(f"Selected province: {choice} ({province_choice})")
        else:
            raise ValueError("Invalid choice. Please enter a valid number.")
            
        asyncio.run(run_scraper(max_page_limit=args.max_page_limit, 
                                province_prefix=province_choice,
                                output_filepath=_output_filepath))

    
    print("Scraping all provinces...")
    # scrape all provinces
    for prefix in tqdm(province_prefixes, desc="Scraping provinces", unit="province"):
        print(f"Scraping {prefix}...")
        _output_filepath = os.path.join(RESULTS_DIR, f"{args.filename}_{prefix.replace('/','-')}_{_now}.json")
        asyncio.run(run_scraper(max_page_limit=args.max_page_limit, 
                                province_prefix=prefix,
                                output_filepath=_output_filepath))
        print(f"Finished scraping {prefix}. Data saved to {_output_filepath}")