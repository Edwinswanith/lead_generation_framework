import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Any

import pandas as pd
from dotenv import load_dotenv
from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from typing_extensions import override
from .sub_agents.agent import create_sequential_agent
from .sub_agents.tools.read_google_docs import read_doc
from .config import MAX_RETRIES, CSV_OUTPUT, BIZZZUP_DOCUMETS
import re
import logging
import csv
from .monitoring import create_log_entry, count_tokens
from .sub_agents.tools.perplexity_tool import perplexity_research_tool

# ──────────────────────────── ENV / LOGGING ──────────────────────────────
load_dotenv()
module_logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_logging(session_id: str) -> logging.Logger:
    """Set up logging with a session-specific log file and return a new logger instance."""
    session_logger = logging.getLogger(f"{__name__}.{session_id}")
    session_logger.setLevel(logging.INFO)
    session_logger.propagate = False

    # Remove existing handlers
    if session_logger.handlers:
        for handler in session_logger.handlers:
            handler.close()
            session_logger.removeHandler(handler)

    # Create session directory
    session_dir = os.path.join(BASE_DIR, "files", session_id)
    os.makedirs(session_dir, exist_ok=True)
    log_file = os.path.join(session_dir, "logs.json")

    fh = logging.FileHandler(log_file, mode='w')
    fh.setFormatter(JsonFormatter())
    session_logger.addHandler(fh)
    
    return session_logger

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "timestamp": self.formatTime(record),
            "agent": getattr(record, 'agent', 'general'),
            "task": getattr(record, 'task', 'general_task')
        }

        if isinstance(record.msg, dict):
            log_record.update(record.msg)
        else:
            log_record["message"] = record.getMessage()
        
        return json.dumps(log_record)

def handle_final_response(event: Event, report_path: Optional[str] = None) -> None:
    """Handle the final response from an agent."""
    if not event.content or not event.content.parts:
        return
    
    content = event.content.parts[0].text if event.content.parts else None
    if not content:
        return
        
    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)

# ───────────────────────────── Configuration ─────────────────────────────
APP_NAME = "company_info_scraper_app"
USER_ID = "dev_user_01"
SESSION_ID = "company_info_scraper_session"

CSV_OUTPUT_COLS = ["Company Name", "Website", "CEO Name", "CEO Email", "Company Revenue", "Company Employee Count", "Company Founding Year", "Target Industries", "Target Company Size", "Target Geography", "Client Examples", "Service Focus", "Ranking", "Reasoning"]
DOCUMENT_CONTENT = read_doc(BIZZZUP_DOCUMETS)
KEY_TO_COLUMN_MAP = {   
    "ceo_name": "CEO Name",
    "ceo_email": "CEO Email", 
    "company_revenue": "Company Revenue",
    "company_employee_count": "Company Employee Count",
    "company_founding_year": "Company Founding Year",
    "target_industries": "Target Industries",
    "target_company_size": "Target Company Size",
    "target_geography": "Target Geography",
    "client_examples": "Client Examples", 
    "service_focus": "Service Focus",
    "ranking": "Ranking",
    "reasoning": "Reasoning"
}

# Session-state keys
STATE_INPUT_FILE = "input_file"
STATE_OUTPUT_FILE = "output_file"

