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
from .sub_agents.agent import sequential_agent
from .sub_agents.tools.read_google_docs import read_doc
from .config import MAX_RETRIES, CSV_OUTPUT, BIZZZUP_DOCUMETS
from .sub_agents.email_sender import email_sender_agent # type: ignore
from .sub_agents.Email_content import email_content_agent
import re
import logging
from .monitoring import create_log_entry,  count_tokens, _calculate_cost


# ──────────────────────────── ENV / LOGGING ──────────────────────────────
load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False  # To prevent duplicate logs

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_logging(session_id: str):
    """Set up logging with a session-specific log file."""
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
            handler.close()

    log_dir = os.path.join(BASE_DIR, "files")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{session_id}.json")

    # JSON file handler for the frontend monitoring
    fh = logging.FileHandler(log_file, mode='w')
    fh.setFormatter(JsonFormatter())
    logger.addHandler(fh)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            log_record = record.msg
            log_record["level"] = record.levelname
            log_record["timestamp"] = self.formatTime(record)
            return json.dumps(log_record)

        return json.dumps({
            "level": record.levelname,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record),
            "agent": getattr(record, 'agent', 'general'),
            "task": getattr(record, 'task', record.getMessage())
        })

# Remove old logger setup to avoid running it at import time.

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

# ──────────────────────────── Email Integration ──────────────────────────
def send_collaboration_email():
    """Interactive function to send collaboration proposal emails."""
    from .sub_agents.tools.email_sender_tool import get_all_collaboration_reports, send_email
    from google.adk.tools import ToolContext
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.sessions import Session, InMemorySessionService
    from google.adk.agents import BaseAgent
    import uuid
    
    # Check if collaboration reports exist
    all_reports = get_all_collaboration_reports()
    if not all_reports:
        logger.error("❌ No collaboration reports found. Please run company analysis first.")
        return
    
    logger.info(f"📄 Found {len(all_reports)} collaboration reports.")
    
    for report_file in all_reports:
        logger.info(f"\n🚀 Processing report: {report_file}")
        
        # Get recipient details
        logger.info("\n📧 Email Setup")
        recipient_name = input(f"Enter recipient's full name for '{os.path.basename(report_file)}' (e.g., Jane Doe): ").strip()
        recipient_email = input(f"Enter recipient's email address for '{os.path.basename(report_file)}': ").strip()
        
        if not recipient_name or not recipient_email:
            logger.error("❌ Both the recipient's name and email are required. Skipping this report.")
            continue
        
        # Optional custom subject
        custom_subject = input("Enter custom subject (press Enter for auto-generated): ").strip()
        
        # Create dummy invocation and tool context
        session = Session(
            app_name=APP_NAME, user_id=USER_ID, id=SESSION_ID, state={}
        )
        session_service = InMemorySessionService()
        dummy_agent = BaseAgent(name="EmailSenderAgent")
        invocation_context = InvocationContext(
            session=session,
            session_service=session_service,
            invocation_id=str(uuid.uuid4()),
            agent=dummy_agent,
        )
        tool_context = ToolContext(invocation_context=invocation_context)
        
        # Send email
        logger.info(f"\n📤 Sending collaboration proposal to {recipient_email}...")
        result = send_email(
            recipient_email=recipient_email,
            receiver_name=recipient_name,
            subject=custom_subject,
            body="",  # Will be auto-generated from collaboration report
            tool_context=tool_context,
            report_file=report_file
        )
        
        if result["success"]:
            logger.info(f"✅ {result['message']}")
            logger.info(f"📄 Report used: {result['filepath']}")
            logger.info(f"📧 Subject: {result['subject']}")
        else:
            logger.error(f"❌ {result['message']}")

