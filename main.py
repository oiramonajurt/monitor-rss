import os
import re
import json
import time
import hashlib
import requests
import feedparser
import threading
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, request

# ==============================================================================
# 1. CONFIGURACIÓN E IDENTIFICACIÓN (Variables existentes de Render)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID", "1468116225"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://monitor-rss-service.onrender.com")

DB_FILE = "inteligencia_veracruz.db"

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==============================================================================
# 2. BASE DE DATOS LOCAL AUTOMÁTICA (SQLite Autónomo)
# ==============================================================================
def init_db():
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
            fecha_publicacion TEXT,
            es_nahle INTEGER,
            es_crisis INTEGER,
            es_lluvias INTEGER,
            municipio TEXT,
            dependencia TEXT,
            sentimiento TEXT,
            riesgo_politico TEXT,
            riesgo_mediatico TEXT
        )
    ''')
    conn.commit()
    conn.close()

def item_ya_procesado(hash_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id FROM items_monitoreo WHERE hash_id = ?', (hash_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def guardar_item(data):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO items_monitoreo 
            (hash_id, fuente, autor, titulo, url, fecha_publicacion, es_nahle, es_crisis, es_lluvias, municipio, dependencia, sentimiento, riesgo_politico, riesgo_mediatico)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get("hash_id"), data.get("fuente"), data.get("autor"), data.get("titulo"), data.get("url"),
            data.get("fecha_publicacion"), data.get("es_nahle", 0), data.get("es_crisis", 0), data.get("es_lluvias", 0),
            data.get("municipio"), data.get("dependencia"), data.get("sentimiento"), data.get("riesgo_politico"), data.get("riesgo_mediatico")
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass

# ==============================================================================
# 3. FUENTES Y REGLAS ESTRATÉGICAS DE VERACRUZ
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

MUNICIPIOS = [
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
    "Zacualpan", "Zaragoza", "Zentla", "Zongolica", "Zontecomatlán", "Zozocolco"
]

DEPENDENCIAS = [
    "SEGOB", "SSP", "SEV", "SS", "SEFIPLAN", "SEDECOP", "SEDESOL", "SIOP", 
    "STPSP", "SECTUR", "SECVER", "SEDEMA", "SEDARPA", "SPC", "Protección Civil",
    "DIF Estatal", "CGCS", "CGEC", "Contraloría General", "Fiscalía General", "FGE"
]

KEYWORDS_CRISIS_NAHLE = [
    "corrupcion", "desvio", "denuncia", "escandalo", "crimen", "inseguridad",
    "protesta", "manifestacion", "auditoria", "desabasto", "violencia", "bloqueo"
]

KEYWORDS_LLUVIAS = [
    "inundacion", "inundaciones", "desbordamiento", "deslave", "deslaves",
    "derrumbe", "derrumbes", "evacuacion", "refugio temporal", "albergue", "rio desbordado"
]

KEYWORDS_CRISIS = [
    "homicidio", "secuestro", "desaparicion", "narcobloqueo", "fosa", "extorsion",
    "cobro de piso", "balacera", "ejecutado", "orfis", "juicio politico", "desfalco",
    "toma de instalaciones", "socavon", "puente colapsado"
]

# ==============================================================================
# 4. FUNCIONES DE PROCESAMIENTO E INTELIGENCIA
# ==============================================================================
def normalizar(texto: str) -> str:
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

def evaluar_reglas(titulo: str, contenido: str):
    texto_norm = normalizar(f"{titulo} {contenido}")
    
    es_nahle = "nahle" in texto_norm or "rocio nahle" in texto_norm
    crisis_nahle = any(kw in texto_norm for kw in KEYWORDS_CRISIS_NAHLE)
    es_alerta_nahle = es_nahle and crisis_nahle
    
    es_lluvias = any(kw in texto_norm for kw in KEYWORDS_LLUVIAS)
    es_crisis = es_alerta_nahle or es_lluvias or any(kw in texto_norm for kw in KEYWORDS_CRISIS)
    
    muni = "Estatal"
    for m in MUNICIPIOS:
        if normalizar(m) in texto_norm:
            muni = m
            break
            
    dep = "Gobierno del Estado"
    for d in DEPENDENCIAS:
        if normalizar(d) in texto_norm:
            dep = d
            break

    return {
        "es_nahle": 1 if es_alerta_nahle else 0,
        "es_lluvias": 1 if es_lluvias else 0,
        "es_crisis": 1 if es_crisis else 0,
        "municipio": muni,
        "dependencia": dep
    }

def analizar_con_gemini_estructurado(titulo: str, contenido: str, fuente: str):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Actúa como Analista de Inteligencia Política y Riesgos del Estado de Veracruz.
    Analiza esta nota y devuelve EXCLUSIVAMENTE un JSON con:
    {{
      "tipo_actor": "Medio | Periodista | Columnista | Opositor | Funcionario | Alcalde | Ciudadano",
      "sentimiento": "Muy positivo | Positivo | Neutral | Negativo | Muy negativo",
      "riesgo_politico": "Bajo | Medio | Alto | Crítico",
      "riesgo_mediatico": "Bajo | Medio | Alto | Crítico",
      "tema_principal": "Tema central en máximo 6 palabras",
      "municipio": "Municipio involucrado o 'Estatal'",
      "dependencia": "Dependencia involucrada o 'Ninguna'",
      "resumen_ejecutivo": [
        "Viñeta 1 concisa",
        "Viñeta 2 concisa",
        "Viñeta 3 concisa"
      ],
      "impacto_potencial": "Impacto político o mediático directo",
      "recomendacion_estrategica": "Acción institucional sugerida"
    }}
    Nota: Fuente: {fuente} | Título: {titulo} | Resumen: {contenido}
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}
    }
    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            return json.loads(resp.json()['candidates'][0]['content']['parts'][0]['text'])
    except Exception:
        pass
    return None

# ==============================================================================
# 5. SALIDA TELEGRAM ESTRATÉGICA
# ==============================================================================
def enviar_alerta_telegram(item: dict, ia: dict = None):
    if not TELEGRAM_TOKEN: return False

    if item.get("es_nahle"):
        header = "🔥 *ALERTA CRÍTICA: GOBERNADORA ROCÍO NAHLE*"
    elif item.get("tipo_fuente") == "CAPUFE":
        header = "🛣️ *ALERTA VIAL CAPUFE: VERACRUZ*"
    elif item.get("es_lluvias"):
        header = "🌧️ *ALERTA PROTECCIÓN CIVIL / LLUVIAS*"
    else:
        header = "🚨 *ALERTA ESTRATÉGICA*"

    fuente = item.get("fuente", "Medio")
    autor = item.get("autor", "Redacción")
    url = item.get("url", "#")

    if ia:
        actor = ia.get("tipo_actor", "Medio")
        tema = ia.get("tema_principal", item.get("titulo", "Novedad"))
        muni = ia.get("municipio", item.get("municipio", "Estatal"))
        dep = ia.get("dependencia", item.get("dependencia", "Gobierno"))
        sent = ia.get("sentimiento", "Neutral")
        r_pol = ia.get("riesgo_politico", "Medio")
        r_med = ia.get("riesgo_mediatico", "Medio")
        vines = ia.get("resumen_ejecutivo", [])
        resumen_txt = "\n".join([f"• {v}" for v in vines]) if isinstance(vines, list) else f"• {vines}"
        impacto = ia.get("impacto_potencial", "Monitoreo preventivo")
        rec = ia.get("recomendacion_estrategica", "Mantener seguimiento")
    else:
        actor = "Medio"
        tema = item.get("titulo", "Novedad informativa")
        muni = item.get("municipio", "Estatal")
        dep = item.get("dependencia", "Gobierno")
        sent = "Pendiente de Análisis"
        r_pol = "Medio"
        r_med = "Medio"
        resumen_txt = f"• {item.get('contenido', '')[:220]}..."
        impacto = "En evaluación"
        rec = "Revisar alcance de la publicación"

    msg = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏛️ *Fuente:* {fuente}\n"
        f"✍️ *Autor:* {autor}\n"
        f"👤 *Tipo de actor:* `{actor}`\n"
        f"📌 *Tema:* {tema}\n"
        f"📍 *Municipio:* {muni}\n"
        f"🏢 *Dependencia involucrada:* {dep}\n"
        f"📊 *Postura:* {sent}\n"
        f"⚠️ *Riesgo Político:* `{r_pol}`\n"
        f"📢 *Riesgo Mediático:* `{r_med}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 *Resumen Ejecutivo:*\n{resumen_txt}\n\n"
        f"💥 *Impacto Potencial:*\n{impacto}\n\n"
        f"🎯 *Recomendación Estratégica:*\n{rec}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *Enlace:* {url}"
    )

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        r = requests.post(api_url, json=payload, timeout=10)
        if r.status_code == 400:
            payload["parse_mode"] = ""
            r = requests.post(api_url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

# ==============================================================================
# 6. PIPELINE DE RECOLECCIÓN (RSS + CAPUFE)
# ==============================================================================
def ejecutar_monitoreo():
    items = []

    # 1. Monitoreo CAPUFE Carreteras
    try:
        capufe_feed = feedparser.parse("https://nitter.privacydev.net/CAPUFE/rss")
        for e in capufe_feed.entries[:8]:
            txt = e.get("summary", "")
            if any(t in txt.lower() for t in ["veracruz", "cordoba", "orizaba", "maltrata", "coatzacoalcos", "isla", "tinaja", "minatitlan"]):
                link = e.get("link", "#").replace("nitter.privacydev.net", "x.com")
                items.append({
                    "hash_id": hashlib.sha256(f"CAPUFE_{link}".encode('utf-8')).hexdigest(),
                    "tipo_fuente": "CAPUFE",
                    "fuente": "CAPUFE Oficial (@CAPUFE)",
                    "autor": "@CAPUFE",
                    "titulo": "Reporte Vial Carretero CAPUFE",
                    "contenido": txt,
                    "url": link,
                    "fecha_publicacion": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                })
    except Exception:
        pass

    # 2. Medios RSS Estatales
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            nombre_medio = feed.feed.get("title", url.split("//")[-1].split("/")[0])
            for e in feed.entries[:6]:
                link = e.get("link", "")
                if not link: continue
                titulo = e.get("title", "").strip()
                resumen = e.get("summary", "").strip()
                h_id = hashlib.sha256(f"{link}_{titulo}".encode('utf-8')).hexdigest()

                items.append({
                    "hash_id": h_id,
                    "tipo_fuente": "RSS",
                    "fuente": nombre_medio,
                    "autor": e.get("author", nombre_medio),
                    "titulo": titulo,
                    "contenido": f"{titulo}. {resumen}",
                    "url": link,
                    "fecha_publicacion": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                })
        except Exception:
            continue

    # 3. Filtrado, Análisis IA y Persistencia SQLite
    for data in items:
        if item_ya_procesado(data["hash_id"]):
            continue

        reglas = evaluar_reglas(data.get("titulo", ""), data.get("contenido", ""))
        debe_ia = reglas["es_nahle"] or reglas["es_crisis"] or reglas["es_lluvias"] or data["tipo_fuente"] == "CAPUFE"

        ia = None
        if debe_ia:
            ia = analizar_con_gemini_estructurado(data.get("titulo", ""), data.get("contenido", ""), data["fuente"])
            enviar_alerta_telegram(data | reglas, ia)
            time.sleep(0.4)

        registro = {
            "hash_id": data["hash_id"],
            "fuente": data["fuente"],
            "autor": data.get("autor"),
            "titulo": data.get("titulo"),
            "url": data["url"],
            "fecha_publicacion": data["fecha_publicacion"],
            "es_nahle": reglas["es_nahle"],
            "es_crisis": reglas["es_crisis"],
            "es_lluvias": reglas["es_lluvias"],
            "municipio": ia.get("municipio") if ia else reglas["municipio"],
            "dependencia": ia.get("dependencia") if ia else reglas["dependencia"],
            "sentimiento": ia.get("sentimiento") if ia else None,
            "riesgo_politico": ia.get("riesgo_politico") if ia else None,
            "riesgo_mediatico": ia.get("riesgo_mediatico") if ia else None
        }
        guardar_item(registro)

# ==============================================================================
# 7. SERVIDOR FLASK Y WEBHOOK
# ==============================================================================
app = Flask(__name__)
init_db()

@app.route('/')
def home():
    return "Sistema de Inteligencia de Veracruz Operativo (Single-File SQLite)"

@app.route('/webhook', methods=['POST'])
def webhook():
    datos = request.get_json()
    if datos and "message" in datos:
        msg = datos["message"]
        if msg.get("from", {}).get("id") == CHAT_ID:
            txt = msg.get("text", "").strip()
            if txt in ["/escanear", "/scan"]:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                              json={"chat_id": CHAT_ID, "text": "🚀 _Iniciando escaneo integral estratégico..._", "parse_mode": "Markdown"})
                threading.Thread(target=ejecutar_monitoreo, daemon=True).start()
    return "OK", 200

def registrar_webhook():
    time.sleep(3)
    endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={endpoint}", timeout=8)
    except Exception:
        pass

def bucle_automatico():
    while True:
        try:
            ejecutar_monitoreo()
        except Exception:
            pass
        time.sleep(300) # Escaneo automático cada 5 minutos

if __name__ == "__main__":
    threading.Thread(target=bucle_automatico, daemon=True).start()
    threading.Thread(target=registrar_webhook, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
