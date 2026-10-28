import os
import re
import json
import time
import hashlib
import calendar
import requests
import feedparser
import threading
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, request

# ==============================================================================
# 1. CONFIGURACIÓN E IDENTIFICACIÓN
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# ID del grupo configurado (-5252825542)
CHAT_ID = int(os.environ.get("CHAT_ID", "-5252825542"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://monitor-rss-service.onrender.com")

DB_FILE = "inteligencia_veracruz.db"

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==============================================================================
# 2. BASE DE DATOS LOCAL
# ==============================================================================
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS items_monitoreo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_id TEXT UNIQUE,
                fuente TEXT,
                autor TEXT,
                titulo TEXT,
                url TEXT,
                fecha_publicacion TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error DB init: {e}")

def item_ya_procesado(hash_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT id FROM items_monitoreo WHERE hash_id = ?', (hash_id,))
        res = c.fetchone()
        conn.close()
        return res is not None
    except Exception:
        return False

def guardar_item(hash_id, fuente, autor, titulo, url, fecha_publicacion):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO items_monitoreo 
            (hash_id, fuente, autor, titulo, url, fecha_publicacion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (hash_id, fuente, autor, titulo, url, fecha_publicacion))
        conn.commit()
        conn.close()
    except Exception:
        pass

# ==============================================================================
# 3. LISTAS DE FUENTES Y PARÁMETROS DE FILTRADO
# ==============================================================================
RSS_FEEDS = [
    "https://coatzadiario.com/feed/", "https://coatzahoy.com/feed/", "https://www.elpinero.mx/feed/",
    "https://elementosmx.com/feed/", "https://www.enprivadoveracruz.com.mx/feed/", "https://www.firmas.mx/feed/",
    "https://horacero.mx/feed/", "https://jornadaveracruz.com.mx/feed/", "https://www.politicaaldia.com/feed/",
    "https://tvsureste.com/feed/", "https://alornoticias.com.mx/feed/", "https://www.avcnoticias.com.mx/rss/",
    "https://blogexpediente.com/feed/", "https://cambiodigitalnoticias.com/feed/", "https://cronicadelpoder.com/feed/",
    "https://www.diariodexalapa.com.mx/rss/", "https://diariolostuxtlas.com/feed/", "https://graficoaldia.mx/feed/",
    "https://elheraldodemartinez.com.mx/feed/", "https://lasillarota.com/veracruz/feed/", "https://latinus.us/feed/",
    "https://www.masnoticias.mx/feed/", "https://www.nmas.com.mx/rss/", "https://palabrasclaras.mx/feed/",
    "https://sociedadtrespuntocero.com/feed/", "https://xeu.mx/feed/", "https://billieparkernoticias.com/feed/",
    "https://imagendelgolfo.mx/feed/", "https://noreste.net/feed/", "https://ventanaver.mx/feed/",
    "https://municipiosur.com/feed/", "https://www.elchiltepin.com/feed/", "https://veracruz.quadratin.com.mx/feed/",
    "https://vanguardiaveracruz.com/feed/", "https://www.alcalorpolitico.com/rss/"
]

PARAMETROS = [
    "Rocío Nahle", "Rocio Nahle", "Nahle", "Mañanera", "DIF Estatal", "DIF Veracruz",
    "CGEC", "Contraloría General del Estado", "CGCS", "Coordinación General Comunicación Social",
    "SEGOB", "Secretaría de Gobierno", "SSP", "Secretaría de Seguridad Pública",
    "SEV", "Secretaría de Educación de Veracruz", "SS", "Secretaría de Salud",
    "SEFIPLAN", "Secretaría de Finanzas y Planeación", "SEDECOP", "Secretaría de Desarrollo Económico y Portuario",
    "SEDESOL", "Secretaría de Desarrollo Social", "SIOP", "Secretaría de Infraestructura y Obras Públicas",
    "STPSP", "Secretaría de Trabajo, Previsión Social y Productividad", "SECTUR", "Secretaría de Turismo",
    "SECVER", "Secretaría de Cultura de Veracruz", "SEDEMA", "Secretaría de Medio Ambiente",
    "SEDARPA", "Secretaría de Desarrollo Agropecuario, Rural, Pesca y Alimentación", "SPC", "Secretaría de Protección Civil",
    "Zona Norte", "Zona Centro", "Zona Sur", "Zona Altas Montañas", "Zona Totonacapan",
    "Acajete", "Acatlán", "Acayucan", "Actopan", "Acula", "Acultzingo", "Agua Dulce", 
    "Álamo Temapache", "Alpatláhuac", "Alto Lucero", "Altotonga", "Alvarado", "Amatitlán", 
    "Amatlán de los Reyes", "Ángel R. Cabada", "Apazapan", "Aquila", "Astacinga", 
    "Atlahuilco", "Atoyac", "Atzacan", "Atzalan", "Ayahualulco", "Banderilla", 
    "Benito Juárez", "Boca del Río", "Calcahualco", "Camerino Z. Mendoza", 
    "Carlos A. Carrillo", "Carrillo Puerto", "Catemaco", "Cazones de Herrera", 
    "Cerro Azul", "Chacaltianguis", "Chalma", "Chiconamel", "Chiconquiaco", 
    "Chicontepec", "Chinameca", "Chinampa de Gorostiza", "Chocamán", "Chontla", 
    "Chumatlán", "Coacoatzintla", "Coahuitlán", "Coatepec", "Coatzacoalcos", 
    "Coatzintla", "Comapa", "Córdoba", "Cosamaloapan", "Cosautlán de Carvajal", 
    "Coscomatepec", "Cosoleacaque", "Cotaxtla", "Coxquihui", "Coyutla", "Cuichapa", 
    "Cuitláhuac", "El Higo", "Emiliano Zapata", "Espinal", "Filomeno Mata", "Fortín", 
    "Gutiérrez Zamora", "Hidalgotitlán", "Huatusco", "Huayacocotla", "Hueyapan de Ocampo", 
    "Huiloapan", "Ignacio de la Llave", "Ilamatlán", "Isla", "Ixcatepec", 
    "Ixhuacán de los Reyes", "Ixhuatlán de Madero", "Ixhuatlán del Café", 
    "Ixhuatlán del Sureste", "Ixmatlahuacan", "Ixtaczoquitlán", "Jalacingo", 
    "Jalcomulco", "Jáltipan", "Jamapa", "Jesús Carranza", "Jilotepec", "José Azueta", 
    "Juan Rodríguez Clara", "Juchique de Ferrer", "Landero y Coss", "Las Choapas", 
    "Las Minas", "Las Vigas", "Lerdo de Tejada", "Los Reyes", "Magdalena", 
    "Maltrata", "Mariano Escobedo", "Martínez de la Torre", "Mecayapan", "Mecatlán", 
    "Miahuatlán", "Minatitlán", "Misantla", "Mixtla de Altamirano", "Moloacán", 
    "Naranjal", "Naranjos Amatlán", "Naolinco", "Nanchital", "Nautla", "Nogales", 
    "Oluta", "Omealca", "Orizaba", "Otatitlán", "Oteapan", "Ozuluama", "Pajapan", 
    "Pánuco", "Papantla", "Paso del Macho", "Paso de Ovejas", "Perote", 
    "Platón Sánchez", "Playa Vicente", "Poza Rica", "Pueblo Viejo", "Puente Nacional", 
    "Rafael Delgado", "Rafael Lucio", "Río Blanco", "Saltabarranca", 
    "San Andrés Tenejapan", "San Andrés Tuxtla", "San Juan Evangelista", 
    "Santiago Tuxtla", "Santiago Sochiapan", "Sayula de Alemán", "Soconusco", 
    "Sochiapa", "Soledad Atzompa", "Soledad de Doblado", "Soteapan", "Tamalín", 
    "Tamiahua", "Tampico Alto", "Tancoco", "Tantima", "Tantoyuca", "Tatahuicapan", 
    "Tatatila", "Tecolutla", "Tehuipango", "Tempoal", "Tenampa", "Tenochtitlán", 
    "Teocelo", "Tepatlaxco", "Tepetlán", "Tepetzintla", "Tequila", "Texcatepec", 
    "Texhuacán", "Texistepec", "Tezonapa", "Tierra Blanca", "Tihuatlán", 
    "Tlachichilco", "Tlacojalpan", "Tlacolulan", "Tlacotalpan", "Tlacotepec de Mejía", 
    "Tlaltetela", "Tlapacoyan", "Tlaquilpa", "Tlilapan", "Tomatlán", "Tonayán", 
    "Totutla", "Tres Valles", "Tuxpan", "Tuxtilla", "Úrsulo Galván", "Vega de Alatorre", 
    "Veracruz", "Villa Aldama", "Xalapa", "Xico", "Xoxocotla", "Yanga", "Yecuatla", 
    "Zacualpan", "Zaragoza", "Zentla", "Zongolica", "Zontecomatlán", "Zozocolco", 
    "Yunes", "Manuel Huerta", "Julen Rementería", "Patricia Lobeira", "Claudia Guerrero", 
    "Mussio Cárdenas", "inundación", "deslave", "derrumbe", "bloqueo", "homicidio"
]

KEYWORDS_CRISIS_NAHLE = [
    "corrupcion", "desvio", "denuncia", "escandalo", "crimen", "inseguridad",
    "protesta", "manifestacion", "auditoria", "desabasto", "violencia", "bloqueo"
]

# ==============================================================================
# 4. EVALUACIÓN Y ANÁLISIS IA
# ==============================================================================
def normalizar(texto: str) -> str:
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

def evaluar_coincidencia(texto: str):
    texto_norm = normalizar(texto)
    for kw in PARAMETROS:
        kw_norm = normalizar(kw)
        if " " in kw_norm:
            if kw_norm in texto_norm: return True, kw
        else:
            if re.search(rf"\b{re.escape(kw_norm)}\b", texto_norm): return True, kw
    return False, None

def analizar_nota_con_gemini(titulo: str, resumen: str):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        f"Eres un analista de comunicación y riesgo político del Estado de Veracruz. "
        f"Analiza la siguiente nota y genera un reporte breve y directo:\n"
        f"1) Tres viñetas concisas con los hechos clave.\n"
        f"2) Sentimiento (Positivo, Neutral, Negativo o Muy Negativo).\n"
        f"3) Riesgo Político (Bajo, Medio o Alto) con una frase del porqué.\n"
        f"4) Riesgo Mediático (Bajo, Medio o Alto).\n\n"
        f"Título: {titulo}\nContexto: {resumen}"
    )
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception:
        pass
    return None

# ==============================================================================
# 5. MENSAJERÍA TELEGRAM
# ==============================================================================
def enviar_mensaje_telegram(texto: str):
    if not TELEGRAM_TOKEN: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 400:
            payload["parse_mode"] = ""
            r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

# ==============================================================================
# 6. PIPELINE DE MONITOREO
# ==============================================================================
def calcular_umbral_tiempo(horas_atras=None):
    if horas_atras:
        return calendar.timegm(time.gmtime()) - (horas_atras * 3600)
    
    ahora_utc = datetime.utcnow()
    ahora_veracruz = ahora_utc - timedelta(hours=6)
    if ahora_veracruz.hour >= 22:
        fecha_10pm = ahora_veracruz.replace(hour=22, minute=0, second=0, microsecond=0)
    else:
        fecha_10pm = (ahora_veracruz - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
    
    return calendar.timegm((fecha_10pm + timedelta(hours=6)).utctimetuple())

def ejecutar_monitoreo(horas_atras=None):
    epoch_threshold = calcular_umbral_tiempo(horas_atras)
    alertas_enviadas = 0

    # 1. Monitoreo CAPUFE con timeout estricto
    try:
        r_cap = requests.get("https://nitter.privacydev.net/CAPUFE/rss", headers=HEADERS_HTTP, timeout=3)
        if r_cap.status_code == 200:
            cap_feed = feedparser.parse(r_cap.content)
            for e in cap_feed.entries[:6]:
                txt = e.get("summary", "")
                if any(t in txt.lower() for t in ["veracruz", "cordoba", "orizaba", "maltrata", "coatzacoalcos", "isla", "tinaja"]):
                    link = e.get("link", "#").replace("nitter.privacydev.net", "x.com")
                    h_id = hashlib.sha256(f"CAPUFE_{link}".encode('utf-8')).hexdigest()
                    if not item_ya_procesado(h_id):
                        msg = (
                            f"🛣️ *ALERTA VIAL CAPUFE: VERACRUZ*\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"📌 *Fuente:* CAPUFE Oficial (@CAPUFE)\n"
                            f"📝 *Reporte:* {txt}\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"🔗 *Enlace:* {link}"
                        )
                        enviar_mensaje_telegram(msg)
                        guardar_item(h_id, "CAPUFE", "@CAPUFE", "Reporte Vial", link, "")
                        alertas_enviadas += 1
                        time.sleep(0.4)
    except Exception:
        pass

    # 2. Medios RSS
    for url in RSS_FEEDS:
        try:
            r = requests.get(url, headers=HEADERS_HTTP, timeout=6)
            if r.status_code != 200: continue
            feed = feedparser.parse(r.content)
        except Exception:
            continue

        if not hasattr(feed, 'entries'): continue
        nombre_medio = feed.feed.get("title", url.split("//")[-1].split("/")[0])

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link: continue

            titulo = entry.get("title", "")
            resumen = entry.get("summary", "")
            h_id = hashlib.sha256(f"{link}_{titulo}".encode('utf-8')).hexdigest()

            if item_ya_procesado(h_id):
                continue

            fecha_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            timestamp_noticia = ""
            if fecha_parsed:
                try:
                    nota_epoch = calendar.timegm(fecha_parsed)
                    if nota_epoch < epoch_threshold: continue
                    dt_veracruz = datetime(*fecha_parsed[:6]) - timedelta(hours=6)
                    timestamp_noticia = dt_veracruz.strftime("%H:%M del %d/%m/%Y")
                except Exception:
                    pass

            if not timestamp_noticia:
                timestamp_noticia = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M del %d/%m/%Y")

            hizo_match, kw = evaluar_coincidencia(titulo)
            if not hizo_match:
                hizo_match, kw = evaluar_coincidencia(resumen)

            if hizo_match:
                texto_norm = normalizar(f"{titulo} {resumen}")
                es_nahle_crisis = ("nahle" in texto_norm) and any(c in texto_norm for c in KEYWORDS_CRISIS_NAHLE)
                
                header = "🔥 *ALERTA CRÍTICA: GOBERNADORA ROCÍO NAHLE*" if es_nahle_crisis else "🚨 *ALERTA ESTRATÉGICA VERACRUZ*"
                analisis_ia = analizar_nota_con_gemini(titulo, resumen)

                if analisis_ia:
                    msg = (
                        f"{header}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🏛️ *Medio:* {nombre_medio}\n"
                        f"🎯 *Match:* `{kw}`\n"
                        f"📝 *Título:* {titulo}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🧠 *ANÁLISIS DE INTELIGENCIA:*\n"
                        f"{analisis_ia}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🕒 _Publicado: {timestamp_noticia}_\n"
                        f"🔗 *Enlace:* {link}"
                    )
                else:
                    msg = (
                        f"{header}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🏛️ *Medio:* {nombre_medio}\n"
                        f"🎯 *Match:* `{kw}`\n"
                        f"📝 *Título:* {titulo}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🕒 _Publicado: {timestamp_noticia}_\n"
                        f"🔗 *Enlace:* {link}"
                    )

                enviar_mensaje_telegram(msg)
                guardar_item(h_id, nombre_medio, "", titulo, link, timestamp_noticia)
                alertas_enviadas += 1
                time.sleep(0.4)

    enviar_mensaje_telegram(f"✅ *Escaneo completado.*\n📊 Alertas enviadas: `{alertas_enviadas}`")

def ejecutar_busqueda_tema(tema_objetivo):
    palabras = [normalizar(w) for w in tema_objetivo.split() if len(w) >= 3]
    if not palabras: return
    hallados = 0

    for url in RSS_FEEDS:
        try:
            r = requests.get(url, headers=HEADERS_HTTP, timeout=5)
            if r.status_code != 200: continue
            feed = feedparser.parse(r.content)
            nombre_medio = feed.feed.get("title", url.split("//")[-1].split("/")[0])
            for e in feed.entries:
                titulo = e.get("title", "")
                resumen = e.get("summary", "")
                texto = normalizar(f"{titulo} {resumen}")

                if all(w in texto for w in palabras):
                    link = e.get("link", "#")
                    analisis = analizar_nota_con_gemini(titulo, resumen)
                    msg = (
                        f"🔍 *HALLAZGO BÚSQUEDA:* `{tema_objetivo}`\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🏛️ *Medio:* {nombre_medio}\n"
                        f"📝 *Título:* {titulo}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"{analisis if analisis else ''}\n"
                        f"🔗 *Enlace:* {link}"
                    )
                    enviar_mensaje_telegram(msg)
                    hallados += 1
                    time.sleep(0.4)
        except Exception:
            continue
    enviar_mensaje_telegram(f"✅ Búsqueda terminada. Hallazgos: `{hallados}`")

# ==============================================================================
# 7. SERVIDOR WEB Y CONTROL DE COMANDOS
# ==============================================================================
app = Flask(__name__)
init_db()

@app.route('/')
def home():
    return "Monitor Veracruz Operativo"

@app.route('/webhook', methods=['POST'])
def webhook():
    datos = request.get_json()
    if datos and "message" in datos:
        msg = datos["message"]
        chat_id_recibido = msg.get("chat", {}).get("id")

        # Verifica que el mensaje provenga del grupo configurado
        if chat_id_recibido == CHAT_ID:
            raw_text = msg.get("text", "").strip()
            # Limpia comandos con sufijo de bot en grupos (ej. "/escanear@tu_bot" -> "/escanear")
            txt = re.sub(r"(@\w+)", "", raw_text).strip()

            if txt == "/start" or txt == "/ayuda":
                menu = (
                    "🏛️ *SISTEMA DE INTELIGENCIA VERACRUZ*\n\n"
                    "👉 `/escanear` : Rastrear corte desde las 22:00 hrs de ayer.\n"
                    "👉 `/escanear X` : Rastrear últimas X horas (ej. `/escanear 3`).\n"
                    "👉 `/buscar TEMA` : Búsqueda temática directa.\n"
                    "👉 `/limpiar` : Vaciar historial de base de datos."
                )
                enviar_mensaje_telegram(menu)

            elif txt.startswith("/escanear"):
                arg = txt.replace("/escanear", "").strip()
                num = re.findall(r'\d+', arg)
                horas = int(num[0]) if num else None
                if horas:
                    enviar_mensaje_telegram(f"🔍 _Rastreando últimas {horas} horas..._")
                else:
                    enviar_mensaje_telegram("🔍 _Rastreando corte desde las 22:00 hrs de ayer..._")
                threading.Thread(target=ejecutar_monitoreo, args=(horas,), daemon=True).start()

            elif txt.startswith("/buscar "):
                tema = txt.replace("/buscar", "", 1).strip()
                if tema:
                    enviar_mensaje_telegram(f"🔍 _Buscando:_ `{tema}`...")
                    threading.Thread(target=ejecutar_busqueda_tema, args=(tema,), daemon=True).start()

            elif txt == "/limpiar":
                conn = sqlite3.connect(DB_FILE)
                conn.cursor().execute("DELETE FROM items_monitoreo")
                conn.commit()
                conn.close()
                enviar_mensaje_telegram("🗑️ *Base de datos local vaciada.*")

    return "OK", 200

def registrar_webhook():
    time.sleep(3)
    endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={endpoint}", timeout=8)
    except Exception:
        pass

if __name__ == "__main__":
    threading.Thread(target=registrar_webhook, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
