import asyncio
from typing import Dict, Any
import os
from dotenv import load_dotenv
import httpx
import json

load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

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

    query = f"""Research the company {company_name} (website: {website}) and provide:
    1. CEO name and email
    2. Company revenue 
    3. Number of employees
    4. Target industries they serve
    Format the response as JSON with these keys: ceo_name, ceo_email, company_revenue, company_employee_count, target_industries"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json={
                "model": "pplx-7b-chat",
                "messages": [{"role": "user", "content": query}]
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Perplexity API error: {response.text}")

        try:
            result = response.json()
            content = result['choices'][0]['message']['content']
            data = json.loads(content)
            
            # Ensure all required fields exist with default empty strings
            return {
                "ceo_name": data.get("ceo_name", ""),
                "ceo_email": data.get("ceo_email", ""),
                "company_revenue": data.get("company_revenue", ""),
                "company_employee_count": data.get("company_employee_count", ""),
                "target_industries": data.get("target_industries", "")
            }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing Perplexity response: {e}")
            return {
                "ceo_name": "",
                "ceo_email": "",
                "company_revenue": "",
                "company_employee_count": "",
                "target_industries": ""
            }