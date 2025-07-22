from pathlib import Path
import datetime
import re
from typing import Optional
from pydantic import BaseModel, Field
from google.adk.tools import ToolContext
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import glob


body_content = []



class EmailInput(BaseModel):
    recipient_email: str = Field(description="Recipient email")
    receiver_name: str = Field(description="Recipient name")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body (HTML)")

class EmailOutput(BaseModel):
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body content")


def get_latest_collaboration_report():
    """Get the latest collaboration report markdown file from the collaboration_reports directory."""
    # Check both possible directories
    for reports_dir in ["collaboration_reports", "Lead_scraper/collaboration_reports"]:
        reports_path = Path(reports_dir)
        if reports_path.exists():
            # Get all markdown files
            md_files = glob.glob(str(reports_path / "*_collaboration.md"))
            if md_files:
                # Sort by modification time and get the latest
                latest_file = max(md_files, key=os.path.getmtime)
                return latest_file
    
    # Fallback to manager/outputs if no collaboration reports found
    output_path = Path("manager/outputs")
    if output_path.exists():
        md_files = glob.glob(str(output_path / "company_analysis_*.md"))
        if md_files:
            latest_file = max(md_files, key=os.path.getmtime)
            return latest_file
    
    return None

def get_all_collaboration_reports():
    """Get all collaboration report markdown files from the collaboration_reports directory."""
    all_files = []
    # Check both possible directories
    for reports_dir in ["collaboration_reports", "Lead_scraper/collaboration_reports"]:
        reports_path = Path(reports_dir)
        if reports_path.exists():
            # Get all markdown files
            md_files = glob.glob(str(reports_path / "*_collaboration.md"))
            if md_files:
                all_files.extend(md_files)
    
    if all_files:
        return sorted(all_files, key=os.path.getmtime, reverse=True)

    # Fallback to manager/outputs if no collaboration reports found
    output_path = Path("manager/outputs")
    if output_path.exists():
        md_files = glob.glob(str(output_path / "company_analysis_*.md"))
        if md_files:
            return sorted(md_files, key=os.path.getmtime, reverse=True)
    
    return []

