from pathlib import Path
import datetime
import re
from pydantic import BaseModel, Field
from google.adk.tools import ToolContext
import os

class EmailInput(BaseModel):
    recipient_email: str = Field(description="Recipient email")
    receiver_name: str = Field(description="Recipient name")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body (HTML)")

class EmailOutput(BaseModel):
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body content")

def get_body(content: dict) -> str:
    """
    Extracts and formats the body content from the input dictionary.
    
    Args:
        content: Dictionary containing email content data
        
    Returns:
        str: Formatted email body content
    """
    # Extract company name from the content
    company_name = content.get("company_name", "Company Research")
    
    # Format body sections
    sections = []
    
    # Add greeting
    sections.append(f"Dear {content.get('recipient_name', '[Name]')},\n")
    
    # Add introduction
    intro = f"Following up on our research into {company_name}, here's a comprehensive analysis of the company based on our research framework."
    sections.append(f"{intro}\n")
    
    # Add company overview
    if "company_overview" in content:
        sections.append("1. Company Overview")
        for key, value in content["company_overview"].items():
            sections.append(f"*   **{key}:** {value}")
        sections.append("")
    
    # Add closing
    sections.append("We hope this analysis provides valuable insights into the company. Please let us know if you need any additional information or have questions about specific aspects of the analysis.\n")
    sections.append("Best regards,\n[SENDER_NAME]\n[SENDER_ROLE]")
    
    # Join all sections
    return "\n".join(sections)

def format_adk_output_to_markdown(content: dict) -> tuple[str, str]:
    """
    Formats ADK web output into a structured markdown format.
    
    Args:
        content: Dictionary containing ADK web output data
        
    Returns:
        tuple: (subject, formatted_body)
    """
    # Extract company name from the content
    company_name = content.get("company_name", "Company Research")
    
    # Create subject
    subject = f"{company_name} Company Analysis Report"
    
    # Get formatted body
    formatted_body = get_body(content)
    
    return subject, formatted_body

def save_email_output_as_markdown(
    subject: str,
    body: str,
    filename_prefix: str = "company_analysis"
) -> str:
    """
    Saves email content as a markdown file in manager/outputs directory.
    
    Args:
        subject: Email subject
        body: Email body content
        filename_prefix: Prefix for the output filename
        
    Returns:
        str: Path to the saved markdown file
    """
    output_path = Path("manager/outputs")
    output_path.mkdir(parents=True, exist_ok=True)

    clean_subject = re.sub(r'\W+', '_', subject.lower())[:30]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{clean_subject}_{timestamp}.md"
    filepath = output_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {subject}\n\n{body}")

    return str(filepath)

def prepare_email_and_send(email: dict) -> dict:
    """
    Prepares and sends an email by saving it as markdown and formatting it.
    
    Args:
        email: Dictionary containing email details and ADK web output data
        
    Returns:
        dict: Formatted email data ready for sending
    """
    # Format ADK output into markdown
    subject, formatted_body = format_adk_output_to_markdown(email)
    
    # Save the formatted content as markdown
    markdown_file_path = save_email_output_as_markdown(
        subject=subject,
        body=formatted_body
    )

    # Read back the markdown content
    with open(markdown_file_path, "r", encoding="utf-8") as f:
        body_content = f.read()

    # Extract sender name from environment
    sender_email = os.getenv("SENDER_EMAIL", "sender@example.com")
    sender_name = sender_email.split("@")[0].capitalize()

    # Replace placeholders
    body_content = body_content.replace("[SENDER_NAME]", sender_name)
    body_content = body_content.replace("[SENDER_ROLE]", "Business Research Specialist")

    return {
        "recipient_email": email.get("recipient_email", ""),
        "receiver_name": email.get("recipient_name", ""),
        "subject": subject,
        "body": body_content
    }

def send_email(
    recipient_email: str,
    receiver_name: str,
    subject: str,
    body: str,
    tool_context: ToolContext
):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from dotenv import load_dotenv

    load_dotenv()
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = f"{receiver_name} <{recipient_email}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return {"success": True, "message": f"Email sent to {recipient_email}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to send email: {str(e)}"}
