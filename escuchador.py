from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import os

app = Flask(__name__)

# --- CONFIGURACIÓN ---
API_KEY = os.environ.get("OPENAI_API_KEY") or "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"
WPP_URL_BASE = os.environ.get("EVOLUTION_URL") or "https://determined-sparkle-production.up.railway.app"
WPP_KEY = os.environ.get("WPP_APIKEY") or "benjorro_secret_key"
INSTANCIA = "teste2"

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

@app.route('/webhook', methods=['GET', 'POST'])
def handle_webhook():
    if request.method == 'GET':
        return "<h1>BOT ARIZON: CONECTADO ✅</h1>", 200

    payload = request.json or {}
    data = payload.get('data', {})
    
    if not data or data.get('key', {}).get('fromMe'):
        return jsonify({"status": "ignored"}), 200

    remote_jid = data.get('key', {}).get('remoteJid', '')
    participant = data.get('participant', '')
    target = participant if "@lid" in remote_jid and participant else remote_jid
    
    msg_body = data.get('message', {})
    text = msg_body.get('conversation') or msg_body.get('extendedTextMessage', {}).get('text', '')

    if text:
        try:
            chat_completion = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[{"role": "system", "content": "Sos un técnico de refrigeración de 20 años, hablas tranqui."}, 
                          {"role": "user", "content": text}]
            )
            ai_resp = chat_completion.choices[0].message.content

            send_url = f"{WPP_URL_BASE}/message/sendText/{INSTANCIA}"
            requests.post(send_url, 
                          json={"number": target, "textMessage": {"text": ai_resp}}, 
                          headers={"apikey": WPP_KEY}, 
                          timeout=10)
        except Exception as e:
            print(f"Error: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port_env = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port_env)
