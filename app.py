import os
import sqlite3
import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv  
from google import genai
from google.genai import types

# 1. Establish absolute directory path structures
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Force load the .env file explicitly using its absolute location
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=dotenv_path)

# 3. Explicitly wire the template_folder configuration using absolute paths
app = Flask(
    __name__, 
    template_folder=os.path.join(BASE_DIR, 'template')
)
DB_FILE = os.path.join(BASE_DIR, "knowledge_capture.db")

# 4. Initialize the official Gemini Client
# It will now easily locate the GEMINI_API_KEY from the explicitly loaded environment
client = genai.Client()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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
            status TEXT,
            image_base64 TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_recent_data_summary(limit=12):
    conn = sqlite3.connect(DB_FILE)
    # Exclude base64 image strings to prevent feeding massive content to the LLM token window
    df = pd.read_sql_query(
        f"SELECT id, timestamp, name, target_task, category, detailed_desc, troubleshooting_steps, resolution, status "
        f"FROM responses ORDER BY id DESC LIMIT {limit}", 
        conn
    )
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
        image_base64 = data.get("image_base64", "")
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not detailed_desc:
            return jsonify({"error": "Description is required"}), 400

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO responses (timestamp, name, target_task, category, detailed_desc, troubleshooting_steps, resolution, status, image_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, name, target_task, category, detailed_desc, troubleshooting_steps, resolution, status, image_base64))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    try:
        user_query = request.json.get("query", "")
        current_data_context = get_recent_data_summary(limit=12)
        
        system_instruction = (
            "You are an expert operations assistant. Look at the comprehensive tracking data breakdown snapshot below "
            "and answer the user's question directly based on tasks, troubleshooting data, and resolution descriptions."
        )
        
        prompt_content = (
            f"--- LIVE TRACKER DATA SNAPSHOT ---\n{current_data_context}\n----------------------------------\n\n"
            f"User Question: {user_query}"
        )
        
        # Request generation using the high-speed, free-tier gemini-2.5-flash model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            ),
        )
        
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"reply": f"Cloud Core Error Processing Request: {str(e)}"}), 500

init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)