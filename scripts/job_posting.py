from dataclasses import dataclass, field
import asyncio
import datetime
import json
from openai import OpenAI
from pydantic import BaseModel
from ulid import ULID
import markitdown
import os
from .scraper import Scraper
import argparse
from typing import Dict, List, Literal

RESULTS_DIR = "scraped/jobs"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

class Skill(BaseModel):
    name: str
    justification: str

class JobPosting(BaseModel):
    title: str
    company: str
    location: str
    description: str
    mode: Literal["presencial", "remoto"]
    seniority: Literal["junior", "semi-senior", "senior"]
    skills: List[Skill]


@dataclass(kw_only=True)
class JobExtractor(Scraper):
    """
    A class to represent a job posting.
    """
    url: str
    md_object: markitdown.MarkItDown
    openai_model: str = field(default="gpt-4o-mini-2024-07-18")
    metadata: Dict = field(default_factory=dict)

    async def _get_html(self):
        """
        Get the HTML content of the job posting.
        """
        self.logger.info(f"Getting HTML content from {self.url}")
        await self.page.goto(self.url)

        # go to "section detalle"
        post_info = self.page.locator("#ficha-detalle")

        # store html into a temporary directory
        self.temp_id = str(ULID())
        self.temp_dir = os.path.join("temp", f"{self.temp_id}.html")
        with open(self.temp_dir, "w", encoding="utf-8") as f:
            _html = await post_info.inner_html()
            f.write(_html)
        self.logger.info("HTML content saved to temp.html")

    def _query_openai(self) -> JobPosting:
        """
        Query OpenAI for structured output.
        """
        # create OpenAI client
        self.openai_client = OpenAI()

        completion = self.openai_client.beta.chat.completions.parse(
            model=self.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": f'''
                    Eres un extractor experto de datos estructurados de avisos de trabajo.
                    A partir del texto en Markdown, sin estructurar, de una oferta, extrae estos campos: 
                    - título del puesto 
                    - nombre de la empresa
                    - ciudad o región
                    - descripción completa del rol
                    - modalidad de trabajo, sólo puede ser una de : “presencial” o “remoto”
                    - nivel de experiencia (“junior”, “semi-senior” o “senior”, según juzgues apropiado)
                    - un objeto "skills” en el que cada clave sea una habilidad concreta y cada valor la justificación de por qué es necesaria para el puesto. Asegurate de 
                    que la justificación sea clara y concisa, breve.

                    Si no tienes información suficiente para completar alguno de los campos, no proveas una respuesta y rellena con "N/A".
                    '''
                },
                {
                    "role": "user",
                    "content": f'''
                    Extrae los datos estructurados de la siguiente oferta de trabajo en Markdown:
                    {self.text_content}
                    '''
                }
            ],
            response_format=JobPosting
        )

        # parse the response
        self.logger.info("Parsing OpenAI response...")
        parsed_response = completion.choices[0].message.parsed
        if parsed_response is None:
            self.logger.error("OpenAI response could not be parsed into JobPosting model.")
            raise ValueError("Failed to parse OpenAI response into JobPosting model.") # TODO: add missing try catch
        return parsed_response

    async def scrape(self):
        """
        Scrape the job posting from the given URL.
        """
        # get the HTML content of the job posting
        await self._get_html()

        # convert it to Markdown
        self.logger.info("Converting HTML to Markdown...")
        self.text_content = self.md_object.convert(self.temp_dir)

        # run it through OpenAI for structured output
        self.logger.info("Querying OpenAI for structured output...")
        response = self._query_openai()
        self.structured_output = response.model_dump(mode="json")
        # update the structured output with the metadata
        self.structured_output.update(self.metadata)
        # add the original HTML content
        self.structured_output["md_text"] = self.text_content.markdown
        # add the original URL
        self.structured_output["url"] = self.url

        self.logger.info("Structured output received.")
        self.logger.info(f"Structured output: {self.structured_output}")

    def save_data(self):
        """
        Save the structured data to a JSON file.
        """
        if self.output_filepath:
            with open(self.output_filepath, "w", encoding="utf-8") as f:
                json.dump(self.structured_output,
                          f, indent=4, ensure_ascii=False)
            self.logger.info(f"Structured data saved to {self.output_filepath}")

async def run_scaper(url: str, output_filepath: str, md_object: markitdown.MarkItDown):
    """
    Run the scraper for the given URL.
    Args:
        url (str): The URL to scrape.
        output_filepath (str): The path to save the structured data.
        md_object (markitdown.MarkItDown): The MarkItDown object to use for conversion.
    Returns:
        None
    """
    # create a JobExtractor instance
    job_extractor = JobExtractor(url=url,
                                 output_filepath=output_filepath,
                                 md_object=md_object,
                                 logger_name="JobExtractor",)

    # scrape the job posting
    await job_extractor.run()

if __name__ == "__main__":
    # parse command line arguments
    parser = argparse.ArgumentParser(
        description="Scrape job postings from Bumeran.")
    parser.add_argument("--url", type=str, required=True,
                        help="URL of the job posting to scrape.")
    parser.add_argument("--output", type=str,
                        default="output.json", help="Output file path.")
    args = parser.parse_args()

    # initialize MarkItDown object
    md = markitdown.MarkItDown(enable_plugins=True)

    _now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    _output_filepath = os.path.join(RESULTS_DIR, f"{args.output}_{_now}.json")


    # create a JobExtractor instance
    asyncio.run(run_scaper(args.url, _output_filepath, md))
