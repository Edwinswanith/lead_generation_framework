import eventlet
eventlet.monkey_patch()
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_session import Session
from agent.main import run_agent_async
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import threading
import time
import os
import json
from datetime import timedelta
import uuid
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Get secret key from environment
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    raise ValueError("Missing FLASK_SECRET_KEY in .env")

# Configure database
app.config.update(
    SQLALCHEMY_DATABASE_URI='sqlite:///users.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# Initialize database
db = SQLAlchemy(app)

# Configure session settings
app.config.update(
    SESSION_TYPE="sqlalchemy",
    SECRET_KEY=secret_key,
    SESSION_SQLALCHEMY=db,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    SESSION_COOKIE_NAME="lead_generation",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True
)

# Initialize session
Session(app)

# Create database tables
with app.app_context():
    db.create_all()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')

def stream_and_collect_data(session_id: str):
    """Streams logs and collects enriched companies data."""
    if not session_id:
        return

    with app.app_context():
        # Stream logs
        file_name = session_id
        logs_path = os.path.join(BASE_DIR, 'files', f'{file_name}.json')
        if os.path.exists(logs_path):
            with open(logs_path, 'r') as f:
                logs = [json.loads(line) for line in f if line.strip()]
            
            grouped_logs = {}
            for log in logs:
                agent = log.get('agent', 'general')
                if agent not in grouped_logs:
                    grouped_logs[agent] = []
                grouped_logs[agent].append(log)
            socketio.emit('logs_update', grouped_logs)

        # Collect token usage data
        token_usage = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0
        }
        if os.path.exists(logs_path):
            with open(logs_path, 'r') as f:
                for line in f:
                    if line.strip():
                        log = json.loads(line)
                        token_usage['total_input_tokens'] += log.get('input_tokens', 0)
                        token_usage['total_output_tokens'] += log.get('output_tokens', 0)
                        token_usage['total_cost'] += log.get('cost', 0.0)
        
        socketio.emit('token_update', token_usage)

        # Collect enriched companies data
        companies_path = os.path.join(BASE_DIR, 'files', f'{session_id}.csv')
        if os.path.exists(companies_path):
            df = pd.read_csv(companies_path)
            df = df.fillna('')
            socketio.emit('companies_update', df.to_dict(orient='records'))

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    session_id = session.get('session_id')
    if session_id:
        stream_and_collect_data(session_id)

@app.route('/get-companies')
def get_enriched_companies_data():
    try:
        file_path = os.path.join(BASE_DIR, 'files', f'{session.get("session_id")}.csv')
        df = pd.read_csv(file_path)
        df = df.fillna('')
        return jsonify(df.to_dict(orient='records'))
    except FileNotFoundError:
        return jsonify([])

@app.route('/generate-leads', methods=['POST'])
def generate_leads():
    try:
        if 'inputFile' not in request.files:
            return jsonify({"error": "No file part"}), 400
            
        input_file = request.files['inputFile']
        
        if input_file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        if input_file:
            FILE_FOLDER = os.path.join(BASE_DIR, 'files')
            os.makedirs(FILE_FOLDER, exist_ok=True)
            
            for file in os.listdir(FILE_FOLDER):
                if file.endswith('.csv') or file.endswith('.xlsx'):
                    os.remove(os.path.join(FILE_FOLDER, file))
                    
            filename = input_file.filename
            filepath = os.path.join(FILE_FOLDER, filename)
            input_file.save(filepath)
            print(f"File saved to {filepath}")
            
            session_id = session.get('session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id

            logs_path = os.path.join(FILE_FOLDER, f'{session_id}.json')
            if os.path.exists(logs_path):
                with open(logs_path, 'w') as f:
                    f.truncate(0)
                
            thread = threading.Thread(target=run_agent_with_updates, args=(filepath, session_id))
            thread.start()
            
            return redirect(url_for('index'))
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_agent_with_updates(filepath: str, session_id: str):
    """Run the agent and periodically send updates via WebSocket."""
    
    agent_thread = threading.Thread(target=run_agent_async, args=(filepath, session_id))
    agent_thread.start()

    while agent_thread.is_alive():
        stream_and_collect_data(session_id)
        socketio.sleep(2)
    
    stream_and_collect_data(session_id)

@app.route('/get-logs')
def get_logs():
    try:
        file_name = session.get('session_id')
        logs_path = os.path.join(BASE_DIR, 'files', f'{file_name}.json')
        with open(logs_path, 'r') as f:
            logs = [json.loads(line) for line in f if line.strip()]
        
        grouped_logs = {}
        for log in logs:
            agent = log.get('agent', 'general')
            if agent not in grouped_logs:
                grouped_logs[agent] = []
            grouped_logs[agent].append(log)
            
        return jsonify(grouped_logs)
    except FileNotFoundError:
        return jsonify({})

@app.route('/download_file')
def download_file():
    try:
        file_path = os.path.join(BASE_DIR, 'files', f'{session.get("session_id")}.csv')
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)