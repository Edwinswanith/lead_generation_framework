import eventlet
eventlet.monkey_patch()
import eventlet.debug
eventlet.debug.hub_prevent_multiple_readers(False)
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, session
from flask_socketio import SocketIO, join_room
from flask_session import Session
from agent.main import run_agent_async
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
import json
from datetime import timedelta, datetime
import uuid
from eventlet.patcher import original
real_threading = original('threading')
load_dotenv()
import re
from emails import send_emails_task
import asyncio

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
app.config['BASE_DIR'] = BASE_DIR

@app.route('/')
def index():
    if not session.get('session_id'):
        session['session_id'] = str(uuid.uuid4())
        session['total_rows'] = 0  # Initialize total_rows
    return render_template('index.html')

def stream_and_collect_data(session_id: str, total_rows: int = 0):
    """Streams logs and collects enriched companies data."""
    if not session_id:
        return

    with app.app_context():
        # Create session directory if it doesn't exist
        session_dir = os.path.join(BASE_DIR, 'files', session_id)
        os.makedirs(session_dir, exist_ok=True)

        # Stream logs
        logs_path = os.path.join(session_dir, 'logs.json')
        if os.path.exists(logs_path):
            try:
                with open(logs_path, 'r') as f:
                    logs = [json.loads(line) for line in f if line.strip()]
                
                grouped_logs = {}
                for log in logs:
                    agent = log.get('agent', 'general')
                    if agent not in grouped_logs:
                        grouped_logs[agent] = []
                    grouped_logs[agent].append(log)
                socketio.emit('logs_update', grouped_logs, room=session_id)

                # Collect token usage data
                token_usage = {
                    'total_input_tokens': 0,
                    'total_output_tokens': 0,
                    'total_cost': 0.0
                }
                for log in logs:
                    token_usage['total_input_tokens'] += log.get('input_tokens', 0)
                    token_usage['total_output_tokens'] += log.get('output_tokens', 0)
                    token_usage['total_cost'] += log.get('cost', 0.0)
                
                socketio.emit('token_update', token_usage, room=session_id)
            except Exception as e:
                print(f"Error reading logs file: {e}")

        # Collect enriched companies data and emit progress
        companies_path = os.path.join(session_dir, 'companies.csv')
        processed_rows = 0
        if os.path.exists(companies_path):
            try:
                df = pd.read_csv(companies_path, engine='python', on_bad_lines='warn')
                df = df.fillna('')
                processed_rows = len(df)
                socketio.emit('companies_update', df.to_dict(orient='records'), room=session_id)
            except Exception as e:
                print(f"Could not parse {companies_path}. It might be in the process of being written, empty, or contain errors. Error: {e}")
        
        current_total_rows = total_rows if total_rows > 0 else session.get('total_rows', 0)
        socketio.emit('progress_update', {
            'processed': processed_rows,
            'total': current_total_rows
        }, room=session_id)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    session_id = session.get('session_id')
    if session_id:
        join_room(session_id)
        print(f"Client with sid {request.sid} joined room {session_id}")
        # Initial data push on connect, can be empty if no process has run for this session
        with app.app_context():
            stream_and_collect_data(session_id, session.get('total_rows', 0))

@app.route('/get-companies')
def get_enriched_companies_data():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify([])
        
    try:
        file_path = os.path.join(BASE_DIR, 'files', session_id, 'companies.csv')
        df = pd.read_csv(file_path, engine='python', on_bad_lines='warn')
        df = df.fillna('')
        return jsonify(df.to_dict(orient='records'))
    except (FileNotFoundError, pd.errors.ParserError, pd.errors.EmptyDataError):
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
            session_id = session.get('session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id

            # Create session directory
            session_dir = os.path.join(BASE_DIR, 'files', session_id)
            os.makedirs(session_dir, exist_ok=True)
            
            filename = input_file.filename
            filepath = os.path.join(session_dir, filename)
            input_file.save(filepath)
            print(f"File saved to {filepath}")

            try:
                if filename.endswith('.csv'):
                    df_input = pd.read_csv(filepath, engine='python', on_bad_lines='warn')
                elif filename.endswith(('.xls', '.xlsx')):
                    df_input = pd.read_excel(filepath)
                else:
                    df_input = None
                
                if df_input is not None:
                    session['total_rows'] = len(df_input)
                else:
                    session['total_rows'] = 0
            except Exception as e:
                print(f"Could not read input file to get total rows: {e}")
                session['total_rows'] = 0

            logs_path = os.path.join(session_dir, 'logs.json')
            if os.path.exists(logs_path):
                os.remove(logs_path)

            companies_path = os.path.join(session_dir, 'companies.csv')
            if os.path.exists(companies_path):
                os.remove(companies_path)

            running_flag_path = os.path.join(session_dir, 'running')
            if os.path.exists(running_flag_path):
                os.remove(running_flag_path)
                
            socketio.start_background_task(
                run_agent_with_updates, filepath, session_id, session.get('total_rows', 0)
            )
            
            return jsonify({"message": "Agent process started successfully."}), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status')
def status():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'running': False})

    running_flag_path = os.path.join(BASE_DIR, 'files', session_id, 'running')
    is_running = os.path.exists(running_flag_path)
    return jsonify({'running': is_running})

