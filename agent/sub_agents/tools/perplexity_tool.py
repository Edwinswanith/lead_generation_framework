import asyncio
from typing import Dict, Any
import os
from dotenv import load_dotenv
import httpx
import json
import re

load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

def extract_json_object(text: str) -> str:
    """
    Extract the first valid JSON object from a text string.
    Handles cases where JSON is embedded in text or has extra data.
    """
    # First try to find JSON in code blocks
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        json_str = text.split("```")[1].split("```")[0]
    else:
        json_str = text
    
    json_str = json_str.strip()
    
    # Try to find a JSON object using regex
    json_pattern = r'\{[^{}]*\}'
    # This pattern finds nested JSON objects
    nested_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    
    # First try simple pattern
    match = re.search(json_pattern, json_str)
    if match:
        try:
            json.loads(match.group())
            json_str = match.group()
        except:
            # If simple pattern fails, try nested pattern
            match = re.search(nested_pattern, json_str)
            if match:
                json_str = match.group()
    
    # If regex doesn't work, try brace counting
    if json_str.startswith('{'):
        brace_count = 0
        in_string = False
        escape = False
        for i, char in enumerate(json_str):
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = json_str[:i+1]
                        break
    
    return json_str

async def perplexity_research_tool(company_name: str, website: str) -> Dict[str, Any]:
    """
    Research company information using Perplexity AI API.
    """
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    query = """Research the following company and provide information in JSON format:
    Company Name: {}
    Website: {}

    Find:
    1. Leadership & Contact:
       - CEO name
       - CEO email
       - Company headquarters

    2. Business Metrics:
       - Annual revenue/revenue range
       - Number of employees
       - Year founded

    3. Market Focus:
       - Primary target industries
       - Target company sizes
       - Geographical focus
       - Notable clients
       - Core services/products

    Format response as JSON with these keys:
    {{
        "ceo_name": "string",
        "ceo_email": "string",
        "company_revenue": "string",
        "company_employee_count": "string",
        "company_founding_year": "string",
        "target_industries": ["string"],
        "target_company_size": ["string"],
        "target_geography": ["string"],
        "client_examples": ["string"],
        "service_focus": ["string"]
    }}""".format(company_name, website)

    # Configure timeout and retries
    timeout = httpx.Timeout(30.0, connect=5.0)  # 30 seconds total, 5 seconds connect
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json={
                        "model": "sonar",
                        "messages": [
                            {"role": "system", "content": "You are a corporate research assistant. Always return responses in valid JSON format."},
                            {"role": "user", "content": query}
                        ]
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"Perplexity API error: {response.text}")

                try:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Extract JSON from the response
                    json_str = extract_json_object(content)
                    
                    data = json.loads(json_str)
                    
                    # Ensure all required fields exist with default empty values
                    default_data = {
                        "ceo_name": "",
                        "ceo_email": "",
                        "company_revenue": "",
                        "company_employee_count": "",
                        "company_founding_year": "",
                        "target_industries": [],
                        "target_company_size": [],
                        "target_geography": [],
                        "client_examples": [],
                        "service_focus": []
                    }
                    
                    # Update default data with any found values
                    default_data.update(data)
                    
                    return default_data
                    
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    print(f"Error parsing Perplexity response: {e}")
                    return {
                        "ceo_name": "",
                        "ceo_email": "",
                        "company_revenue": "",
                        "company_employee_count": "",
                        "company_founding_year": "",
                        "target_industries": [],
                        "target_company_size": [],
                        "target_geography": [],
                        "client_examples": [],
                        "service_focus": []
                    }
                    
        except httpx.ReadTimeout:
            print(f"Timeout on attempt {attempt + 1} for {company_name}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                print(f"All retries exhausted for {company_name}")
                # Return empty data on timeout
                return {
                    "ceo_name": "",
                    "ceo_email": "",
                    "company_revenue": "",
                    "company_employee_count": "",
                    "company_founding_year": "",
                    "target_industries": [],
                    "target_company_size": [],
                    "target_geography": [],
                    "client_examples": [],
                    "service_focus": []
                }
        except Exception as e:
            print(f"Error on attempt {attempt + 1} for {company_name}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                raise

FIELD_PROMPTS = {
    "ceo_name": "CEO name",
    "ceo_email": "CEO email",
    "company_revenue": "Annual revenue/revenue range",
    "company_employee_count": "Number of employees",
    "company_founding_year": "Year founded",
    "target_industries": "Primary target industries",
    "target_company_size": "Target company sizes",
    "target_geography": "Geographical focus",
    "client_examples": "Notable clients",
    "service_focus": "Core services/products"
}

async def get_specific_info_tool(company_name: str, website: str, fields_to_find: list[str]) -> Dict[str, Any]:
    """
    Research specific company information fields using Perplexity AI API.
    """
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    find_section = "\n".join([f"       - {FIELD_PROMPTS[field]}" for field in fields_to_find if field in FIELD_PROMPTS])
    json_keys = ",\n".join([f'        "{field}": "string or [string]"' for field in fields_to_find])

    query = f"""Research the following company and provide information in JSON format:
    Company Name: {company_name}
    Website: {website}

    Find ONLY the following information:
{find_section}

    Format response as a single JSON object with these keys:
    {{
{json_keys}
    }}
    
    If you cannot find a specific piece of information, return an empty string or empty list for that key."""

    # Configure timeout and retries
    timeout = httpx.Timeout(30.0, connect=5.0)  # 30 seconds total, 5 seconds connect
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json={
                        "model": "sonar",
                        "messages": [
                            {"role": "system", "content": "You are a corporate research assistant. Always return responses in valid JSON format."},
                            {"role": "user", "content": query}
                        ]
                    }
                )

            if response.status_code != 200:
                raise Exception(f"Perplexity API error: {response.text}")

            try:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Extract JSON from the response
                json_str = extract_json_object(content)
                
                data = json.loads(json_str)
                
                default_data = {key: "" for key in fields_to_find}
                for key in default_data:
                    if isinstance(default_data[key], list):
                        default_data[key] = []

                default_data.update(data)
                
                return default_data
                
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                print(f"Error parsing Perplexity response for specific fields: {e}")
                return {key: "" for key in fields_to_find}
                
        except httpx.ReadTimeout:
            print(f"Timeout on attempt {attempt + 1} for specific info on {company_name}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                print(f"All retries exhausted for specific info on {company_name}")
                # Return empty data on timeout
                return {key: "" for key in fields_to_find}
        except Exception as e:
            print(f"Error on attempt {attempt + 1} for specific info on {company_name}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                raise