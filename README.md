# 🕵️ Lead Generation Monitor with Flask + Google ADK

This project is a lightweight Flask-based monitoring tool for tracking token usage, agent tasks, and performance of Google ADK agents used in lead generation workflows.

## 🚀 Features

- ✅ Track each agent’s:
  - Token usage (input/output)
  - Task status
  - Execution time
- ✅ Display monitoring data on a simple, responsive frontend
- ✅ API endpoints to fetch and update monitoring data
- ✅ Modular design to plug into existing Google ADK agent pipelines
- ✅ Ideal for B2B or outbound marketing automation tools

---

## 🧰 Tech Stack

- **Backend**: Flask, Python
- **Frontend**: HTML/CSS/JS (can be easily replaced with React/Vue)
- **Agents**: Google ADK `SequentialAgent`, `LlmAgent`, custom token counting utilities
- **Others**: Flask-CORS, Flask-Session, dotenv

---

## 📧 Email Configuration

To enable email sending functionality, you need to configure the following environment variables in your `.env` file:

```env
# Flask Configuration
FLASK_SECRET_KEY=your-secret-key-here

# Email Configuration
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-specific-password
SENDER_NAME=Your Name
SENDER_ROLE=Business Development & Strategic Partnerships
```

### Gmail Setup Instructions:
1. Go to your Google Account settings
2. Enable 2-factor authentication
3. Generate an App Password:
   - Go to Security settings
   - Select "2-Step Verification"
   - At the bottom, select "App passwords"
   - Generate a password for "Mail"
4. Use the generated App Password in `SENDER_PASSWORD`

### Email Features:
- **Save as Drafts Only**: Generates email drafts saved locally as EML and HTML files
- **Send Emails Directly**: Sends emails via SMTP while also saving drafts for records
- All drafts include a summary CSV for easy tracking
- Personalized emails based on company's service focus

---

<img width="940" height="699" alt="Screenshot from 2025-07-22 19-43-07" src="https://github.com/user-attachments/assets/a6006d5e-5e5c-4f3f-afc2-a4dde2dddc3f" />
