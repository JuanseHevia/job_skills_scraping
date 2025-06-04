# Skill Scraping

A Python project for scraping job postings from Bumeran, extracting structured job data via OpenAI, converting content to Markdown, and processing results for skill embedding and analysis.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Configuration](#configuration)
- [Running the Job List Scraper](#running-the-job-list-scraper)
- [Extracting Job Details](#extracting-job-details)
- [Directory Structure](#directory-structure)
- [Main Modules and Entities](#main-modules-and-entities)
- [Analysis and Embeddings](#analysis-and-embeddings)
- [Logging](#logging)
- [License](#license)

## Prerequisites

- Python 3.11 or higher
- [Poetry](https://python-poetry.org/) (optional) or `pip`
- A valid `STEEL_API_KEY` for Steel browser sessions
- A valid `OPENAI_API_KEY` for OpenAI API access

## Environment Setup

1. Clone the repository:

   ```bash
   git clone <repo-url>
   cd skill_scraping
   ```

2. (Optional) Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   Using Poetry:

   ```bash
   poetry install
   ```

   Or using pip:

   ```bash
   pip install --upgrade pip
   pip install .
   ```

4. Create a `.env` file in the project root with your API keys:

   ```dotenv
   STEEL_API_KEY=your_steel_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

## Configuration

- `pyproject.toml`: Defines project metadata and Python dependencies.
- `.env`: Stores environment variables for Steel and OpenAI API keys.

## Running the Job List Scraper

Use `scripts/job_list.py` to collect URLs of job postings from Bumeran:

```bash
python -m scripts.job_list \
  --max_page_limit 5 \
  --filename bumeran_jobs
```

This generates:

- `scraped/bumeran_jobs_<timestamp>.json`: JSON file with URLs and metadata.
- `scraped/bumeran_jobs_<timestamp>.txt`: Plain-text list of URLs.

## Extracting Job Details

### Batch Extraction

Use `get_job_data.py` to fetch and process each job URL into structured JSON:

```bash
python get_job_data.py \
  --input_path scraped/bumeran_jobs_<timestamp>.txt \
  --output_path data/jobs/job_data_<timestamp>.json
```

- Reads URLs from either a text file or a JSON list.
- Converts HTML to Markdown.
- Queries OpenAI to extract:
  - Title, company, location, full description, work mode, seniority, skills with justifications.
- Saves output to `data/jobs/job_data_<timestamp>_index<start>.json`.

### Single Extraction

For a single URL:

```bash
python scripts/job_posting.py \
  --url "https://bumeran.com.ar/..." \
  --output detailed_job_<timestamp>.json
```

## Directory Structure

```
.
├── get_job_data.py        # Batch job data extraction
├── scripts/
│   ├── scraper.py         # Base Scraper class
│   ├── job_list.py        # Bumeran URL list scraper
│   └── job_posting.py     # Single job detail extractor
├── data/                  # Structured job data outputs
│   └── jobs/
├── scraped/               # Raw scraping outputs (URLs)
├── notebooks/             # Analysis & embedding notebooks
│   └── find_skillds.ipynb
├── logs/                  # Runtime and error logs
├── pyproject.toml         # Project config & dependencies
└── README.md              # This file
```

## Main Modules and Entities

- `Scraper` (scripts/scraper.py): Abstract base class managing Steel browser sessions and logging.
- `BumeranScraper` (scripts/job_list.py): Extends `Scraper` to collect job posting URLs.
- `JobExtractor` (scripts/job_posting.py): Extends `Scraper` to convert HTML to Markdown and extract structured data via OpenAI.
- `JobPosting` & `Skill` (Pydantic models): Define the schema of extracted job data.

## Analysis and Embeddings

Open the Jupyter notebook `notebooks/find_skillds.ipynb` to:

1. Load and combine job data from `data/jobs/...`.
2. Use `pandas` and `matplotlib` for exploration.
3. Embed job descriptions or skill text using `sentence-transformers`:

   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer("nomic-ai/modernbert-embed-base", truncate_dim=256)
   embeddings = model.encode(df['description'].tolist(), show_progress_bar=True)
   ```

4. Perform clustering or similarity analysis on skill embeddings.

## Logging

- Log files are stored in the `logs/` directory.
- Each scraper uses its `logger_name` plus a timestamp (e.g., `BumeranScraper_20250501_1010.log`).

## License

*(Add license information here, e.g., MIT License)*