def format_collaboration_email_body(content: str, sender_name: str, sender_email: str, sender_role: str) -> str:
    """Format the collaboration markdown content into a professional HTML email."""
    content = content.strip()
    
    # Extract company name from summary title
    company_match = re.search(r'# Smart AI Integration Partnership – (.+?)$', content, re.MULTILINE)
    if not company_match:
        # Fallback for the original proposal format
        company_match = re.search(r'# Collaboration Proposal for (.+?)$', content, re.MULTILINE)
        
    company_name = company_match.group(1) if company_match else "Target Company"
    
    # Convert main title to HTML with enhanced styling
    content = re.sub(r'^# .+$', 
                    f'<h1 style="color: #1a237e; font-size: 28px; margin-bottom: 30px; font-weight: 800; text-align: center; border-bottom: 2px solid #1a237e; padding-bottom: 15px;">Smart AI Integration Partnership: {company_name} × Bizzzup</h1>', 
                    content, flags=re.MULTILINE)
    
    # Convert ## headers to styled H2
    content = re.sub(r'^## (.+?)$', 
                    r'<h2 style="color: #283593; font-size: 22px; margin: 25px 0 15px; font-weight: 700; background: linear-gradient(135deg, #e8eaf6, #f3e5f5); padding: 12px 15px; border-radius: 8px;">\1</h2>', 
                    content, flags=re.MULTILINE)
    
    # Convert ### headers to styled H3
    content = re.sub(r'^### (.+?)$', 
                    r'<h3 style="color: #3f51b5; font-size: 18px; margin: 20px 0 10px; font-weight: 600; padding-left: 10px; border-left: 3px solid #3f51b5;">\1</h3>', 
                    content, flags=re.MULTILINE)
    
    # Convert bold markdown to strong tags
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)

    # Convert bullet points to styled list items
    content = re.sub(r'^- (.+?)$', 
                    r'<li style="margin: 8px 0; color: #333; font-size: 16px; line-height: 1.6;">\1</li>', 
                    content, flags=re.MULTILINE)
    
    # Group consecutive list items into ul tags
    content = re.sub(r'(<li[^>]*>.*?</li>\s*)+', 
                    lambda m: f'<ul style="margin: 15px 0; padding-left: 25px; list-style-type: disc;">{m.group(0)}</ul>', 
                    content, flags=re.DOTALL)
    
    # Convert remaining paragraphs
    lines = content.split('\n')
    formatted_lines = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('<'):
            formatted_lines.append(f'<p style="margin: 15px 0; line-height: 1.8; color: #333; font-size: 16px;">{line}</p>')
        else:
            formatted_lines.append(line)
    
    content = '\n'.join(formatted_lines)
    
    # Add professional greeting and closing
    closing = f"""<div style="margin-top: 40px; padding-top: 25px; border-top: 2px solid #e0e0e0;">
        <p style="color: #333; font-size: 16px; margin: 15px 0; line-height: 1.8;">
            We believe this synergy presents a solid opportunity to scale your services with minimal operational overhead.
        </p>
        <p style="color: #333; font-size: 16px; margin: 15px 0; line-height: 1.8;">
            If you'd like to explore more about our work and solutions, feel free to check out our recent projects and capabilities here:
        </p>
        <p style="color: #333; font-size: 16px; margin: 10px 0 5px;">
            👉 <a href="https://www.upwork.com/nx/find-work/" style="color: #1a237e; text-decoration: none; font-weight: bold;">Upwork Portfolio</a>
        </p>
        <p style="color: #333; font-size: 16px; margin: 5px 0 25px;">
            👉 <a href="https://labs.bizzzup.com/" style="color: #1a237e; text-decoration: none; font-weight: bold;">Bizzzup Website</a>
        </p>
        <p style="color: #333; font-size: 16px; margin: 25px 0 15px;">
            Thanks for your time, and wishing you continued success.
        </p>
        <div style="margin-top: 25px;">
            <p style="color: #333; font-size: 16px; margin: 5px 0;">Best regards,</p>
            <p style="color: #1a237e; font-weight: bold; font-size: 16px; margin: 5px 0;">{sender_name}</p>
            <p style="color: #666; font-size: 14px; margin: 5px 0;">{sender_role}</p>
            <p style="color: #666; font-size: 14px; margin: 5px 0;">
                <a href="mailto:{sender_email}" style="color: #1a237e; text-decoration: none;">📧 {sender_email}</a>
            </p>
        </div>
    </div>"""
    
    # Add container styling with enhanced design
    final_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 0 auto; padding: 40px 30px; line-height: 1.6; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        {content}
        {closing}
    </div>
    """
    
    # Clean up any formatting issues
    final_content = re.sub(r'\n\s*\n', '\n', final_content)
    final_content = re.sub(r'<p>\s*</p>', '', final_content)
    
    return final_content

def send_email(
    recipient_email: str,
    receiver_name: str,
    subject: str,
    body: str,
    tool_context: ToolContext,
    report_file: Optional[str] = None
) -> dict:
    """
    Sends an email using Gmail SMTP server with collaboration report content.
    
    Args:
        recipient_email: Email address of the recipient
        receiver_name: Name of the recipient
        subject: Subject line of the email
        body: HTML content of the email body
        tool_context: ADK tool context
        report_file: Optional path to a specific report file to send.
        
    Returns:
        dict: Status of the email sending attempt
    """
    try:
        load_dotenv()
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")
        sender_name = os.getenv("SENDER_NAME")
        sender_role = os.getenv("SENDER_ROLE", "Business Development & Strategic Partnerships")
        
        if not sender_email or not sender_password:
            raise ValueError("SENDER_EMAIL and SENDER_PASSWORD environment variables must be set")
        
        if not sender_name:
            sender_name = sender_email.split('@')[0].capitalize()

        # Get the latest collaboration report
        file_to_send = report_file if report_file else get_latest_collaboration_report()
        
        if file_to_send and os.path.exists(file_to_send):
            with open(file_to_send, "r", encoding="utf-8") as f:
                content = f.read()
                body = format_collaboration_email_body(content, sender_name, sender_email, sender_role)
                # Replace recipient name placeholder
                body = body.replace("[RECIPIENT_NAME]", receiver_name)
                
                # Extract company name for subject if not provided
                if not subject or subject == "":
                    company_match = re.search(r'# Collaboration Proposal for (.+?)$', content, re.MULTILINE)
                    company_name = company_match.group(1) if company_match else "Partnership"
                    subject = f"Strategic Partnership Opportunity: {company_name}"
        else:
            return {
                "success": False,
                "message": "No collaboration report found to send",
                "filepath": "No collaboration report file found"
            }
        
        # Send email
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = f"{receiver_name} <{recipient_email}>"
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return {
            "success": True,
            "message": f"Collaboration proposal email sent successfully to {recipient_email}",
            "filepath": file_to_send,
            "subject": subject
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error sending email: {str(e)}",
            "error_type": type(e).__name__
        }

def get_body():
    """Get the content of the latest collaboration report file."""
    latest_file = get_latest_collaboration_report()
    if latest_file:
        with open(latest_file, "r", encoding="utf-8") as f:
            return f.read()
    return "No collaboration report file found"








