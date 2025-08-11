import asyncio
from typing import Dict, Any, List
from .perplexity_tool import get_specific_info_tool

async def enrich_data_tool(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches company data by finding and filling missing fields.

    This tool checks for null or empty values in the provided company data dictionary.
    For each missing field, it uses another tool to fetch the information and
    updates the dictionary with the new data.
    """
    # Try to get company name and website from various possible locations
    company_name = company_data.get("company_name") or company_data.get("name", "")
    website = company_data.get("website") or company_data.get("company_website", "")
    
    # If nested company_info exists, try to get from there
    if "company_info" in company_data:
        company_name = company_name or company_data["company_info"].get("name", "")
        website = website or company_data["company_info"].get("website", "")

    if not company_name or not website:
        # Cannot proceed without company name or website
        return company_data

    # Identify missing fields
    missing_fields: List[str] = []
    for field, value in company_data.items():
        if value is None or value == "" or (isinstance(value, list) and not value):
            if field not in ["company_name", "website", "name", "company_info", "document_content", "aggregated_data"]: # These are inputs or meta fields
                missing_fields.append(field)

    if not missing_fields:
        # No data to enrich
        return company_data

    # Use the specific info tool to fetch missing data
    fetched_data = await get_specific_info_tool(
        company_name=company_name,
        website=website,
        fields_to_find=missing_fields
    )

    # Update the original data with the fetched data
    if fetched_data:
        for field, value in fetched_data.items():
            if value and value is not None: # Only update if new data was found
                company_data[field] = value

    return company_data