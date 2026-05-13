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
 
# --- ARCHIVOS DE DATOS ---
MAPEO_FILE = "lid_map.json"        # lid_digits -> numero_real
PENDIENTES_FILE = "pendientes.json" # lid_digits -> mensaje_original pendiente
 
def cargar_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}
 
def guardar_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
 
lid_map = cargar_json(MAPEO_FILE)
pendientes = cargar_json(PENDIENTES_FILE)
 
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
    global lid_map, pendientes
 
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
 
    # --- RESOLVER @lid ---
    if "@lid" in remote_jid:
        lid_digits = normalize_number(remote_jid.split('@')[0])
        logging.warning("remoteJid es @lid: %s", lid_digits)
 
        # 1. ¿Ya lo tenemos guardado?
        if lid_digits in lid_map:
            remote_jid = f"{lid_map[lid_digits]}@s.whatsapp.net"
            logging.info("@lid resuelto desde archivo: %s", remote_jid)
 
        # 2. ¿Viene el número real en 'participant'?
        elif data.get('participant') and "@lid" not in data.get('participant', ''):
            remote_jid = data['participant']
            numero = normalize_number(remote_jid.split('@')[0])
            lid_map[lid_digits] = numero
            guardar_json(MAPEO_FILE, lid_map)
            logging.info("@lid resuelto desde participant: %s", remote_jid)
 
        # 3. ¿Está esperando que nos diga su nombre? (viene respuesta al pedido)
        elif lid_digits in pendientes:
            # El usuario respondió con su nombre — lo usamos como número ficticio
            # y guardamos el LID para que el bot pueda responderle
            numero_ficticio = lid_digits  # usamos el propio LID como clave
            lid_map[lid_digits] = numero_ficticio
            guardar_json(MAPEO_FILE, lid_map)
 
            # Recuperar mensaje original pendiente
            mensaje_original = pendientes.pop(lid_digits, "")
            guardar_json(PENDIENTES_FILE, pendientes)
 
            remote_jid_respuesta = f"{lid_digits}@lid"
 
            # Responder al mensaje original
            if mensaje_original:
                respuesta = consultar_ia(mensaje_original)
                enviar_mensaje(remote_jid_respuesta, respuesta)
 
            logging.info("LID %s registrado y mensaje original procesado", lid_digits)
            return jsonify({"status": "lid_resolved"}), 200
 
        # 4. LID desconocido — guardar mensaje y pedir identificación
        else:
            logging.error("No se pudo resolver @lid %s — pidiendo identificación", lid_digits)
            pendientes[lid_digits] = mensaje_cliente
            guardar_json(PENDIENTES_FILE, pendientes)
 
            # Responder directamente al JID del lid
            remote_jid_lid = f"{lid_digits}@lid"
            enviar_mensaje(remote_jid_lid, "hola! para poder ayudarte necesito que me digas tu nombre 👋")
            return jsonify({"status": "lid_pending_name"}), 200
 
    # --- FLUJO NORMAL ---
    numero_cliente_digits = normalize_number(remote_jid.split('@')[0])
    print(f"📩 Mensaje de {numero_cliente_digits}: {mensaje_cliente}")
 
    respuesta_ia = consultar_ia(mensaje_cliente)
 
    try:
        enviar_mensaje(remote_jid, respuesta_ia)
    except requests.RequestException as e:
        logging.exception("Error al enviar a Evolution API: %s", e)
        return jsonify({"status": "error", "detail": "request_failed"}), 500
 
    return jsonify({"status": "success"}), 200
 
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
 
