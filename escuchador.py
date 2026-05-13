from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import re
import os
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- CONFIGURACIÓN IA ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or "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"
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
)

# --- CONFIGURACIÓN EVOLUTION API ---
# Usamos el nombre exacto que tenés en Railway: EVOLUTION_URL
EVOLUTION_URL_BASE = os.environ.get("EVOLUTION_URL") or "https://determined-sparkle-production.up.railway.app"
INSTANCIA = "teste2"
WPP_URL = f"{EVOLUTION_URL_BASE}/message/sendText/{INSTANCIA}"
WPP_APIKEY = os.environ.get("WPP_APIKEY") or "benjorro_secret_key"
WPP_HEADERS = {"apikey": WPP_APIKEY, "Content-Type": "application/json"}

def normalize_number(number_str: str) -> str:
    return re.sub(r'\D', '', number_str or "")

def consultar_ia(mensaje_cliente: str) -> str:
    try:
        completion = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {"role": "system", "content": "Sos tranquilo e inteligente, respondes muy natural, como alguien de unos 20 años, sin tantos signos de exclamacion ni preguntas etc, como alguien humano, sin tantas reglas de ortografía."},
                {"role": "user", "content": mensaje_cliente}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.exception("Error en IA: %s", e)
        return "Perdón, estoy teniendo un problema técnico."

@app.route('/webhook', methods=['GET', 'POST']) # Agregamos GET para testear en navegador
def recibir_mensaje():
    if request.method == 'GET':
        return "¡Bot de Arizon activo y escuchando!", 200

    datos = request.json or {}
    event = datos.get('event')
    data = datos.get('data', {})

    if event != 'messages.upsert' or data.get('key', {}).get('fromMe', True):
        return jsonify({"status": "ignored"}), 200

    key = data.get('key', {})
    remote_jid = key.get('remoteJid', '')
    participant = data.get('participant', '')

    # Lógica de rescate para @lid
    if "@lid" in remote_jid and participant:
        jid_destino = participant
    else:
        jid_destino = remote_jid

    message = data.get('message', {})
    mensaje_cliente = ""
    if 'conversation' in message:
        mensaje_cliente = message.get('conversation', '').strip()
    elif 'extendedTextMessage' in message:
        mensaje_cliente = message.get('extendedTextMessage', {}).get('text', '').strip()

    if not mensaje_cliente:
        return jsonify({"status": "no_message"}), 200

    respuesta_ia = consultar_ia(mensaje_cliente)

    # Enviar respuesta
    payload = {
        "number": jid_destino,
        "textMessage": {"text": respuesta_ia}
    }

    try:
        requests.post(WPP_URL, json=payload, headers=WPP_HEADERS, timeout=10)
    except Exception as e:
        logging.error("Error al enviar: %s", e)

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    # ESTO ES LO MÁS IMPORTANTE PARA RAILWAY:
    # Debe leer la variable 'PORT' y usar 0.0.0.0
    puerto = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=puerto)
