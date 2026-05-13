from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import os
import re

app = Flask(__name__)

# --- CONFIGURACIÓN SEGURA ---
# Usamos .get() para que si no existe la variable, el bot no explote
API_KEY_IA = os.environ.get("OPENAI_API_KEY", "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")
BASE_URL_IA = "https://openrouter.ai/api/v1"
WPP_BASE = os.environ.get("EVOLUTION_URL", "https://determined-sparkle-production.up.railway.app")
WPP_KEY = os.environ.get("WPP_APIKEY", "benjorro_secret_key")
INSTANCIA = "teste2"

client = OpenAI(base_url=BASE_URL_IA, api_key=API_KEY_IA)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return "BOT ONLINE", 200
        
    datos = request.json or {}
    # Extraemos la data del mensaje
    data = datos.get('data', {})
    if not data or data.get('key', {}).get('fromMe'):
        return jsonify({"status": "ignored"}), 200

    # Destino y Mensaje
    remote_jid = data.get('key', {}).get('remoteJid', '')
    participant = data.get('participant', '')
    destinatario = participant if "@lid" in remote_jid and participant else remote_jid
    
    msg_dict = data.get('message', {})
    texto_usuario = msg_dict.get('conversation') or msg_dict.get('extendedTextMessage', {}).get('text', '')

    if texto_usuario:
        try:
            # IA
            res = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[{"role": "system", "content": "Sos humano, tranqui, 20 años."}, 
                          {"role": "user", "content": texto_usuario}]
            )
            respuesta = res.choices[0].message.content

            # Enviar
            url_send = f"{WPP_BASE}/message/sendText/{INSTANCIA}"
            requests.post(url_send, json={"number": destinatario, "textMessage": {"text": respuesta}}, 
                          headers={"apikey": WPP_KEY}, timeout=10)
        except Exception as e:
            print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    # Esto es lo que pide Railway en image_648cfb.png
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
