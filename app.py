# concesionaria/ia/app.py

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import google.generativeai as genai
import requests # Para hacer peticiones HTTP a tu API de admin
import json # Para manejar los datos JSON
import uuid

# Cargar variables de entorno del archivo .env
load_dotenv()

# --- Configuración de Google Gemini ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('models/gemini-1.5-flash')

# --- Configuración de Flask ---
app = Flask(__name__)
CORS(app)

# --- Consumir endpoints y guardar datos ---
URL_API_AUTOS = os.getenv("URL_API_AUTOS", "http://localhost:8080/concesionaria/admin/api/api.php")
URL_API_SUCURSALES = os.getenv("URL_API_AUTOS", "http://localhost:8080/concesionaria/admin/api/sucursales.php")

def get_vehiculos_from_api():
    try:
        response = requests.get(URL_API_AUTOS)
        response.raise_for_status() # Lanza un error si la petición falla
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de vehículos: {e}")
        return []
    
def get_sucursales_from_api():
    try:
        response = requests.get(URL_API_SUCURSALES)
        response.raise_for_status() # Lanza un error si la petición falla
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al conectar con la API de sucursales: {e}")
        return []


chat_sessions = {}

# --- Endpoint del Chatbot para que se comunique React ---
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    user_message = data.get('message')
    session_id = data.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        chat_sessions[session_id] = []

    vehiculos_data = get_vehiculos_from_api()
    vehiculos_str = json.dumps(vehiculos_data, indent=2)

    sucursales_data = get_sucursales_from_api()
    sucursales_str = json.dumps(sucursales_data, indent=2)

    # 2. Construcción del Prompt para Gemini
    prompt = f"""
    Eres un asistente llamado CARBOT, experto en vehículos de una concesionaria. Tu función es responder preguntas de clientes sobre los autos disponibles en nuestro inventario 
    basado ÚNICAMENTE en la 'Información recuperada de vehiculos disponibles' de nuestra base de datos que te proporciono, o responder preguntas sobre las sucursales basado UNICAMENTE en la 'Información recuperada de sucursales disponibles'.
    En la informacion recuperada aparecen los vehiculos, en marca_descripcion esta su marca por ejemplo ford o ram o chevrolet, en modelo_descripcion su modelo por ejemplo ranger para ford o vento para volgswagen, 
    en traccion_descripcion su traccion por ejemplo 4x4 o delantera, en categoria_descripcion si es un auto, una camioneta, una moto etc, y bueno la demas informacion que aparece. El sistema
    funciona asi te explico para que lo entiendas y respondas perfectamente: para cargar un vehiculo hay que seleccionar su categoria, para esta categoria hay marcas registradas entonces cuando seleccionas
    una categoria te aparecen las marcas para esa categoria, entonces seleccionar la marca, y luego te aparecen los modelos relacionados a esa marca, luego ingresas textual su version y demas info... Luegos tambien
    cada caracteristica esta asociada a su respectiva categoria, porque por ejemplo los autos no tienen traccion 4x4, las caracteristicas son traccion transmision combustible carroceria etc. 
    Despues tambien estan las otras caracteristicas que son equipamientos, seguridades y confort, lo mismo, cada una esta relacionada a su categoria. Entonces si te preguntan por categoria es decir si hay
    camionetas o autos o motos ahi te fijas por categoria, si te preguntar por camioneta SUV o camioneta PICKUP te fijas en la categoria camioneta y en la carroceria que se indico...
    Si la 'información_recuperada' indica que "No se encontraron vehículos...", o si la pregunta no puede ser respondida con esa información, infórmale al usuario que no tienes esa información o que debe ser más específico o reformular su consulta.
    Sé amigable, conciso y profesional. Si hay múltiples resultados, puedes enumerarlos de forma clara en vez de numero utilizar '·' .
    Si se pide informacion sobre varios vehiculos como por ejemplo busco autos sedan o busco camioneta pick up, quiero que en forma de lista, listes uno debajo del otro TODOS los vehiculos (no omitir ninguno) que coincidan con la pregunta del usuario, mencionando de cada uno SOLAMENTE la marca el modelo la version y el año de cada vehiculo, pero para cada vehículo en especifico que se te pregunte y tu menciones, toda la informacion relevante deberas ponerla en forma de listado amigable una caracteristica debajo de la otra (osea cuando te pregunten por ejemplo sobre un vehiculo y en la info de vehiculos que te di esa pregunta coincida con un resultado solo, ya si coincide con varios resultados listas solo marca modelo version y anio de cada uno.).
    Cuando te hablo de listado es algo asi: TITULO dos puntos enter -info enter -info enter -info etc.
    Si te preguntan por un auto y no encuentras coincidencias, sugiérele que pruebe con otra marca o modelo.
    Otro punto muy importante, tambien estas recibiendo cada historial del chat de la sesion actual, debes apoyarte en ese historial para dar la respuesta mas precisa, por ejemplo te preguntan sobre camionetas, y luego en otro mensaje sin especificarte camioneta te dicen que buscan ford, tienes que informar camionetas ford...
    Y cando 

    ---
    Información recuperada de vehiculos disponibles:
    {vehiculos_str}
    ---
    Información recuperada de sucursales disponibles:
    {sucursales_str}
    ---
    Pregunta del usuario:
    {user_message}
    ---
    Respuesta:
    """

    chat_history = chat_sessions.get(session_id, [])
    chat = model.start_chat(history=chat_history)

    # 3. Generación de respuesta con Gemini
    try:
        response = chat.send_message(prompt)
        respuesta_final = response.text
    except Exception as e:
        print(f"Error al generar respuesta con Gemini: {e}")
        respuesta_final = "Lo siento, tuve un problema técnico al procesar tu consulta con la IA. Por favor, intentá de nuevo más tarde."

    # 4. Actualizar el historial de chat con la nueva interacción
    chat_history.append({"role": "user", "parts": [{"text": user_message}]})
    chat_history.append({"role": "model", "parts": [{"text": respuesta_final}]})
    chat_sessions[session_id] = chat_history

    return jsonify({"response": respuesta_final, "session_id": session_id})

# --- Ejecutar el servidor Flask ---
if __name__ == '__main__':
    app.run(debug=True, port=5000) # Este microservicio correrá en http://localhost:5000