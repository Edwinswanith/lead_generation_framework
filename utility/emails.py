import os
import re
import smtplib
import time
import csv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import json
import pandas as pd
from dotenv import load_dotenv
import asyncio
import eventlet
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agent.sub_agents.agent import create_email_sequence_agent, create_follow_up_agent
from agent.sub_agents.tools.perplexity_tool import extract_json_object

# MCP imports for Gmail draft functionality
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

APP_NAME = "email_content_app"
USER_ID = "email_user"

# MCP server configuration
MCP_SERVER_URL = "https://mcp.zapier.com/api/mcp/s/YTI2MDQwYWItZjBjNi00OWEyLTg1MDktOGM5YTdiODk3NTE1Ojc2ZTc1MzI4LWI3ZjctNDA5MC04YjYyLTEwNzlhZTg3YWYzYw==/mcp"
# MCP_SERVER_URL = "https://mcp.zapier.com/api/mcp/s/M2RkZDgyMDUtN2U1Yy00MDM3LTljM2MtZDI2N2ViOWQxYjM4OjcxNGEyYTRkLWM4NTEtNGRiZS05YjRmLTcxNmU3NTAxOTRhOQ==/mcp"



def _save_email_content_json(session_dir: str, email: str, subject: str, body: str) -> None:
    """Persist email subject/body keyed by recipient email in a JSON file under the session directory."""
    try:
        os.makedirs(session_dir, exist_ok=True)
        json_path = os.path.join(session_dir, 'email_contents.json')
        data = {}
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}
        data[email] = {
            'subject': subject,
            'body': body,
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to save email content JSON for {email}: {e}")


async def create_gmail_draft_via_mcp(to_email: str, subject: str, body: str) -> dict:
    """Create a Gmail draft using MCP (Model Context Protocol)."""
    try:
        # Use streamablehttp_client to get streams for MCP communication
        async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, get_session_id):
            # Initialize the client session with the streams
            async with ClientSession(read_stream, write_stream) as client:
                print(f"MCP Client connected successfully")
                
                # Initialize the session
                await client.initialize()
                
                # List available tools first (optional, for debugging)
                try:
                    tools_result = await client.list_tools()
                    available_tools = [tool.name for tool in tools_result.tools]
                    print(f"Available tools: {available_tools}")
                except Exception as e:
                    print(f"Warning: Could not list tools: {e}")
                
                # Call gmail_create_draft tool with parameters
                result = await client.call_tool(
                    "gmail_create_draft",
                    {
                        "instructions": "Execute the Gmail: Create Draft tool with the following parameters",
                        "body": body,
                        "subject": subject,
                        "to": to_email
                    }
                )
                
                # Parse the result
                if result and result.content:
                    # Extract text content from the result
                    content_text = ""
                    for content in result.content:
                        if hasattr(content, 'text'):
                            content_text += content.text
                    
                    if content_text:
                        try:
                            json_result = json.loads(content_text)
                            # print(f"Gmail draft created successfully: {json_result}")
                            return {"success": True, "result": json_result}
                        except json.JSONDecodeError:
                            print(f"Non-JSON response: {content_text}")
                            return {"success": True, "result": content_text}
                    else:
                        return {"success": False, "error": "Empty content in result"}
                else:
                    return {"success": False, "error": "No result returned from MCP"}
                
    except Exception as e:
        print(f"Error creating Gmail draft via MCP: {e}")
        return {"success": False, "error": str(e)}

def is_missing_timestamp(value) -> bool:
    return pd.isna(value) or (isinstance(value, str) and value.strip() == '')

def check_company_cooldown(company_name: str, summary_path: str) -> bool:
    """
    Check if the company is within the 3-day cooldown period.
    Returns True if company can be emailed (cooldown expired), False otherwise.
    """
    if not os.path.exists(summary_path):
        return True

    try:
        df = pd.read_csv(summary_path)
        if df.empty:
            return True

        # Get all rows for this company
        company_emails = df[df['Company Name'] == company_name]
        if company_emails.empty:
            return True

        # Get the most recent email date
        sent_dates = []
        for col in ['1st Email Sent', '2nd Email Sent', '3rd Email Sent']:
            dates = company_emails[col].dropna()
            if not dates.empty:
                sent_dates.extend(dates.tolist())

        if not sent_dates:
            return True

        # Convert dates to datetime objects
        sent_dates = [datetime.strptime(date, '%Y-%m-%d %H:%M:%S') for date in sent_dates if date.strip()]
        if not sent_dates:
            return True

        last_sent = max(sent_dates)
        cooldown_period = timedelta(days=3)
        return datetime.now() - last_sent >= cooldown_period

    except Exception as e:
        print(f"Error checking cooldown: {e}")
        return True  # If there's an error reading the file, allow sending to be safe