# ─────────────────────── Agents for Company Research ──────────────────
class CompanyInfoExtractorAgent(BaseAgent):
    """Agent that orchestrates company information extraction and enrichment."""
    
    model_config = {"arbitrary_types_allowed": True}
    
    sequential_agent: SequentialAgent
    _sub_agents_map: Dict[str, LlmAgent]
    logger: logging.Logger
    
    def __init__(self, name: str, logger: Optional[logging.Logger] = None) -> None:
        sequential_agent = create_sequential_agent()
        
        super().__init__(
            name=name,
            sequential_agent=sequential_agent,
            sub_agents=[sequential_agent],
            logger=logger or module_logger
        )
        self._sub_agents_map = {
            agent.name: agent for agent in self.sequential_agent.sub_agents
        }

    @staticmethod
    def _load_input(path: str) -> pd.DataFrame:
        """Load input file (CSV or Excel)."""
        ext = Path(path).suffix.lower()
        if ext == ".csv":
            return pd.read_csv(path)
        if ext in {".xlsx", ".xls"}:
            return pd.read_excel(path, engine="openpyxl")
        raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse the first JSON object found inside an arbitrary text blob."""
        if not text:
            return None

        code_block_match = re.search(r"```json\s*([\s\S]*?)```", text, re.IGNORECASE)
        if code_block_match:
            candidate = code_block_match.group(1).strip()
        else:
            brace_match = re.search(r"\{[\s\S]*?\}", text)
            if not brace_match:
                return None
            candidate = brace_match.group(0).strip()

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    async def _enrich_row(self, ctx: InvocationContext, company: str, website: str) -> Dict[str, Any]:
        """Process one company row through the agent pipeline."""
        if not website.startswith(("http://", "https://")):
            website = "https://" + website.lstrip("/")

        initial_state = {
            "company_name": company,
            "website": website,
            "company_info": {
                "name": company,
                "website": website
            },
            "document_content": DOCUMENT_CONTENT,
            "ceo_name": "",
            "ceo_email": "",
            "company_revenue": "",
            "company_employee_count": "",
            "company_founding_year": "",
            "target_industries": "",
            "target_company_size": "",
            "target_geography": "",
            "client_examples": "",
            "service_focus": "",
            "ranking": "",
            "reasoning": ""
        }
        ctx.session.state.update(initial_state)

        model_name = "gemini-1.5-pro-preview-0409"
        if hasattr(self, 'sequential_agent') and self.sequential_agent.sub_agents:
            first_agent = self.sequential_agent.sub_agents[0]
            if hasattr(first_agent, "model") and first_agent.model:
                model_name = first_agent.model
        
        initial_state_str = json.dumps(ctx.session.state)
        prompt_tokens = count_tokens(initial_state_str, model_name=model_name)

        data: Optional[Dict[str, Any]] = None
        for attempt in range(MAX_RETRIES):
            try:
                aggregated: Dict[str, Any] = {}

                async for event in self.sequential_agent.run_async(ctx):
                    if not (event.content and event.content.parts):
                        continue

                    agent = self._sub_agents_map.get(event.author)
                    if not agent:
                        continue
                    
                    text_content = ""
                    for part in event.content.parts:
                        text_content += getattr(part, "text", "")
                    
                    self.logger.info({
                        "agent": agent.name,
                        "task": f'Output for {ctx.session.state.get("company_name", "Unknown")}',
                        "output": text_content,
                    })

                    parsed = self._extract_json_from_text(text_content)
                    if parsed:
                        cleaned_parsed = {k: "" if v is None else v for k, v in parsed.items()}
                        if output_key := getattr(agent, "output_key", None):
                            aggregated[output_key] = cleaned_parsed
                        else:
                            aggregated.update(cleaned_parsed)
                        ctx.session.state.update(cleaned_parsed)

                # Fallback to Perplexity tool if initial aggregation is empty
                if not aggregated:
                    self.logger.info(f"Initial agent response was empty for {company}, using Perplexity tool.", extra={'agent': self.name, 'task': 'perplexity_fallback'})
                    perplexity_data = await perplexity_research_tool(company, website)
                    cleaned_perplexity_data = {k: "" if v is None else v for k, v in perplexity_data.items()}
                    aggregated.update(cleaned_perplexity_data)
                    self.logger.info({
                        'agent': self.name,
                        'task': 'perplexity_research',
                        'data': cleaned_perplexity_data
                    })
                    ctx.session.state.update(cleaned_perplexity_data)

                ctx.session.state["aggregated_data"] = aggregated

                aggregated_str = json.dumps(aggregated)
                completion_tokens = count_tokens(aggregated_str, model_name=model_name)
                
                tools_used = [agent.name for agent in self.sequential_agent.sub_agents]
                # Add Perplexity tool to tools_used if it was used
                if not data and aggregated:
                    tools_used.append("Perplexity Research Tool")
                
                log_entry = create_log_entry(
                    agent_name=self.name,
                    task_description=f"Enriching company info for {company}",
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    output=aggregated_str,
                    tools_used=tools_used
                )
                self.logger.info(log_entry)

                data = aggregated
                break

            except Exception as e:
                self.logger.error(f"Error during enrichment attempt {attempt + 1} for '{company}': {e}", extra={'agent': self.name, 'task': 'enrichment_error'})

                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

        flat_data = {}
        if data:
            for agent_output in data.values():
                if isinstance(agent_output, dict):
                    flat_data.update(agent_output)

        default_data = {
            "ceo_name": "",
            "ceo_email": "",
            "company_revenue": "",
            "company_employee_count": "",
            "company_founding_year": "",
            "target_industries": "",
            "target_company_size": "",
            "target_geography": "",
            "client_examples": "",
            "service_focus": "",
            "ranking": "",
            "reasoning": ""
        }

        if not flat_data:
            return default_data

        result = default_data.copy()
        result.update({k: v for k, v in flat_data.items() if v is not None})
        return result

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Main execution flow."""
        input_path = ctx.session.state.get(STATE_INPUT_FILE)
        if not input_path:
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text="❌ No input file set")]))
            return

        df = self._load_input(input_path)
        for col in ["Company Name", "Website"]:
            if col not in df.columns:
                yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"❌ Missing column {col}")]))
                return

        session_id = ctx.session.id
        session_dir = os.path.join(BASE_DIR, "files", session_id)
        output_path = os.path.join(session_dir, "companies.csv")

        for idx, row in df.iterrows():
            stop_flag_path = os.path.join(session_dir, 'stop')
            if os.path.exists(stop_flag_path):
                self.logger.info(f"Stop signal detected for session {session_id}. Stopping agent.", extra={'agent': self.name, 'task': 'stop_signal'})
                break

            company = str(row["Company Name"]).strip()
            website = str(row["Website"]).strip()

            if not company or not website or pd.isna(company) or pd.isna(website):
                continue

            result = await self._enrich_row(ctx, company, website)
            
            output_row = {
                "Company Name": company,
                "Website": website
            }
            for key, col_name in KEY_TO_COLUMN_MAP.items():
                output_row[col_name] = str(result.get(key, "")) if result.get(key) is not None else ""
            
            file_exists = os.path.exists(output_path)

            with open(output_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_OUTPUT_COLS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(output_row)

        ctx.session.state[STATE_OUTPUT_FILE] = str(output_path)

        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part(text=f"✅ Done – enriched file saved to {output_path}")]
            )
        )

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

