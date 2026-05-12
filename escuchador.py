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
EVOLUTION_URL_BASE = "https://evolution-api-production-fa6b.up.railway.app"
INSTANCIA = "teste"
WPP_URL = f"{EVOLUTION_URL_BASE}/message/sendText/{INSTANCIA}"
WPP_APIKEY = "benjorro_secret_key"
WPP_HEADERS = {"apikey": WPP_APIKEY, "Content-Type": "application/json"}

# --- ARCHIVO DE MAPEO LID -> NÚMERO REAL ---
MAPEO_FILE = "lid_map.json"

def cargar_mapeo():
    if os.path.exists(MAPEO_FILE):
        with open(MAPEO_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_mapeo(mapeo):
    with open(MAPEO_FILE, "w") as f:
        json.dump(mapeo, f, indent=2)

lid_map = cargar_mapeo()

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

def buscar_numero_por_lid(lid_digits: str):
    try:
        url = f"{EVOLUTION_URL_BASE}/contacts/fetchContacts/{INSTANCIA}"
        resp = requests.post(url, json={"where": {}}, headers=WPP_HEADERS, timeout=8)
        if resp.status_code == 200:
            contactos = resp.json()
            for c in contactos:
                jid = c.get("id", "")
                lid = c.get("lid", "") or c.get("jid_lid", "")
                lid_clean = normalize_number(lid.split("@")[0] if "@" in lid else lid)
                if lid_clean == lid_digits:
                    numero = normalize_number(jid.split("@")[0])
                    logging.info("Número encontrado en contactos: %s para lid %s", numero, lid_digits)
                    return numero
    except Exception as e:
        logging.warning("No se pudo consultar contactos: %s", e)
    return None


@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    global lid_map

    datos = request.json or {}
    event = datos.get('event')
    data = datos.get('data', {})

    if event != 'messages.upsert' or data.get('key', {}).get('fromMe', True):
        return jsonify({"status": "ignored"}), 200

    key = data.get('key', {})
    remote_jid = key.get('remoteJid', '')

    # --- RESOLVER @lid ---
    if "@lid" in remote_jid:
        lid_digits = normalize_number(remote_jid.split('@')[0])
        logging.warning("remoteJid es @lid: %s", lid_digits)

        # 1. ¿Ya lo tenemos guardado en archivo?
        if lid_digits in lid_map:
            remote_jid = f"{lid_map[lid_digits]}@s.whatsapp.net"
            logging.info("@lid resuelto desde archivo: %s", remote_jid)

        # 2. ¿Viene el número real en 'participant'?
        elif data.get('participant') and "@lid" not in data.get('participant', ''):
            remote_jid = data['participant']
            numero = normalize_number(remote_jid.split('@')[0])
            lid_map[lid_digits] = numero
            guardar_mapeo(lid_map)
            logging.info("@lid resuelto desde participant y guardado: %s", remote_jid)

        # 3. Consultar contactos de Evolution API
        else:
            numero_real = buscar_numero_por_lid(lid_digits)
            if numero_real:
                remote_jid = f"{numero_real}@s.whatsapp.net"
                lid_map[lid_digits] = numero_real
                guardar_mapeo(lid_map)
                logging.info("@lid resuelto desde contactos y guardado: %s", remote_jid)
            else:
                logging.error("No se pudo resolver @lid %s", lid_digits)
                return jsonify({"status": "lid_pending"}), 200

    # Extraer texto del mensaje
    message = data.get('message', {})
    mensaje_cliente = ""
    if 'conversation' in message:
        mensaje_cliente = message.get('conversation', '').strip()
    elif 'extendedTextMessage' in message:
        mensaje_cliente = message.get('extendedTextMessage', {}).get('text', '').strip()

    if not mensaje_cliente:
        return jsonify({"status": "no_message"}), 200

    numero_cliente_digits = normalize_number(remote_jid.split('@')[0])
    print(f"📩 Mensaje de {numero_cliente_digits}: {mensaje_cliente}")

    # --- CONSULTA A LA IA ---
    try:
        completion = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {"role": "system", "content": "Sos tranquilo e inteligente, respondes muy natural, como alguien de unos 20 años, sin tantos signos de exclamacion ni preguntas etc, como alguien humano, sin tantas reglas de ortografia."},
                {"role": "user", "content": mensaje_cliente}
            ]
        )
        respuesta_ia = completion.choices[0].message.content
    except Exception as e:
        logging.exception("Error en IA: %s", e)
        respuesta_ia = "Lo siento, no puedo procesar tu solicitud en este momento."

    # --- ENVIAR RESPUESTA ---
    try:
        enviar_mensaje(remote_jid, respuesta_ia)
    except requests.RequestException as e:
        logging.exception("Error al enviar a Evolution API: %s", e)
        return jsonify({"status": "error", "detail": "request_failed"}), 500

    return jsonify({"status": "success"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
