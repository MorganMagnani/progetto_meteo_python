from flask import Flask, request, jsonify, render_template
import requests
import mysql.connector
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Connessione al DB
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="meteo"
)
cursor = db.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS ricerche (
    id INT AUTO_INCREMENT PRIMARY KEY,
    citta VARCHAR(100),
    data DATETIME,
    temperatura FLOAT
)
""")

def descrizione_meteo(code):
    if code == 0: return "Sereno"
    if code in [1, 2]: return "Parzialmente nuvoloso"
    if code == 3: return "Nuvoloso"
    if 45 <= code <= 48: return "Nebbia"
    if 51 <= code <= 57: return "Pioviggine"
    if 61 <= code <= 67: return "Pioggia"
    if 71 <= code <= 77: return "Neve"
    if 80 <= code <= 82: return "Rovesci"
    if code == 95: return "Temporale"
    if 96 <= code <= 99: return "Temporale con grandine"
    return "Non disponibile"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/meteo', methods=['POST'])
def meteo():
    data = request.get_json()
    city = data.get('city')

    # Geolocalizzazione con OpenStreetMap
    headers = { "User-Agent": "meteo-app/1.0 (email@esempio.it)" }
    geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"

    try:
        geo_res = requests.get(geo_url, headers=headers, timeout=5)
        geo_res.raise_for_status()
        geo_data = geo_res.json()
    except requests.exceptions.RequestException as e:
        print("Errore nella richiesta a Nominatim:", e)
        return jsonify({"error": "Errore nella geolocalizzazione"}), 500
    except ValueError:
        print("Risposta non valida da Nominatim:", geo_res.text)
        return jsonify({"error": "Formato risposta non valido"}), 500

    if not geo_data:
        return jsonify({"error": "Città non trovata"}), 404

    lat = geo_data[0]['lat']
    lon = geo_data[0]['lon']

    # Richiesta meteo a Open-Meteo
    meteo_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=Europe%2FRome"

    try:
        meteo_res = requests.get(meteo_url, timeout=5)
        meteo_res.raise_for_status()
        meteo_json = meteo_res.json()
        if 'current_weather' not in meteo_json:
            return jsonify({"error": "Dati meteo non disponibili"}), 500
        meteo_data = meteo_json['current_weather']
    except requests.exceptions.RequestException as e:
        print("Errore nella richiesta a Open-Meteo:", e)
        return jsonify({"error": "Errore nel recupero dei dati meteo"}), 500
    except ValueError:
        print("Risposta non valida da Open-Meteo:", meteo_res.text)
        return jsonify({"error": "Formato risposta meteo non valido"}), 500

    # Salvataggio e risposta
    temperatura = meteo_data['temperature']
    vento = meteo_data['windspeed']
    codice = meteo_data['weathercode']
    descrizione = descrizione_meteo(codice)
    ora = datetime.now()

    try:
        cursor.execute("INSERT INTO ricerche (citta, data, temperatura) VALUES (%s, %s, %s)", (city, ora, temperatura))
        db.commit()

        cursor.execute("SELECT citta, data, temperatura FROM ricerche ORDER BY id DESC LIMIT 5")
        risultati = cursor.fetchall()
        ricerche = [{"citta": r[0], "data": r[1], "temperatura": r[2]} for r in risultati]
    except Exception as e:
        print("Errore con il database:", e)
        return jsonify({"error": "Errore nel salvataggio dei dati"}), 500

    return jsonify({
        "citta": city,
        "temperatura": temperatura,
        "vento": vento,
        "meteo": descrizione,
        "ricerche": ricerche
    })

@app.route('/pulisci', methods=['POST'])
def pulisci():
    try:
        cursor.execute("DELETE FROM ricerche")
        db.commit()
        return jsonify({"message": "Cronologia pulita"})
    except Exception as e:
        print(e)
        return jsonify({"error": "Errore durante la cancellazione"}), 500

if __name__ == '__main__':
    app.run(debug=True)