# ───────────────────────────── Configuration ─────────────────────────────
APP_NAME = "company_info_scraper_app"
USER_ID = "dev_user_01"
SESSION_ID = "company_info_scraper_session"
COLLABORATION_REPORTS_DIR = "collaboration_reports"

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
    
    # Pydantic model config
    model_config = {"arbitrary_types_allowed": True}
    
    # Field declarations
    sequential_agent: SequentialAgent
    _sub_agents_map: Dict[str, LlmAgent]
    
    def __init__(self, name: str) -> None:
        super().__init__(
            name=name,
            sequential_agent=sequential_agent,
            sub_agents=[sequential_agent]
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

    # ------------------------------------------------------------------
    # Helper – JSON extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse the first JSON object found inside an arbitrary text blob."""
        if not text:
            return None

        # Prefer fenced JSON block (```json ... ```)
        code_block_match = re.search(r"```json\s*([\s\S]*?)```", text, re.IGNORECASE)
        if code_block_match:
            candidate = code_block_match.group(1).strip()
        else:
            # Fallback: first {...} appearance (non-greedy)
            brace_match = re.search(r"\{[\s\S]*?\}", text)
            if not brace_match:
                return None
            candidate = brace_match.group(0)

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _format_collaboration_md(company_name: str, data: Dict[str, Any]) -> str:
        """Formats collaboration data into a Markdown string."""
        md = f"# Smart AI Integration Partnership – {company_name}\n\n"

        if "company_alignment" in data:
            md += "## Company Alignment\n"
            md += f"{data['company_alignment']['overview']}\n\n"

        if "market_edge" in data:
            md += "## Market Edge\n"
            # Insert the detailed Market Edge content as requested
            md += (
                "This section focuses on key operational areas in companies and how our AI automation interaction partnership solutions can enhance them. For each area, you can pull relevant data on how companies currently operate, then analyze how our company's AI solutions can optimize these functions:\n\n"
                "1. Sales: Understand how companies currently handle lead generation, qualification, and sales strategies. Then, explain how our AI-powered solutions can automate processes like lead enrichment, scoring, and customer segmentation to improve sales efficiency and conversion rates.\n\n"
                "2. Marketing: Research how companies approach their marketing efforts (including campaigns, targeting, and analytics). Highlight how our AI-driven tools like personalized email campaigns, automated content generation, and customer insights can boost marketing ROI.\n\n"
                "3. Operations: Pull data on the company's operational workflows and identify inefficiencies. Showcase how our AI solutions for task automation, predictive analytics for inventory management, and process optimization can streamline operations.\n\n"
                "4. Delivery: Examine how companies manage logistics, shipping, and delivery timelines. Propose AI-enhanced solutions such as route optimization, demand forecasting, and real-time tracking to improve delivery efficiency.\n\n"
                "5. Customer Support: Analyze how customer support is handled, including response times and service quality. Offer our AI-powered chatbots, ticketing systems, and sentiment analysis to improve customer interactions, speed up resolutions, and enhance satisfaction.\n\n"
                "\nProduct Services AI Integration\n"
                "This section covers AI applications for specific product services, focusing on how our AI solutions can improve areas like SEO, Ads, and PPC:\n\n"
                "SEO (Search Engine Optimization): Research how companies handle SEO, including keyword targeting, on-page optimization, and content strategy. Propose how our AI tools can assist with automated content creation, keyword analysis, and real-time SEO performance tracking.\n\n"
                "Ads: Understand the strategies companies use for online advertising (display ads, social media ads, etc.). Explain how our AI can optimize ad targeting, bidding strategies, and real-time campaign adjustments for better cost-per-click (CPC) and return on investment (ROI).\n\n"
                "PPC (Pay-Per-Click): Investigate how companies manage PPC campaigns, including keyword selection, budget allocation, and performance analysis. Showcase how our AI-powered solutions for automated bid management, keyword suggestions, and data-driven insights can maximize ad spend effectiveness.\n\n"
                "By pulling relevant data from these areas, you can tailor our AI solutions to help companies enhance these functions through automation and optimization, offering a competitive edge and increasing their efficiency in these core business areas.\n\n"
            )

        if "top_benefits" in data and data["top_benefits"]["advantages"]:
            md += "## Top Benefits\n"
            md += "\n".join(f"- {item}" for item in data["top_benefits"]["advantages"]) + "\n\n"

        if "bizzzup_walkthrough" in data:
            md += "## Bizzzup Walkthrough\n"
            overview = data['bizzzup_walkthrough']['overview']
            # Remove the old sentence if present
            overview = overview.replace(
                "For more details, please visit our website and explore our portfolio where you will find examples of our successful collaborations and the impact we have created.",
                "If you'd like to explore more about our work and solutions, feel free to check out our recent projects and capabilities here:"
            )
            # Add the new synergy sentence at the end
            if not overview.strip().endswith("We believe this synergy presents a solid opportunity to scale your services with minimal operational overhead."):
                overview = overview.strip() + "\n\nWe believe this synergy presents a solid opportunity to scale your services with minimal operational overhead."
            md += f"{overview}\n\n"

        return md

    @staticmethod
    def _save_collaboration_report(company_name: str, data: Dict[str, Any]):
        """Saves collaboration data to a markdown file."""
        if not data:
            return
        
        # Sanitize company name for filename
        safe_company_name = re.sub(r'[\\/*?:"<>|]', "", company_name)
        report_path = Path(COLLABORATION_REPORTS_DIR) / f"{safe_company_name}_collaboration.md"
        
        md_content = CompanyInfoExtractorAgent._format_collaboration_md(company_name, data)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Collaboration report saved to {report_path}")

    async def _send_email_with_content(self, ctx: InvocationContext, proposal: Dict[str, Any]) -> None:
        """Generates email content and sends the email."""
        ctx.session.state["collaboration_proposal"] = proposal
        email_content_events = []
        async for event in email_content_agent.run_async(ctx):
            email_content_events.append(event)
        if not email_content_events:
            logger.error("❌ Failed to generate email content.")
            return
        email_content_res = email_content_events[-1]

        text_content = ""
        if email_content_res.content and email_content_res.content.parts:
            text_content = "".join(
                part.text for part in email_content_res.content.parts if hasattr(part, "text")
            )

        email_content = self._extract_json_from_text(text_content)
        if not email_content:
            logger.error("❌ Failed to generate email content.")
            logger.error(f"DEBUG: Failed to parse JSON from content: {text_content}")
            return

        # Assuming email_sender_agent is available and configured
        ctx.session.state["subject"] = email_content.get("subject", "Collaboration Proposal")
        ctx.session.state["body"] = email_content.get("body")
        # a more robust solution would be to get the recipient from the company info
        ctx.session.state["recipient_email"] = "test@example.com" 

        email_sender_events = []
        async for event in email_sender_agent.run_async(ctx):
            email_sender_events.append(event)
        logger.info("✅ Email sent successfully.")

    async def _enrich_row(self, ctx: InvocationContext, company: str, website: str) -> Dict[str, Any]:
        """Process one company row through the agent pipeline."""
        if not website.startswith(("http://", "https://")):
            website = "https://" + website.lstrip("/")

        # Update context state with company info
        ctx.session.state.update({
            "company_name": company,
            "website": website,
            "company_info": {
                "name": company,
                "website": website
            },
            "document_content": DOCUMENT_CONTENT
        })

        # Token monitoring
        model_name = "gemini-1.5-pro-preview-0409" # Default model
        if self.sequential_agent.sub_agents:
            first_agent = self.sequential_agent.sub_agents[0]
            if hasattr(first_agent, "model") and first_agent.model:
                model_name = first_agent.model
        
        initial_state_str = json.dumps(ctx.session.state)
        prompt_tokens = count_tokens(initial_state_str, model_name=model_name)


        data: Optional[Dict[str, Any]] = None
        for attempt in range(MAX_RETRIES):
            try:
                # Aggregate JSON snippets returned by ALL sub-agents in the sequential pipeline
                aggregated: Dict[str, Any] = {}

                async for event in self.sequential_agent.run_async(ctx):
                    if not (event.content and event.content.parts):
                        continue

                    agent = self._sub_agents_map.get(event.author)
                    if not agent:
                        continue

                    # The output key for the entire agent's output is used to store
                    # the parsed JSON back into the context state for subsequent agents.
                    output_key = getattr(agent, "output_key", None)
                    
                    for part in event.content.parts:
                        text_content = getattr(part, "text", "")
                        logger.info(f"Agent '{agent.name}' produced output.", extra={'agent': agent.name, 'task': text_content})
                        parsed = self._extract_json_from_text(text_content)
                        if parsed:
                            # Merge keys from this partial result into the aggregated dict
                            if output_key:
                                aggregated[output_key] = parsed
                            else:
                                aggregated.update(parsed)
                            
                            # Update context state for subsequent agents
                            if output_key:
                                ctx.session.state[output_key] = parsed
                            else:
                                ctx.session.state.update(parsed)

                # Persist the final aggregated results
                ctx.session.state["aggregated_data"] = aggregated

                # Token monitoring
                aggregated_str = json.dumps(aggregated)
                completion_tokens = count_tokens(aggregated_str, model_name=model_name)
                
                # Here we assume all sub-agents in a sequence contribute to one "task"
                # for a given company. A more granular approach would require ADK changes.
                tools_used = [agent.name for agent in self.sequential_agent.sub_agents]
                
                log_entry = create_log_entry(
                    agent_name=self.name,
                    task_description=f"Enriching company info for {company}",
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    output=aggregated_str,
                    tools_used=tools_used
                )
                logger.info(log_entry)


                # Save the collaboration report
                if "collaboration_proposal" in aggregated:
                    self._save_collaboration_report(company, aggregated["collaboration_proposal"])
                    # Send email with the new content
                    await self._send_email_with_content(ctx, aggregated["collaboration_proposal"])

                data = aggregated
                break  # Exit retry loop on success

            except Exception as e:
                logger.error(f"Error during enrichment attempt {attempt + 1} for '{company}': {e}", extra={'agent': self.name, 'task': 'enrichment_error'})
                # Fallback to a simpler agent if the primary fails
                if attempt == 0:  # First failure
                    logger.error("Fallback: trying to send a generic email.", extra={'agent': self.name, 'task': 'fallback'})
                    await self._send_email_with_content(ctx, {})
                    break  # Email sent, no need to retry.

                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)  # Exponential backoff, starting with 2 seconds
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

        # Flatten the aggregated data from multiple agents
        flat_data = {}
        if data:
            for agent_output in data.values():
                if isinstance(agent_output, dict):
                    flat_data.update(agent_output)

        # Return default values if no data parsed
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

        # Merge parsed data with defaults for missing fields
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

        os.makedirs(COLLABORATION_REPORTS_DIR, exist_ok=True)

        df = self._load_input(input_path)
        for col in ["Company Name", "Website"]:
            if col not in df.columns:
                yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"❌ Missing column {col}")]))
                return

        output_path = Path.cwd() / CSV_OUTPUT

        # Process rows and collect enriched data
        enriched_data = []
        for idx, row in df.iterrows():
            company = str(row["Company Name"]).strip()
            website = str(row["Website"]).strip()

            if not company or not website or pd.isna(company) or pd.isna(website):
                continue

            result = await self._enrich_row(ctx, company, website)
            
            output_row = {
                "Company Name": company,
                "Website": website
            }
            # Add enriched data
            for key, col_name in KEY_TO_COLUMN_MAP.items():
                output_row[col_name] = str(result.get(key, "")) if result.get(key) is not None else ""
            
            # Save to CSV after each row is processed
            output_df = pd.DataFrame([output_row], columns=CSV_OUTPUT_COLS)
            
            # Use the session_id from the context for the output filename
            session_id = ctx.session.id
            output_path = Path.cwd() / "files" / f"{session_id}.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not os.path.exists(output_path):
                output_df.to_csv(output_path, index=False, mode='w')
            else:
                output_df.to_csv(output_path, index=False, mode='a', header=False)

        # Save output
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
    if session_id:
        setup_logging(session_id)
        adk_session_id = session_id
    else:
        # Fallback to a default session ID if none is provided
        adk_session_id = "default_session"
        setup_logging(adk_session_id)

    agent = CompanyInfoExtractorAgent("CompanyInfoExtractor")
    sess_svc = InMemorySessionService()

    await sess_svc.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=adk_session_id,
        state={STATE_INPUT_FILE: filepath}
    )
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=sess_svc)

    start_message = types.Content(role="user", parts=[types.Part(text="Start")])
    async for ev in runner.run_async(user_id=USER_ID, session_id=adk_session_id, new_message=start_message):
        if ev.is_final_response() and ev.content:
            pass
    
    logger.info("\n" + "="*50)
    logger.info("✅ Company data processing complete.")
    logger.info(f"📄 Enriched data saved to: {CSV_OUTPUT}")
    logger.info("="*50 + "\n")

    if not session_id:
        while True:
            choice = input("Would you like to send the collaboration proposal email now? (yes/no): ").lower().strip()
            if choice in ["yes", "y"]:
                send_collaboration_email()
                break
            elif choice in ["no", "n"]:
                logger.info("Skipping email. Exiting program.")
                break
            else:
                logger.error("Invalid choice. Please enter 'yes' or 'no'.")

def run_agent_async(filepath: str, session_id: str):
    asyncio.run(main(filepath, session_id))  

