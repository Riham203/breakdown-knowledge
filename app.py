import os
import sqlite3
import datetime
import pandas as pd
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='template')
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_capture.db")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:latest"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Updated table schema with all specific form questions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            name TEXT,
            target_task TEXT,
            category TEXT,
            detailed_desc TEXT,
            troubleshooting_steps TEXT,
            resolution TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_recent_data_summary(limit=10):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"SELECT * FROM responses ORDER BY id DESC LIMIT {limit}", conn)
    conn.close()
    return df.to_string(index=False)

@app.route('/')
def index():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM responses ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return render_template('index.html', logs=rows)

@app.route('/api/log', methods=['POST'])
def add_new_log():
    try:
        data = request.json
        name = data.get("name", "Anonymous")
        target_task = data.get("target_task", "")
        category = data.get("category", "General")
        detailed_desc = data.get("detailed_desc", "")
        troubleshooting_steps = data.get("troubleshooting_steps", "")
        resolution = data.get("resolution", "")
        status = data.get("status", "Pending")
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not detailed_desc:
            return jsonify({"error": "Description is required"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO responses (timestamp, name, target_task, category, detailed_desc, troubleshooting_steps, resolution, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, name, target_task, category, detailed_desc, troubleshooting_steps, resolution, status))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    user_query = request.json.get("query", "")
    current_data_context = get_recent_data_summary(limit=10)
    
    combined_prompt = (
        "Instructions: You are an expert operations assistant. Look at the comprehensive tracking data breakdown snapshot below "
        "and answer the user's question directly based on tasks, troubleshooting data, and resolution descriptions.\n\n"
        f"--- LIVE DETAILED SNAPSHOT ---\n{current_data_context}\n---------------------------\n\n"
        f"User Question: {user_query}\n\n"
        "Response:"
    )
    
    payload = {
        "model": MODEL_NAME,
        "prompt": combined_prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        return jsonify({"reply": response.json().get("response", "No response generated.")})
    except Exception as e:
        return jsonify({"reply": f"Error communicating with local AI model: {str(e)}"}), 500

init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)