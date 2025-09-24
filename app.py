import os
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
import requests
import io
import json
import re

app = Flask(__name__)
# Create directories for uploaded files and processed data if they don't exist
if not os.path.exists('data/raw'):
    os.makedirs('data/raw')
if not os.path.exists('data/processed'):
    os.makedirs('data/processed')

# You will need to replace this with your actual Gemini API URL
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key="
API_KEY = "AIzaSyDE4vioKGav0xSz3rwIzGheQ4j0XQ5eEcE" # Your API key will be automatically provided by the environment, but you can paste it here if you face issues
# For example: API_KEY = "YOUR_API_KEY_HERE"

# Route to serve the main HTML page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle CSV file upload and processing
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        try:
            # Read the CSV file into a pandas DataFrame
            df = pd.read_csv(file)

            # Split data into cleaned and uncleaned
            cleaned_df = df.dropna()
            uncleaned_df = df[df.isnull().any(axis=1)]

            # Convert to JSON for sending to the frontend
            cleaned_json = cleaned_df.to_json(orient='records')
            uncleaned_json = uncleaned_df.to_json(orient='records')

            return jsonify({
                'cleaned': json.loads(cleaned_json),
                'uncleaned': json.loads(uncleaned_json),
                'cleaned_count': len(cleaned_df),
                'uncleaned_count': len(uncleaned_df)
            })
        except Exception as e:
            return jsonify({'error': f'An error occurred during file processing: {str(e)}'}), 500
        
# Route to handle Gemini dataset generation
@app.route('/gemini_generate', methods=['POST'])
def gemini_generate():
    data = request.json
    prompt = data.get('prompt')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    try:
        # We will now modify the prompt to tell the model to generate a JSON array.
        full_prompt = f"Generate a dataset based on the following description. The response must be a valid JSON array of objects, where each object represents a row of data.\n\nDescription: {prompt}"
        
        payload = {
            "contents": [{
                "parts": [{ "text": full_prompt }]
            }]
        }
        
        response = requests.post(
            f"{GEMINI_API_URL}{API_KEY}",
            headers={'Content-Type': 'application/json'},
            json=payload
        )
        response.raise_for_status()

        generated_data_text = response.json().get('candidates')[0].get('content').get('parts')[0].get('text')
        
        # Robustly find and parse the JSON content
        json_match = re.search(r'```json\n(.*)\n```', generated_data_text, re.DOTALL)
        if json_match:
            generated_data_text = json_match.group(1)

        generated_data = json.loads(generated_data_text)

        # Return the generated JSON data
        return jsonify(generated_data)
    
    except requests.exceptions.HTTPError as err:
        return jsonify({'error': f"HTTP Error: {err.response.text}"}), err.response.status_code
    except json.JSONDecodeError as e:
        return jsonify({'error': f'An error occurred during JSON parsing. The raw API response was: {generated_data_text}'}), 500
    except Exception as e:
        return jsonify({'error': f'An error occurred during Gemini API call: {str(e)}'}), 500

# Route to export processed data as CSV
@app.route('/export/csv', methods=['POST'])
def export_csv():
    data = request.json
    df = pd.DataFrame(data)
    csv_string = df.to_csv(index=False)
    buffer = io.BytesIO(csv_string.encode('utf-8'))
    return send_file(
        buffer,
        mimetype='text/csv',
        as_attachment=True,
        download_name='data.csv'
    )

# Route to export processed data as Excel
@app.route('/export/excel', methods=['POST'])
def export_excel():
    data = request.json
    df = pd.DataFrame(data)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    excel_buffer.seek(0)
    return send_file(
        excel_buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='data.xlsx'
    )

# Route to export processed data as PDF (will be handled by frontend for simplicity)
@app.route('/export/pdf', methods=['POST'])
def export_pdf():
    # The frontend handles PDF generation using jsPDF
    return jsonify({'message': 'PDF generation is handled by the frontend.'})

if __name__ == '__main__':
    app.run(debug=True)