async def generate_email_content(company_data: dict) -> tuple[str, str]:
    """Generate email content using the email content agent."""
    try:
        sess_svc = InMemorySessionService()
        agent = create_email_sequence_agent()
        
        # Load environment variables for sender info
        load_dotenv()
        sender_name = os.getenv("SENDER_NAME", "Bizzzup Team")
        sender_role = os.getenv("SENDER_ROLE", "Business Development & Strategic Partnerships")
        
        # Create initial state with company data and sender info
        initial_state = {
            "company_name": company_data.get('company_name', ''),
            "ceo_name": company_data.get('ceo_name', ''),
            "service_focus": company_data.get('service_focus', ''),
            "target_industries": company_data.get('target_industries', ''),
            "client_examples": company_data.get('client_examples', ''),
            "email": company_data.get('email', ''),
            "sender_name": sender_name,
            "sender_role": sender_role
        }
        
        session_data = await sess_svc.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=str(time.time()),
            state=initial_state
        )

        runner = Runner(agent=agent, app_name=APP_NAME, session_service=sess_svc)
        content = None

        # Create message using google.genai.types.Content
        from google.genai import types
        message = types.Content(
            role="user",
            parts=[types.Part(text="Generate email content")]
        )

        try:
            async for ev in runner.run_async(
                user_id=USER_ID,
                session_id=session_data.id,
                new_message=message
            ):
                if ev.is_final_response() and ev.content and ev.content.parts:
                    content = ev.content.parts[0].text
                    break

            if not content:
                print("No content generated by the agent")
                return None, None

            # Extract JSON object robustly (handles fenced code and extra text)
            content = extract_json_object(content)

            content_json = json.loads(content)
            subject = content_json.get("subject")
            body = content_json.get("body")
            
            if not subject or not body:
                print("Missing subject or body in generated content")
                return None, None
                
            return subject, body

        except json.JSONDecodeError as e:
            print(f"Error parsing agent response as JSON: {e}")
            print(f"Raw content: {content}")
            return None, None
        finally:
            # Clean up the runner and its resources
            try:
                if hasattr(runner, '_client') and runner._client is not None:
                    # Avoid closing if the event loop is closed
                    loop = asyncio.get_running_loop()
                    if not loop.is_closed():
                        try:
                            await runner._client.aclose()
                            # Give the loop a moment to process transport close callbacks
                            await asyncio.sleep(0)
                        except RuntimeError as e:
                            if 'Event loop is closed' in str(e):
                                pass
                            else:
                                raise
                    # Prevent any destructor from attempting to close again on a closed loop
                    try:
                        runner._client = None
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error closing runner client: {e}")
            
    except Exception as e:
        print(f"Error generating email content: {e}")
        return None, None

