# Lead Generation System

## Overview
The Lead Generation System is an AI-powered application that automates the process of generating and engaging with business leads. It combines web scraping, data enrichment, and automated email outreach capabilities with a user-friendly web interface.

## Features

### 1. Lead Generation
- Automated company research and data collection
- AI-powered data enrichment
- Real-time progress tracking
- Session-based data management

### 2. Email Automation
- AI-generated personalized email content
- Automated email sending with tracking
- Support for multiple email sequences
- Progress monitoring and status updates

## Project Structure

```
Lead_generation/
├── agent/                     # AI Agent components
│   ├── config.py             # Agent configuration
│   ├── main.py               # Main agent logic
│   ├── monitoring.py         # Monitoring utilities
│   └── sub_agents/           # Specialized agents
│       ├── agent.py          # Agent definitions
│       └── tools/            # Agent tools
│           ├── data_enrichment_tool.py
│           ├── perplexity_tool.py
│           └── read_google_docs.py
├── app.py                    # Flask application
├── emails.py                 # Email handling
├── static/                   # Static assets
│   ├── script.js            # Frontend JavaScript
│   └── style.css            # CSS styles
└── templates/                # HTML templates
    └── index.html           # Main interface
```

## Technical Stack

### Backend
- **Framework**: Flask + Flask-SocketIO
- **AI/ML**: Google ADK (Agent Development Kit)
- **Database**: SQLite
- **Email**: SMTP via Gmail
- **Async Support**: Eventlet

### Frontend
- **JavaScript**: Native JS with Socket.IO client
- **CSS**: Custom styling
- **Real-time Updates**: WebSocket communication

## Key Components

### 1. AI Agents

#### Main Agent Types:
- **CEOResearcher**: Finds CEO information and contact details
- **RevenueResearcher**: Researches company revenue data
- **CompanyStatsResearcher**: Gathers employee count and founding year
- **ClientTargetAgent**: Analyzes target markets and clients
- **RankingAgent**: Evaluates collaboration potential
- **EmailContentGenerator**: Creates personalized email content

### 2. Email System

#### Features:
- Personalized content generation
- Email validation
- Progress tracking
- CSV summary generation
- Session-based file management

#### Email Summary Format:
- Company Name
- Email Address
- CEO Name
- Subject
- 1st Email Sent (timestamp)
- 2nd Email Sent (timestamp)
- 3rd Email Sent (timestamp)

### 3. File Management

All generated files are organized in session-specific folders:
```
files/
└── [session_id]/
    ├── companies.csv         # Generated leads
    ├── email_summary.csv     # Email tracking
    └── logs.json            # Operation logs
```

## Setup Instructions

1. **Environment Setup**
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Create a `.env` file with:
   ```
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_app_password
   SENDER_NAME=Your Name
   SENDER_ROLE=Your Role
   ```

3. **Database Initialization**
   ```bash
   flask db upgrade
   ```

4. **Running the Application**
   ```bash
   python app.py
   ```

## Usage Guide

### 1. Lead Generation
1. Access the web interface
2. Upload target criteria or input manually
3. Click "Generate Leads"
4. Monitor progress in real-time
5. Download results when complete

### 2. Email Outreach
1. Review generated leads
2. Click "Send Emails"
3. Monitor sending progress
4. Check email_summary.csv for status

### 3. Monitoring
- Watch real-time progress updates
- Check logs.json for detailed operation logs
- Review email_summary.csv for outreach status

## Security Considerations

1. **Email Security**
   - Use Gmail App Passwords
   - SMTP over SSL
   - Credential protection via .env

2. **Data Protection**
   - Session-based isolation
   - Temporary file cleanup
   - Input validation

3. **Rate Limiting**
   - Email sending delays
   - API request throttling
   - Concurrent operation limits

## Troubleshooting

### Common Issues:

1. **Email Sending Fails**
   - Check SMTP credentials
   - Verify sender email format
   - Check recipient email validity

2. **Agent Errors**
   - Verify API keys
   - Check network connectivity
   - Review logs.json for details

3. **File Access Issues**
   - Check directory permissions
   - Verify session ID validity
   - Ensure proper file paths

## Development Guidelines

1. **Code Organization**
   - Follow modular structure
   - Maintain separation of concerns
   - Document complex logic

2. **Error Handling**
   - Implement comprehensive try-except
   - Log errors appropriately
   - Provide user feedback

3. **Testing**
   - Unit test critical components
   - Integration test workflows
   - End-to-end test key features

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Submit pull request

## License

Proprietary - All rights reserved

## Support

For support or questions, contact the development team.
