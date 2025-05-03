from abc import abstractmethod
import json
import asyncio
import os
import re
import logging
import datetime
from dataclasses import dataclass, field
import time
from dotenv import load_dotenv, find_dotenv
from playwright.async_api import async_playwright
from steel import Steel
import steel


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
        
        self.logger = self._initialize_logger()

    def _initialize_logger(self):
        """
        Initializes and configures a logger for the current instance.
        This method sets up a logging mechanism that writes log messages to a file. The file is named using the
        logger's name appended with the current date and time (formatted as "%Y%m%d_%H%M"). The log file is stored
        in a "logs" directory located one level above the script's directory. If the directory does not exist, it is created.
        Returns:
            logging.Logger: A configured logger instance set to the INFO level with a file handler attached,
            logging messages in the format "%(asctime)s - %(levelname)s - %(message)s".
        """

        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.abspath(os.path.join(script_dir, '..'))
        logs_dir = os.path.join(base_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime(f"{self.logger_name}_%Y%m%d_%H%M.log")
        log_filepath = os.path.join(logs_dir, log_filename)
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_filepath)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        return logger
    
    async def _initialize_client(self):
        # setup Steel client
        self.client = Steel(steel_api_key=self.steel_api_key)
        self.session = self.client.sessions.create()
        self.logger.info(f"View live session at: {self.session.session_viewer_url}")
        await self._setup_browser()
        self.data_store = []

    async def _setup_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.connect_over_cdp(
            f"wss://connect.steel.dev?apiKey={self.steel_api_key}&sessionId={self.session.id}"
        )
        context = self.browser.contexts[0]
        self.page = context.pages[0]

    async def cleanup(self):
        # Close the browser and release the session
        self.logger.info("Closing browser and releasing session...")
        await self.browser.close()
        try:
            self.client.sessions.release(self.session.id)
        except steel.BadRequestError as e:
            self.logger.error(f"Failed to release session: {e}")
            
        self.logger.info("Session released.")
        # self.logger.info("Cleaning up resources...")
        # self.browser.close()
        # self.client.sessions.release(self.session.id)

    @abstractmethod
    async def scrape(self):
        """
        Abstract method to be implemented by subclasses for the scraping logic.
        This method should contain the specific scraping logic for the target website.
        """
        pass

    def save_data(self):
        if self.output_filepath:
            with open(self.output_filepath, "w") as f:
                json.dump(self.data_store, f, indent=4)

    async def run(self):
        """
        Main method to run the scraper.
        It initializes the Steel client, sets up the browser, and starts the scraping process.
        """
        await self._initialize_client()
        self.logger.info("Scraper initialized.")

        try:
            await self.scrape()
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            print(e)
        finally:
            await self.cleanup()
            self.save_data()