async def generate_follow_up_content(company_data: dict, previous_subject: str) -> tuple[str, str]:
    """Generate follow-up email content using the follow-up agent."""
    try:
        sess_svc = InMemorySessionService()
        agent = create_follow_up_agent()
        
        # Load environment variables for sender info
        load_dotenv()
        sender_name = os.getenv("SENDER_NAME", "Bizzzup Team")
        sender_role = os.getenv("SENDER_ROLE", "Business Development & Strategic Partnerships")
        
        # Create initial state with company data and sender info
        initial_state = {
            "company_name": company_data.get('company_name', ''),
            "ceo_name": company_data.get('ceo_name', ''),
            "company_info": company_data,
            "previous_subject": previous_subject,
            "sender_name": sender_name,
            "sender_role": sender_role
        }
        
        session_data = await sess_svc.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=str(time.time()),
            state=initial_state
        )

        runner = Runner(agent=agent, app_name=APP_NAME, session_service=sess_svc)
        content = None

        # Create message using google.genai.types.Content
        from google.genai import types
        message = types.Content(
            role="user",
            parts=[types.Part(text="Generate follow-up email content")]
        )

        try:
            async for ev in runner.run_async(user_id=USER_ID, session_id=session_data.id, new_message=message):
                if ev.is_final_response() and ev.content and ev.content.parts:
                    content = ev.content.parts[0].text
                    break

            if content:
                try:
                    # Extract JSON object robustly (handles fenced code and extra text)
                    content = extract_json_object(content)
                    content_json = json.loads(content)
                    return content_json.get('subject'), content_json.get('body')
                except json.JSONDecodeError:
                    print(f"Error parsing JSON from content: {content}")
                    return None, None
            
            return None, None

        except Exception as e:
            print(f"Error in follow-up agent: {e}")
            return None, None
        finally:
            # Clean up the runner and its resources (mirror generate_email_content)
            try:
                if hasattr(runner, '_client') and runner._client is not None:
                    loop = asyncio.get_running_loop()
                    if not loop.is_closed():
                        try:
                            await runner._client.aclose()
                            # Give the loop a moment to flush transport close callbacks
                            await asyncio.sleep(0)
                        except RuntimeError as e:
                            if 'Event loop is closed' in str(e):
                                pass
                            else:
                                raise
                    # Prevent any destructor from attempting to close again on a closed loop
                    try:
                        runner._client = None
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error closing runner client (follow-up): {e}")
        
    except Exception as e:
        print(f"Error generating follow-up email content: {e}")
        return None, None