@app.route('/stop-agent', methods=['POST'])
def stop_agent():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({"error": "No active session"}), 400

    stop_flag_path = os.path.join(BASE_DIR, 'files', session_id, 'stop')
    with open(stop_flag_path, 'w') as f:
        f.write('stop')
    
    return jsonify({"message": "Agent stop signal sent."})

@app.route('/clear-data', methods=['POST'])
def clear_data():
    import shutil
    
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({"error": "No active session"}), 400

    # Remove session directory and all its contents
    session_dir = os.path.join(BASE_DIR, 'files', session_id)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
            
    return jsonify({"message": "Session data cleared."})

def run_agent_with_updates(filepath: str, session_id: str, total_rows: int):
    """Run the agent and periodically send updates via WebSocket."""
    session_dir = os.path.join(BASE_DIR, 'files', session_id)
    running_flag_path = os.path.join(session_dir, 'running')
    stop_flag_path = os.path.join(session_dir, 'stop')

    def agent_task():
        """Wrapper function to run the agent."""
        run_agent_async(filepath, session_id)

    try:
        with open(running_flag_path, 'w') as f:
            f.write('running')

        agent_thread = real_threading.Thread(target=agent_task)
        agent_thread.start()

        while agent_thread.is_alive():
            if os.path.exists(stop_flag_path):
                print(f"Stop signal detected for session {session_id}. Stopping agent.")
                break 

            with app.app_context():
                stream_and_collect_data(session_id, total_rows)
            socketio.sleep(2)

        # One last poll to ensure we get the final data
        with app.app_context():
            stream_and_collect_data(session_id, total_rows)
            
    finally:
        if os.path.exists(running_flag_path):
            os.remove(running_flag_path)
        
        if os.path.exists(stop_flag_path):
            os.remove(stop_flag_path)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"File {filepath} removed.")


@app.route('/get-logs')
def get_logs():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({})
        
    try:
        logs_path = os.path.join(BASE_DIR, 'files', session_id, 'logs.json')
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
    session_id = session.get("session_id")
    if not session_id:
        return jsonify({"error": "No active session found"}), 400

    file_path = os.path.join(BASE_DIR, 'files', session_id, 'companies.csv')
    logs_path = os.path.join(BASE_DIR, 'files', session_id, 'logs.json')

    # Check if processing is still ongoing
    agent_running_path = os.path.join(BASE_DIR, 'files', session_id, 'running')
    if os.path.exists(agent_running_path):
        return jsonify({"error": "File is still being generated, please try again in a few seconds"}), 202

    # Check if file exists
    if not os.path.exists(file_path):
        return jsonify({"error": "No data file found. Please upload and process a file first."}), 404

    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f'enriched_data_{session_id}.csv',
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({"error": f"Error downloading file: {str(e)}"}), 500


@app.route('/send-bulk-emails', methods=['POST'])
def send_bulk_emails():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({"error": "No active session"}), 400
    
    data = request.get_json()
    mode = data.get('mode', 'draft') if data else 'draft'
    
    companies_path = os.path.join(BASE_DIR, 'files', session_id, 'companies.csv')
    if not os.path.exists(companies_path):
        return jsonify({"error": "No companies data found"}), 404

    def run_email_task():
        try:
            # Create a new event loop in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the email task
            loop.run_until_complete(send_emails_task(session_id, companies_path, mode, socketio, app))
            
        except Exception as e:
            print(f"Error in email task: {e}")
            socketio.emit('email_progress', {
                'status': {
                    'success': False,
                    'message': f'Error in email task: {str(e)}',
                    'company_name': 'System'
                }
            }, room=session_id)
        finally:
            try:
                # Clean up any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                
                # Allow cancelled tasks to complete
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
                # Stop and close the event loop
                loop.stop()
                loop.close()
                
                # Remove the loop from the current thread
                asyncio.set_event_loop(None)
                
            except Exception as e:
                print(f"Error during cleanup: {e}")

    # Start the email task in the background
    socketio.start_background_task(run_email_task)
    
    return jsonify({"message": f"Email {mode} process started"})


@app.route('/download-email-drafts', methods=['POST'])
def download_email_drafts():
    import zipfile
    from io import BytesIO
    
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({"error": "No active session"}), 400
    
    drafts_dir = os.path.join(BASE_DIR, 'email_drafts', session_id)
    if not os.path.exists(drafts_dir):
        return jsonify({"error": "No email drafts found"}), 404
    
    # Create a zip file in memory
    zip_buffer = BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all files from the drafts directory
            for root, dirs, files in os.walk(drafts_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.join(drafts_dir, '..'))
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f'email_drafts_{session_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
            mimetype='application/zip'
        )
    except Exception as e:
        return jsonify({"error": f"Error creating zip file: {str(e)}"}), 500


# if __name__ == '__main__':
#     port = int(os.environ.get("PORT", 8080))
#     socketio.run(app, host='0.0.0.0', port=port)
if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('', 5000)), app)