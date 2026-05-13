
from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import re
import os
import json
import logging
 
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
 
# --- CONFIGURACIÓN IA ---
OPENAI_API_KEY = "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"
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
 
client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
)
 
# --- CONFIGURACIÓN EVOLUTION API ---
EVOLUTION_URL_BASE = "https://determined-sparkle-production.up.railway.app"
INSTANCIA = "teste2"
WPP_URL = f"{EVOLUTION_URL_BASE}/message/sendText/{INSTANCIA}"
WPP_APIKEY = "benjorro_secret_key"
WPP_HEADERS = {"apikey": WPP_APIKEY, "Content-Type": "application/json"}
 
def normalize_number(number_str: str) -> str:
    return re.sub(r'\D', '', number_str or "")
 
def enviar_mensaje(numero_jid: str, texto: str):
    payload = {
        "number": numero_jid,
        "textMessage": {"text": texto}
    }
    response = requests.post(WPP_URL, json=payload, headers=WPP_HEADERS, timeout=8)
    logging.info("Enviado a %s → %s: %s", numero_jid, response.status_code, response.text)
    return response
 
def consultar_ia(mensaje_cliente: str) -> str:
    try:
        completion = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {"role": "system", "content": "Sos tranquilo e inteligente, respondes muy natural, como alguien de unos 20 años, sin tantos signos de exclamacion ni preguntas etc, como alguien humano, sin tantas reglas de ortografia."},
                {"role": "user", "content": mensaje_cliente}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.exception("Error en IA: %s", e)
        return "Lo siento, no puedo procesar tu solicitud en este momento."
 
 
@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    datos = request.json or {}
    event = datos.get('event')
    data = datos.get('data', {})
 
    if event != 'messages.upsert' or data.get('key', {}).get('fromMe', True):
        return jsonify({"status": "ignored"}), 200
 
    key = data.get('key', {})
    remote_jid = key.get('remoteJid', '')
 
    # Extraer texto del mensaje
    message = data.get('message', {})
    mensaje_cliente = ""
    if 'conversation' in message:
        mensaje_cliente = message.get('conversation', '').strip()
    elif 'extendedTextMessage' in message:
        mensaje_cliente = message.get('extendedTextMessage', {}).get('text', '').strip()
 
    if not mensaje_cliente:
        return jsonify({"status": "no_message"}), 200
 
    # Siempre responder al JID original, sea @lid o @s.whatsapp.net
    # Evolution API v1 soporta enviar a @lid directamente
    jid_destino = remote_jid
 
    # Si viene participant válido (no lid), usarlo como destino
    participant = data.get('participant', '')
    if participant and '@lid' not in participant and participant:
        jid_destino = participant
        logging.info("Usando participant como destino: %s", jid_destino)
    else:
        logging.info("Usando remoteJid como destino: %s", jid_destino)
 
    numero_log = normalize_number(remote_jid.split('@')[0])
    print(f"📩 Mensaje de {numero_log}: {mensaje_cliente}")
 
    respuesta_ia = consultar_ia(mensaje_cliente)
 
    try:
        enviar_mensaje(jid_destino, respuesta_ia)
    except requests.RequestException as e:
        logging.exception("Error al enviar a Evolution API: %s", e)
        return jsonify({"status": "error", "detail": "request_failed"}), 500
 
    return jsonify({"status": "success"}), 200
 
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
 