async def send_emails_task(session_id: str, companies_path: str, mode: str, socketio, app, rank_min=None, rank_max=None, selected_emails=None):
    """Background task to send emails."""
    
    try:
        load_dotenv()
        sender_name = os.getenv("SENDER_NAME", "Bizzzup Team")
        sender_role = os.getenv("SENDER_ROLE", "Business Development & Strategic Partnerships")

        # Create session directory in files folder
        session_dir = os.path.join(app.config['BASE_DIR'], 'files', session_id)
        os.makedirs(session_dir, exist_ok=True)

        # Create email summary file path
        summary_path = os.path.join(session_dir, 'email_summary.csv')

        # Create summary file with headers if it doesn't exist
        if not os.path.exists(summary_path):
            with open(summary_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Company Name', 'Email', 'CEO Name', 'Subject', '1st Email Sent', '2nd Email Sent', '3rd Email Sent'])

        # Read the companies CSV file
        try:
            df = pd.read_csv(companies_path)
            
            # If explicit selections exist, filter by them and ignore ranking
            if selected_emails and isinstance(selected_emails, list) and len(selected_emails) > 0:
                lower_set = set([str(e).strip().lower() for e in selected_emails])
                email_col_candidates = ['CEO Email', 'Email']
                email_col = next((c for c in email_col_candidates if c in df.columns), None)
                if email_col:
                    df = df[df[email_col].astype(str).str.strip().str.lower().isin(lower_set)]
            else:
                # Apply ranking filter if provided
                if rank_min is not None or rank_max is not None:
                    if 'Ranking' in df.columns:
                        ranking_series = pd.to_numeric(df['Ranking'], errors='coerce')
                    else:
                        ranking_series = pd.Series([None] * len(df), index=df.index, dtype=float)
                    _min = float('-inf') if rank_min is None else rank_min
                    _max = float('inf') if rank_max is None else rank_max
                    mask = (ranking_series >= _min) & (ranking_series <= _max)
                    df = df[mask]
        except Exception as e:
            socketio.emit('email_progress', {
                'status': {
                    'success': False,
                    'message': f'Error reading CSV file: {str(e)}',
                    'company_name': 'System'
                }
            }, room=session_id)
            return

        # Define the email column - check both CEO Email and Email columns
        email_column = next((col for col in df.columns if col in ['CEO Email', 'Email']), None)
        if not email_column:
            socketio.emit('email_progress', {
                'status': {
                    'success': False,
                    'message': 'No email column found in the CSV file',
                    'company_name': 'System'
                }
            }, room=session_id)
            return

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        # Read the email summary file
        summary_df = pd.read_csv(summary_path) if os.path.exists(summary_path) else pd.DataFrame(columns=['Company Name', 'Email', 'CEO Name', 'Subject', '1st Email Sent', '2nd Email Sent', '3rd Email Sent'])
        
        # Ensure date columns are using pandas nullable string dtype to preserve missing values
        if not summary_df.empty:
            for col in ['1st Email Sent', '2nd Email Sent', '3rd Email Sent']:
                if col in summary_df.columns:
                    summary_df[col] = summary_df[col].astype('string')
            # Normalize empty strings to NA for consistent missing checks
            date_cols = [c for c in ['1st Email Sent', '2nd Email Sent', '3rd Email Sent'] if c in summary_df.columns]
            if date_cols:
                summary_df[date_cols] = summary_df[date_cols].replace(r'^\s*$', pd.NA, regex=True)

        # Get all rows with valid emails
        valid_rows = []
        for _, row in df.iterrows():
            email = str(row[email_column]).strip()
            if pd.isna(email) or not re.match(email_pattern, email):
                continue

            company_data = {
                'company_name': row.get('Company Name', ''),
                'email': email,
                'ceo_name': row.get('CEO Name', ''),
                'service_focus': row.get('Service Focus', ''),
                'target_industries': row.get('Target Industries', ''),
                'client_examples': row.get('Client Examples', '')
            }
            valid_rows.append(company_data)

        total_emails = len(valid_rows)
        processed_count = 0
        skipped_count = 0

        # Process each company
        for company_data in valid_rows:
            try:
                # Check if we have a record for this company
                company_name_norm = str(company_data['company_name']).strip().lower()
                email_norm = str(company_data['email']).strip().lower()
                if not summary_df.empty and 'Company Name' in summary_df.columns and 'Email' in summary_df.columns:
                    name_norm_series = summary_df['Company Name'].astype(str).str.strip().str.lower()
                    email_norm_series = summary_df['Email'].astype(str).str.strip().str.lower()
                    mask = (name_norm_series == company_name_norm) & (email_norm_series == email_norm)
                    company_record = summary_df[mask]
                else:
                    company_record = pd.DataFrame()
                is_follow_up = not company_record.empty

                # For follow-up mode, skip companies without previous emails
                if mode == 'follow-up' and not is_follow_up:
                    skipped_count += 1
                    socketio.emit('email_progress', {
                        'progress': {
                            'sent': processed_count,
                            'total': total_emails - skipped_count,
                            'action': mode
                        },
                        'status': {
                            'success': False,
                            'message': 'Skipped - No previous email sent',
                            'company_name': company_data['company_name']
                        }
                    }, room=session_id)
                    continue

                # Skip if within cooldown period
                if not check_company_cooldown(company_data['company_name'], summary_path):
                    skipped_count += 1
                    socketio.emit('email_progress', {
                        'progress': {
                            'sent': processed_count,
                            'total': total_emails - skipped_count,
                            'action': mode
                        },
                        'status': {
                            'success': False,
                            'message': 'Skipped - Within cooldown period',
                            'company_name': company_data['company_name']
                        }
                    }, room=session_id)
                    continue

                sent_time = None
                subject = None
                body = None
                email_number = None

                if mode == 'follow-up' and is_follow_up:
                    # Get the previous subject and determine which follow-up to send
                    previous_subject = company_record.iloc[0]['Subject']
                    # Determine which follow-up number to send based on missing timestamps
                    second_sent = company_record.iloc[0]['2nd Email Sent'] if '2nd Email Sent' in company_record.columns else pd.NA
                    third_sent = company_record.iloc[0]['3rd Email Sent'] if '3rd Email Sent' in company_record.columns else pd.NA
                    if is_missing_timestamp(second_sent):
                        # Generate and send second email
                        subject, body = await generate_follow_up_content(company_data, previous_subject)
                        email_number = 2
                    elif is_missing_timestamp(third_sent):
                        # Generate and send third email
                        subject, body = await generate_follow_up_content(company_data, previous_subject)
                        email_number = 3
                    else:
                        # All follow-ups sent, skip this company
                        skipped_count += 1
                        socketio.emit('email_progress', {
                            'progress': {
                                'sent': processed_count,
                                'total': total_emails - skipped_count,
                                'action': mode
                            },
                            'status': {
                                'success': False,
                                'message': 'Skipped - All follow-ups sent',
                                'company_name': company_data['company_name']
                            }
                        }, room=session_id)
                        continue
                else:
                    # Generate first email
                    if is_follow_up:
                        # First email already sent; skip creating another first email entry
                        skipped_count += 1
                        socketio.emit('email_progress', {
                            'progress': {
                                'sent': processed_count,
                                'total': total_emails - skipped_count,
                                'action': mode
                            },
                            'status': {
                                'success': False,
                                'message': 'Skipped - First email already sent',
                                'company_name': company_data['company_name']
                            }
                        }, room=session_id)
                        continue
                    
                    subject, body = await generate_email_content(company_data)
                    email_number = 1

                if not subject or not body:
                    skipped_count += 1
                    socketio.emit('email_progress', {
                        'progress': {
                            'sent': processed_count,
                            'total': total_emails - skipped_count,
                            'action': mode
                        },
                        'status': {
                            'success': False,
                            'message': 'Failed to generate email content',
                            'company_name': company_data['company_name']
                        }
                    }, room=session_id)
                    continue

                status_msg = 'Email prepared'

                # Use MCP to create Gmail drafts instead of SMTP sending
                if mode in ['draft', 'send', 'follow-up']:
                    try:
                        # Create Gmail draft using MCP
                        draft_result = await create_gmail_draft_via_mcp(
                            to_email=company_data['email'],
                            subject=subject,
                            body=body
                        )
                        
                        if draft_result['success']:
                            sent_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            # Persist subject/body for later viewing
                            _save_email_content_json(session_dir, company_data['email'], subject, body)
                            if mode == 'draft':
                                status_msg = 'Gmail draft created successfully via MCP'
                            elif mode in ['send', 'follow-up']:
                                status_msg = 'Gmail draft created successfully via MCP (ready to send)'
                        else:
                            status_msg = f'Failed to create Gmail draft: {draft_result.get("error", "Unknown error")}'
                            
                    except Exception as e:
                        print(f"MCP Error: {str(e)}")
                        status_msg = f'Failed to create Gmail draft: {str(e)}'

                # Update summary CSV
                if is_follow_up and email_number > 1:
                    # Update existing record
                    column_name = '2nd Email Sent' if email_number == 2 else '3rd Email Sent'
                    summary_df.loc[company_record.index[0], column_name] = sent_time or ''
                    summary_df.to_csv(summary_path, index=False)
                elif email_number == 1:
                    # Add new record
                    # Only record if an email was actually sent (not in draft mode)
                    if sent_time:
                        # Avoid duplicate entries if company+email already exist
                        try:
                            exists = False
                            if not summary_df.empty and 'Company Name' in summary_df.columns and 'Email' in summary_df.columns:
                                name_norm_series = summary_df['Company Name'].astype(str).str.strip().str.lower()
                                email_norm_series = summary_df['Email'].astype(str).str.strip().str.lower()
                                exists = bool(((name_norm_series == company_name_norm) & (email_norm_series == email_norm)).any())
                            if not exists:
                                with open(summary_path, 'a', newline='') as f:
                                    writer = csv.writer(f)
                                    writer.writerow([
                                        company_data['company_name'],
                                        company_data['email'],
                                        company_data['ceo_name'],
                                        subject,
                                        sent_time,  # 1st Email sent time
                                        "",        # 2nd Email (not sent yet)
                                        ""         # 3rd Email (not sent yet)
                                    ])
                        except Exception as e:
                            print(f"Error updating summary for {company_data['company_name']}: {e}")

                processed_count += 1

                # Emit progress update
                socketio.emit('email_progress', {
                    'progress': {
                        'sent': processed_count,
                        'total': total_emails - skipped_count,
                        'action': mode
                    },
                    'status': {
                        'success': bool(sent_time),
                        'message': status_msg,
                        'company_name': company_data['company_name'],
                        'email': company_data['email']
                    }
                }, room=session_id)

                # Add a small delay between emails
                await asyncio.sleep(1)

            except Exception as e:
                print(f"Error processing company {company_data['company_name']}: {str(e)}")
                continue

        # Send final summary
        socketio.emit('email_progress', {
            'status': {
                'success': True,
                'message': f'Process complete. {processed_count} emails processed.',
                'company_name': 'System',
                'summary_file': summary_path
            }
        }, room=session_id)

    except Exception as e:
        print(f"Error in send_emails_task: {str(e)}")
        socketio.emit('email_progress', {
            'status': {
                'success': False,
                'message': f'Error in email task: {str(e)}',
                'company_name': 'System'
            }
        }, room=session_id)