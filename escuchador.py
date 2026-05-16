from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import os

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

print(f"TOKEN: {WHATSAPP_TOKEN[:10] if WHATSAPP_TOKEN else 'NO TOKEN'}")
print(f"PHONE_ID: {PHONE_NUMBER_ID}")

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
    print(f"Enviando a {to}: {text[:50]}")
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Respuesta Meta: {response.status_code} - {response.text}")
    return response.json()

@app.route('/registrar', methods=['GET'])
def registrar_numero():
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/register"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "pin": "000000"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Registro: {response.status_code} - {response.text}")
    return jsonify(response.json())

@app.route('/privacidad', methods=['GET'])
def privacidad():
    return """
    <h1>Política de Privacidad - KonversIA</h1>
    <p>KonversIA recopila únicamente los mensajes de WhatsApp necesarios para responder consultas.</p>
    <p>No compartimos datos con terceros.</p>
    <p>Contacto: matisavanco89@gmail.com</p>
    """, 200

@app.route('/test', methods=['GET'])
def test_send():
    result = send_whatsapp_message('549351769854', '¡Hola! Soy KonversIA, tu bot de WhatsApp con IA. 🤖')
    return jsonify(result)

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
    print(f"PAYLOAD RECIBIDO: {payload}")
    try:
        entry = payload['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        if 'messages' not in value:
            print("No hay mensajes en el payload")
            return jsonify({"status": "ignored"}), 200
        message = value['messages'][0]
        print(f"MENSAJE: {message}")
        if message.get('type') != 'text':
            print(f"Tipo de mensaje no soportado: {message.get('type')}")
            return jsonify({"status": "ignored"}), 200
        from_number = message['from']
        text = message['text']['body']
        print(f"DE: {from_number} - TEXTO: {text}")
        completion = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {"role": "system", "content": "Sos un asistente virtual amable y profesional. Respondés en español."},
                {"role": "user", "content": text}
            ]
        )
        ai_response = completion.choices[0].message.content
        print(f"RESPUESTA IA: {ai_response[:100]}")
        send_whatsapp_message(from_number, ai_response)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
