from langchain.tools import tool
from dotenv import load_dotenv
import datetime
import requests
import os

load_dotenv(override=True)

db_api_root_url = os.getenv("DB_API_ROOT_URL")
db_api_relative_path = os.getenv("DB_API_RELATIVE_PATH")  # Default to "filings" if not set

@tool
def retrieve_10k_filing(ticker: str, date: datetime.date) -> str:
    """
    Retrieves the 10-K filing text for a given ticker and year.
    Use this when you need to fetch the actual filing content for analysis.
    Returns the filing text as a string, or an error message if not found.
    """
    try:
        response = requests.get(f"{db_api_root_url}/{db_api_relative_path}/{ticker}/{date}")
        if response.status_code == 200:
            return response.json() #change to text if needed
        else:
            return f"Error retrieving filing: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exception occurred while retrieving filing: {str(e)}"

@tool
# def mock_retrieve_10k_filing(ticker: str, date: datetime.date) -> str:
def mock_retrieve_10k_filing(ticker: str, date: str) -> dict:
    """
    Mock function to retrieve the 10-K filing text for a given ticker and year.
    Use this when you need to fetch the actual filing content for analysis.
    Returns the filing text as a string, or an error message if not found.
    """
    return mock_response

mock_response = {'ticker': 'AAA', 'date': '2023', 'content': """
        Apple Inc. 2023 Form 10-K, Item 1A, pp. 4-5

        The Company’s business, reputation, results of operations, financial condition and stock price can be affected by a number of factors, whether currently known or unknown, including those described below. ... past financial performance should not be considered to be a reliable indicator of future performance, and investors should not use historical trends to anticipate results or trends in future periods.

        The Company has international operations with sales outside the U.S. representing a majority of the Company’s total net sales. In addition, the Company’s global supply chain is large and complex and a majority of the Company’s supplier facilities, including manufacturing and assembly sites, are located outside the U.S."""}