import json
import os
import re
import logging
import datetime
from dataclasses import dataclass, field
import time
from dotenv import load_dotenv, find_dotenv
from playwright.sync_api import sync_playwright
from steel import Steel


@dataclass
class Scraper:
    steel_api_key: str = None
    timeout: int = 1000000
    output_filepath: str = None
    logger: logging.Logger = field(init=False)
    logger_name: str = field(default="scraper")
    client: Steel = field(init=False)
    session: any = field(init=False)
    browser: any = field(init=False)
    page: any = field(init=False)
    data_store: list = field(init=False)

    def __post_init__(self):
        load_dotenv(find_dotenv())
        if not self.steel_api_key:
            self.steel_api_key = os.getenv("STEEL_API_KEY")
            assert self.steel_api_key, "STEEL_API_KEY not found in environment variables."
        
        # initialize logger
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.abspath(os.path.join(script_dir, '..'))
        logs_dir = os.path.join(base_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime(f"{self.logger_name}_%Y%m%d_%H%M.log")
        log_filepath = os.path.join(logs_dir, log_filename)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_filepath)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # setup Steel client
        self.client = Steel(steel_api_key=self.steel_api_key)
        self.session = self.client.sessions.create()
        self.logger.info(f"View live session at: {self.session.session_viewer_url}")
        self._setup_browser()
        self.data_store = []

    def _setup_browser(self):
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.connect_over_cdp(
            f"wss://connect.steel.dev?apiKey={self.steel_api_key}&sessionId={self.session.id}"
        )
        context = self.browser.contexts[0]
        self.page = context.pages[0]

    def cleanup(self):
        self.logger.info("Cleaning up resources...")
        self.browser.close()
        self.client.sessions.release(self.session.id)

    def scrape(self):
        raise NotImplementedError("Subclasses must implement scrape method.")

    def save_data(self):
        if self.output_filepath:
            with open(self.output_filepath, "w") as f:
                json.dump(self.data_store, f, indent=4)

    def run(self):
        try:
            self.scrape()
        finally:
            self.cleanup()
            self.save_data()