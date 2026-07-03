import os
import sqlite3
import datetime
import pandas as pd
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='template')
DB_FILE = "knowledge_capture.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:latest"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            description TEXT,
            status TEXT,
            captured_by TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_recent_data_summary(limit=15):
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

# --- NEW: ROUTE TO REPLACE GOOGLE FORMS ---
@app.route('/api/log', methods=['POST'])
def add_new_log():
    """Receives input directly from the custom web app UI and saves to SQL."""
    try:
        data = request.json
        category = data.get("category", "General")
        description = data.get("description", "")
        captured_by = data.get("captured_by", "Anonymous")
        status = data.get("status", "Pending")
        
        # Automatically generate a clean timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not description:
            return jsonify({"error": "Description is required"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO responses (timestamp, category, description, status, captured_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, category, description, status, captured_by))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Log updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    user_query = request.json.get("query", "")
    current_data_context = get_recent_data_summary(limit=15)
    
    # We combine context clearly so the model sees it as a direct instruction set
    combined_prompt = (
        "Instructions: You are an expert operations assistant. Look at the data snapshot below "
        "and answer the user's question directly. Keep your response concise, clear, and professional.\n\n"
        f"--- LIVE DATA SNAPSHOT ---\n{current_data_context}\n---------------------------\n\n"
        f"User Question: {user_query}\n\n"
        "Response:"
    )
    
    payload = {
        "model": MODEL_NAME,
        "prompt": combined_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3  # Keeps the model focused on the facts in the data snapshot
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response_json = response.json()
        ai_reply = response_json.get("response", "No response generated.")
        return jsonify({"reply": ai_reply})
    except Exception as e:
        return jsonify({"reply": f"Error communicating with Ollama: {str(e)}"}), 500

init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
