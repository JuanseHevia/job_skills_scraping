import asyncio
import datetime
import markitdown
from ulid import ULID
from scripts.job_posting import JobExtractor
import argparse
import os 
import json
import dotenv
from tqdm import tqdm

dotenv.load_dotenv(dotenv_path=dotenv.find_dotenv())
DATA_PATH = "data/jobs"

def get_job_data(file_path: str) -> dict:
    """
    Get job data from a JSON file.
    
    Args:
        file_path (str): The path to the JSON file.
        
    Returns:
        dict: The job data.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


async def extract_job_data(url: str, savedir: str) -> dict:
    """
    Extract job data from a URL.
    
    Args:
        url (str): The URL of the job posting.
        
    Returns:
        dict: The extracted job data.
    """
    
    # get MarkItDown object
    md = markitdown.MarkItDown(enable_plugins=False)

    # create ID
    _id = str(ULID())

    # create a JobExtractor instance
    job_extractor = JobExtractor(
        url=url,
        output_filepath=os.path.join(savedir, f"{_id}.json"),
        md_object=md,
        logger_name=f"JobExtractor_{_id}",
    )

    # run the extractor
    await job_extractor.run()
    return job_extractor.structured_output.copy()


if __name__ == "__main__":
    # parse command line arguments
    parser = argparse.ArgumentParser(
        description="Extract job data from a JSON file or a URL.")
    parser.add_argument("--input_path", type=str,
                        required=True,
                        help="Path to the JSON file containing the URLs to extract.")
    parser.add_argument("--output_path", type=str,
                        help="Path to the output JSON file.")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode.")
    parser.add_argument("--start_at", type=int,
                        default=0,
                        help="Start at this index in the input file.")
    args = parser.parse_args()

    # load the JSON file
    if args.input_path.endswith(".json"):
        with open(args.json_path, "r", encoding="utf-8") as f:
            _data = json.load(f)

        data = [item["url"] for item in _data if "url" in item]
    else:
        with open(args.input_path, "r", encoding="utf-8") as f:
            data = f.readlines()
            data = [line.strip() for line in data if line.strip()]

    print(f"Found {len(data)} URLs in the input file.")
    print(data[:4])
    
    assert len(data) > 0, "No data found in the input file."

    _now = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    savedir = os.path.join(DATA_PATH, f"job_data_{_now}_index{args.start_at}")
    os.makedirs(savedir, exist_ok=True)

    results = []

    for idx, url in tqdm(enumerate(data[args.start_at:]), desc="Extracting job data", unit="job",
                          total=len(data[args.start_at:])):
        
        # extract job data
        try:
            job_data = asyncio.run(extract_job_data(url, savedir=savedir))
        except Exception as e:
            continue

        results.append(job_data)

        if args.debug and idx > 5:
            break
    # save results to output file   
    if args.output_path:
        with open(args.output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"Results saved to {args.output_path}")
    
