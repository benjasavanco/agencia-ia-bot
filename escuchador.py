
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
# Esto busca CUALQUIER nombre que hayas puesto en Railway
EVOLUTION_URL_BASE = os.environ.get("EVOLUTION_URL") or os.environ.get("EVOLUTION_URL_BASE") or "https://determined-sparkle-production.up.railway.app"
INSTANCIA = os.environ.get("INSTANCIA") or "teste2"

WPP_URL = f"{EVOLUTION_URL_BASE}/message/sendText/{INSTANCIA}"
WPP_APIKEY = os.environ.get("WPP_APIKEY") or "benjorro_secret_key"
WPP_HEADERS = {"apikey": WPP_APIKEY, "Content-Type": "application/json"}

def normalize_number(number_str: str) -> str:
    """Limpia el string para dejar solo dígitos."""
    return re.sub(r'\D', '', number_str or "")

def enviar_mensaje(numero_destino: str, texto: str):
    """
    Envía el mensaje a la Evolution API. 
    'numero_destino' puede ser un JID completo o solo el número.
    """
    payload = {
        "number": numero_destino,
        "textMessage": {"text": texto}
    }
    response = requests.post(WPP_URL, json=payload, headers=WPP_HEADERS, timeout=10)
    logging.info("Enviado a %s → %s: %s", numero_destino, response.status_code, response.text)
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

    # 1. Validación de evento y origen
    if event != 'messages.upsert' or data.get('key', {}).get('fromMe', True):
        return jsonify({"status": "ignored"}), 200

    # 2. Identificación del remitente (Solución al problema @lid)
    key = data.get('key', {})
    remote_jid = key.get('remoteJid', '')
    participant = data.get('participant', '')

    # Lógica de rescate: Si el ID principal es un @lid, intentamos usar el participante real
    if "@lid" in remote_jid and participant:
        jid_destino = participant
        logging.info("🔄 Detectado @lid. Corrigiendo destino a participant: %s", jid_destino)
    else:
        jid_destino = remote_jid
        logging.info("📍 Usando destino original: %s", jid_destino)

    # 3. Extraer texto del mensaje
    message = data.get('message', {})
    mensaje_cliente = ""
    if 'conversation' in message:
        mensaje_cliente = message.get('conversation', '').strip()
    elif 'extendedTextMessage' in message:
        mensaje_cliente = message.get('extendedTextMessage', {}).get('text', '').strip()

    if not mensaje_cliente:
        return jsonify({"status": "no_message"}), 200

    # Log para consola
    num_log = normalize_number(jid_destino.split('@')[0])
    print(f"📩 Mensaje de {num_log}: {mensaje_cliente}")

    # 4. Obtener respuesta de la IA
    respuesta_ia = consultar_ia(mensaje_cliente)

    # 5. Enviar respuesta
    try:
        # Forzamos que sea solo el número limpio si es un JID estándar para evitar conflictos
        # Pero mantenemos el JID si la lógica de rescate falló
        destino_final = normalize_number(jid_destino.split('@')[0]) if "@s.whatsapp.net" in jid_destino else jid_destino
        
        enviar_mensaje(destino_final, respuesta_ia)
    except Exception as e:
        logging.exception("❌ Error al enviar a Evolution API: %s", e)
        return jsonify({"status": "error", "detail": str(e)}), 500

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
