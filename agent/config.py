import os

# Base directory is two levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Input/output file paths
CSV_OUTPUT = "enriched_companies.csv"

# Number of retries for API calls
MAX_RETRIES = 1

# Document content path
BIZZZUP_DOCUMETS = os.path.join(BASE_DIR, 'files', 'BIZZZUP.docx')