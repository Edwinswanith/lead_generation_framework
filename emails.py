import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
import csv

def send_emails_task(session_id: str, companies_path: str, mode: str, socketio, app):
    """Background task to save emails as drafts and optionally send them."""
    load_dotenv()
    sender_email = os.getenv("SENDER_EMAIL", "sender@bizzzup.com")
    sender_password = os.getenv("SENDER_PASSWORD")
    sender_name = os.getenv("SENDER_NAME", "Bizzzup Team")
    sender_role = os.getenv("SENDER_ROLE", "Business Development & Strategic Partnerships")

    # Create session directory in files folder
    session_dir = os.path.join(app.config['BASE_DIR'], 'files', session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Read the CSV file
    try:
        df = pd.read_csv(companies_path)
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

    if mode == 'send' and (not sender_email or not sender_password):
        socketio.emit('email_progress', {
            'status': {
                'success': False,
                'message': 'Email credentials not configured in environment',
                'company_name': 'System'
            }
        }, room=session_id)
        return

    # Get all rows with valid emails
    valid_rows = []
    for index, row in df.iterrows():
        email = str(row.get(email_column, '')).strip()
        if email and re.match(email_pattern, email):
            valid_rows.append((index, row))

    total_emails = len(valid_rows)

    if total_emails == 0:
        socketio.emit('email_progress', {
            'status': {
                'success': False,
                'message': 'No valid email addresses found in the data',
                'company_name': 'System'
            }
        }, room=session_id)
        return

    processed_count = 0
    
    # Create or open summary CSV file in the session directory
    summary_path = os.path.join(session_dir, 'email_summary.csv')
    summary_exists = os.path.exists(summary_path)
    
    with open(summary_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not summary_exists:
            writer.writerow(['Company Name', 'Email', 'CEO Name', 'Subject', '1st Email Sent', '2nd Email Sent', '3rd Email Sent'])
    
    # Emit initial progress
    socketio.emit('email_progress', {
        'progress': {
            'sent': 0,
            'total': total_emails,
            'action': mode
        }
    }, room=session_id)
    
    # Process all valid emails
    for index, row in valid_rows:
        try:
            company_name = str(row.get('Company Name', ''))
            service_focus = str(row.get('Service Focus', ''))
            ceo_name = str(row.get('CEO Name', ''))
            website = str(row.get('Website', ''))
            email = str(row.get(email_column, '')).strip()

            # Generate email content
            subject, body = generate_email_content(
                company_name=company_name,
                ceo_name=ceo_name,
                service_focus=service_focus,
                website=website,
                sender_name=sender_name,
                sender_email=sender_email,
                sender_role=sender_role
            )

            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = email
            msg.attach(MIMEText(body, 'html'))

            sent_time = ""
            status_msg = 'Email prepared'

            # If mode is 'send', send the email
            if mode == 'send':
                try:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(sender_email, sender_password)
                        server.send_message(msg)
                        sent_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        status_msg = 'Email sent successfully'
                except Exception as e:
                    status_msg = f'Failed to send email: {str(e)}'

            # Update summary CSV
            with open(summary_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    company_name,
                    email,
                    ceo_name,
                    subject,
                    sent_time,  # 1st Email sent time
                    "",        # 2nd Email (not sent yet)
                    ""         # 3rd Email (not sent yet)
                ])

            processed_count += 1

            # Emit progress update
            socketio.emit('email_progress', {
                'progress': {
                    'sent': processed_count,
                    'total': total_emails,
                    'action': mode
                },
                'status': {
                    'success': bool(sent_time),
                    'message': status_msg,
                    'company_name': company_name,
                    'email': email
                }
            }, room=session_id)

        except Exception as e:
            socketio.emit('email_progress', {
                'status': {
                    'success': False,
                    'message': f'Error processing email for {company_name}: {str(e)}',
                    'company_name': company_name
                }
            }, room=session_id)

    # Final status update
    socketio.emit('email_progress', {
        'progress': {
            'sent': processed_count,
            'total': total_emails,
            'action': mode
        },
        'status': {
            'success': True,
            'message': f'Completed processing {processed_count} emails',
            'company_name': 'System',
            'summary_file': summary_path
        }
    }, room=session_id)


def generate_email_content(company_name: str, ceo_name: str, service_focus: str, 
                         website: str, sender_name: str, sender_email: str, 
                         sender_role: str) -> tuple[str, str]:
    """Generate personalized email subject and body based on company's service focus."""
    company_name = str(company_name).strip()
    ceo_name = str(ceo_name).strip()
    service_focus = str(service_focus).strip()
    website = str(website).strip()

    if ',' in service_focus:
        service_focus_list = [s.strip() for s in service_focus.split(',')]
        primary_service_focus = service_focus_list[0] if service_focus_list else ''
    else:
        primary_service_focus = service_focus

    subject = f"AI integration opportunity for {company_name}"
    first_name = ceo_name.split()[0] if ceo_name and ceo_name != 'Business Leader' else 'there'

    body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333;">
        <p style="font-size: 16px; margin: 20px 0;">Hey {first_name},</p>
        
        <p style="font-size: 16px; margin: 20px 0;">
            Seeing {company_name}'s {'focus on ' + primary_service_focus if primary_service_focus else 'innovative approach'}{' and reviewing ' + website if website and website != 'nan' and website != 'None' else ''} caught my eye.
        </p>
        
        <p style="font-size: 16px; margin: 20px 0;">
            We haven't met, but I wanted to share an idea that could potentially help {company_name} {'enhance its ' + primary_service_focus.lower() + ' capabilities' if primary_service_focus else 'accelerate its growth'}.
        </p>
        
        <p style="font-size: 16px; margin: 20px 0;">
            I'm reaching out about Bizzzup – where our AI agents handle complex automation workflows and surface key operational insights.
        </p>
        
        <p style="font-size: 16px; margin: 20px 0;">
            We help {'companies in the ' + primary_service_focus.lower() + ' space' if primary_service_focus else 'product-led companies'} achieve 35% reduction in operational costs by centralizing every step in their workflows - from data processing to customer interactions across multiple platforms.
        </p>
        
        <p style="font-size: 16px; margin: 20px 0;">
            For instance, we helped a {get_similar_industry_example(primary_service_focus)} streamline their entire operations pipeline, which led to a 42% increase in process efficiency within 3 months.
        </p>
        
        <p style="font-size: 16px; margin: 20px 0;">
            If this sounds interesting, I'd be happy to walk you through it over a short call.
        </p>
        
        <div style="margin-top: 30px;">
            <p style="font-size: 16px; margin: 5px 0;">{sender_name}</p>
            <p style="font-size: 14px; color: #666; margin: 5px 0;">{sender_role}, Bizzzup</p>
        </div>
    </div>
    """
    
    return subject, body


def get_similar_industry_example(service_focus: str) -> str:
    """Get a relevant industry example based on service focus."""
    industry_examples = {
        'cloud infrastructure': 'Singapore-based SaaS company',
        'data analytics': 'Mumbai-based analytics firm',
        'ai': 'Bengaluru-based AI startup',
        'healthcare': 'Delhi-based healthtech company',
        'digital marketing': 'Pune-based marketing agency',
        'fintech': 'Hyderabad-based fintech startup',
        'e-commerce': 'Gurugram-based e-commerce platform',
        'education': 'Chennai-based edtech company',
        'logistics': 'Kolkata-based logistics provider',
        'cybersecurity': 'Noida-based security firm'
    }
    
    if service_focus:
        service_lower = service_focus.lower()
        for key, value in industry_examples.items():
            if key in service_lower:
                return value
    
    return 'Bengaluru-based tech company' 