async def main(filepath: str, session_id: Optional[str] = None) -> None:
    logger = setup_logging(session_id) if session_id else module_logger
    adk_session_id = session_id or "default_session"

    sess_svc = InMemorySessionService()
    agent = CompanyInfoExtractorAgent("CompanyInfoExtractor", logger=logger)
    try:
        session_data = await sess_svc.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=adk_session_id
        )
        await sess_svc.update_session_state(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=adk_session_id,
            state={STATE_INPUT_FILE: filepath}
        )
    except:
        await sess_svc.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=adk_session_id,
            state={STATE_INPUT_FILE: filepath}
        )

    # Clear old files for this session before processing new one
    session_dir = os.path.join(BASE_DIR, 'files', adk_session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    companies_path = os.path.join(session_dir, 'companies.csv')
    if os.path.exists(companies_path):
        os.remove(companies_path)

    runner = Runner(agent=agent, app_name=APP_NAME, session_service=sess_svc)

    start_message = types.Content(role="user", parts=[types.Part(text="Start")])
    async for ev in runner.run_async(user_id=USER_ID, session_id=adk_session_id, new_message=start_message):
        if ev.is_final_response() and ev.content:
            pass
    
    logger.info("\n" + "="*50)
    logger.info("✅ Company data processing complete.")
    logger.info(f"📄 Enriched data saved to: {companies_path}")
    logger.info("="*50 + "\n")

def run_agent_async(filepath: str, session_id: str):
    asyncio.run(main(filepath, session_id))