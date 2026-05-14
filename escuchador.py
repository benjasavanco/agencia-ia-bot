from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import os

app = Flask(__name__)

# --- CONFIGURACIÓN ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    return response.json()

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Token inválido', 403

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    payload = request.json or {}

    try:
        entry = payload['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']

        # Ignorar si no hay mensajes
        if 'messages' not in value:
            return jsonify({"status": "ignored"}), 200

        message = value['messages'][0]

        # Ignorar si no es texto
        if message.get('type') != 'text':
            return jsonify({"status": "ignored"}), 200

        from_number = message['from']
        text = message['text']['body']

        # Generar respuesta con IA
        completion = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "system",
                    "content": "Sos un asistente virtual amable y profesional. Respondés en español."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        ai_response = completion.choices[0].message.content

        # Enviar respuesta por WhatsApp
        send_whatsapp_message(from_number, ai_response)

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
