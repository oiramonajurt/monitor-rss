import os
import re
import json
import time
import hashlib
import requests
import feedparser
import threading
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, request
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.orm import declarative_base, sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler

# ==============================================================================
# 1. CONFIGURACIÓN Y VARIABLES DE ENTORNO
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = int(os.environ.get("CHAT_ID", "1468116225"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://monitor-rss-service.onrender.com")

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif not DATABASE_URL:
    DATABASE_URL = "sqlite:///inteligencia_local.db"

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==============================================================================
# 2. BASE DE DATOS (PostgreSQL / SQLite fallback)
# ==============================================================================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generar_hash(texto: str) -> str:
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

class ItemMonitoreo(Base):
    __tablename__ = "items_monitoreo"

    id = Column(Integer, primary_key=True, index=True)
    hash_id = Column(String(64), unique=True, index=True, nullable=False)
    tipo_fuente = Column(String(20), index=True)
    fuente_nombre = Column(String(150), index=True)
    autor = Column(String(150), nullable=True)
    tipo_actor = Column(String(50), default="Medio", index=True)
    titulo = Column(Text, nullable=True)
    contenido = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    fecha_publicacion = Column(DateTime, default=datetime.utcnow, index=True)
    
    es_alerta_gobernadora = Column(Boolean, default=False, index=True)
    es_crisis = Column(Boolean, default=False, index=True)
    es_lluvias_pc = Column(Boolean, default=False, index=True)
    
    sentimiento = Column(String(20), nullable=True)
    riesgo_politico = Column(String(20), nullable=True)
    riesgo_mediatico = Column(String(20), nullable=True)
    municipio_detectado = Column(String(100), nullable=True)
    dependencia_detectada = Column(String(100), nullable=True)
    resumen_ejecutivo = Column(Text, nullable=True)
    impacto_potencial = Column(Text, nullable=True)
    recomendacion_estrategica = Column(Text, nullable=True)
    alerta_enviada = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# ==============================================================================
# 3. LISTAS DE FUENTES Y REGLAS DE NEGOCIO
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

ACTORES_MAP = {
    "miguel angel yunes": "Opositor", "pepe yunes": "Opositor", "hector yunes": "Opositor",
    "julen rementeria": "Opositor", "indira rosales": "Opositor", "patricia lobeira": "Alcalde / Opositor",
    "fernando yunes": "Opositor", "sergio cadena": "Opositor", "manuel huerta": "Senador / Morena",
    "billie parker": "Periodista", "mussio cardenas": "Columnista", "luis velazquez": "Columnista",
    "raymundo jimenez": "Columnista", "claudia guerrero": "Periodista"
}

KEYWORDS_CRISIS_NAHLE = [
    "corrupcion", "desvio", "denuncia", "escandalo", "crimen", "inseguridad",
    "protesta", "manifestacion", "auditoria", "desabasto", "violencia", "bloqueo"
]

KEYWORDS_LLUVIAS = [
    "inundacion", "inundaciones", "desbordamiento", "deslave", "deslaves",
    "derrumbe", "derrumbes", "evacuacion", "refugio temporal", "rio desbordado"
]

# ==============================================================================
# 4. FUNCIONES DE PROCESAMIENTO Y ANÁLISIS
# ==============================================================================
def normalizar(texto: str) -> str:
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

def evaluar_reglas(titulo: str, contenido: str):
    texto_norm = normalizar(f"{titulo} {contenido}")
    
    es_nahle = "nahle" in texto_norm or "rocio nahle" in texto_norm
    tiene_crisis_nahle = any(kw in texto_norm for kw in KEYWORDS_CRISIS_NAHLE)
    es_alerta_nahle = es_nahle and tiene_crisis_nahle
    
    es_lluvias = any(kw in texto_norm for kw in KEYWORDS_LLUVIAS)
    es_crisis = tiene_crisis_nahle or es_lluvias or any(w in texto_norm for w in ["homicidio", "secuestro", "bloqueo vial", "fosa"])
    
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
        "es_alerta_nahle": es_alerta_nahle,
        "es_lluvias": es_lluvias,
        "es_crisis": es_crisis,
        "municipio": muni,
        "dependencia": dep
    }

def analizar_con_gemini(titulo: str, contenido: str, fuente: str):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Actúa como Analista Senior de Inteligencia Política y Manejo de Crisis del Gobierno de Veracruz.
    Analiza esta nota y devuelve EXCLUSIVAMENTE un JSON con:
    {{
      "tipo_actor": "Medio | Periodista | Columnista | Opositor | Funcionario | Alcalde | Ciudadano",
      "sentimiento": "Positivo | Neutral | Negativo | Muy negativo",
      "riesgo_politico": "Bajo | Medio | Alto | Crítico",
      "riesgo_mediatico": "Bajo | Medio | Alto | Crítico",
      "tema_principal": "Tema en 6 palabras",
      "municipio": "Municipio involucrado o 'Estatal'",
      "dependencia": "Dependencia involucrada o 'Ninguna'",
      "resumen_ejecutivo": ["Viñeta 1 corta", "Viñeta 2 corta", "Viñeta 3 corta"],
      "impacto_potencial": "Riesgo en una frase",
      "recomendacion_estrategica": "Acción recomendada"
    }}
    Nota: {fuente} - {titulo}. {contenido}
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
# 5. MENSAJERÍA TELEGRAM
# ==============================================================================
def enviar_alerta_telegram(item: dict, ia: dict = None):
    if not TELEGRAM_TOKEN: return False

    if item.get("es_alerta_nahle"):
        header = "🔥 *ALERTA CRÍTICA: GOBERNADORA ROCÍO NAHLE*"
    elif item.get("tipo_fuente") == "CAPUFE":
        header = "🛣️ *ALERTA VIAL CAPUFE: VERACRUZ*"
    elif item.get("es_lluvias"):
        header = "🌧️ *ALERTA PROTECCIÓN CIVIL / LLUVIAS*"
    else:
        header = "🚨 *ALERTA ESTRATÉGICA*"

    fuente = item.get("fuente_nombre", "Medio")
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
        impacto = ia.get("impacto_potencial", "Seguimiento preventivo")
        rec = ia.get("recomendacion_estrategica", "Mantener monitoreo")
    else:
        actor = "Medio"
        tema = item.get("titulo", "Novedad informativa")
        muni = item.get("municipio", "Estatal")
        dep = item.get("dependencia", "Gobierno")
        sent = "Neutral"
        r_pol = "Medio"
        r_med = "Medio"
        resumen_txt = f"• {item.get('contenido', '')[:200]}..."
        impacto = "En análisis"
        rec = "Revisar publicación"

    msg = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏛️ *Fuente:* {fuente}\n"
        f"✍️ *Autor:* {autor}\n"
        f"👤 *Tipo de actor:* `{actor}`\n"
        f"📌 *Tema:* {tema}\n"
        f"📍 *Municipio:* {muni}\n"
        f"🏢 *Dependencia:* {dep}\n"
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
# 6. PIPELINE PRINCIPAL DE INGESTA
# ==============================================================================
def ejecutar_ciclo():
    db = SessionLocal()
    items = []
    
    # 1. Scraping CAPUFE
    try:
        capufe_feed = feedparser.parse("https://nitter.privacydev.net/CAPUFE/rss")
        for e in capufe_feed.entries[:10]:
            sum_txt = e.get("summary", "")
            if any(t in sum_txt.lower() for t in ["veracruz", "cordoba", "orizaba", "maltrata", "coatzacoalcos", "isla", "tinaja"]):
                items.append({
                    "hash_id": generar_hash(f"CAPUFE_{e.get('link')}"),
                    "tipo_fuente": "CAPUFE",
                    "fuente_nombre": "CAPUFE Oficial",
                    "autor": "@CAPUFE",
                    "titulo": "Aviso Carretero CAPUFE",
                    "contenido": sum_txt,
                    "url": e.get("link", "#").replace("nitter.privacydev.net", "x.com"),
                    "fecha_publicacion": datetime.utcnow()
                })
    except Exception:
        pass

    # 2. Ingesta RSS
    limite = datetime.utcnow() - timedelta(hours=3)
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            nombre_medio = feed.feed.get("title", url.split("//")[-1].split("/")[0])
            for e in feed.entries[:8]:
                link = e.get("link", "")
                if not link: continue
                
                titulo = e.get("title", "").strip()
                resumen = e.get("summary", "").strip()
                h_id = generar_hash(f"{link}_{titulo}")
                
                items.append({
                    "hash_id": h_id,
                    "tipo_fuente": "RSS",
                    "fuente_nombre": nombre_medio,
                    "autor": e.get("author", nombre_medio),
                    "titulo": titulo,
                    "contenido": f"{titulo}. {resumen}",
                    "url": link,
                    "fecha_publicacion": datetime.utcnow()
                })
        except Exception:
            continue

    # 3. Procesamiento y Deduplicación en Base de Datos
    for data in items:
        if db.query(ItemMonitoreo).filter_by(hash_id=data["hash_id"]).first():
            continue

        reglas = evaluar_reglas(data.get("titulo", ""), data.get("contenido", ""))
        debe_ia = reglas["es_alerta_nahle"] or reglas["es_crisis"] or reglas["es_lluvias"] or data["tipo_fuente"] == "CAPUFE"
        
        ia = None
        if debe_ia:
            ia = analizar_con_gemini(data.get("titulo", ""), data.get("contenido", ""), data["fuente_nombre"])
            enviar_alerta_telegram(data | reglas, ia)
            time.sleep(0.5)

        nuevo = ItemMonitoreo(
            hash_id=data["hash_id"],
            tipo_fuente=data["tipo_fuente"],
            fuente_nombre=data["fuente_nombre"],
            autor=data.get("autor"),
            titulo=data.get("titulo"),
            contenido=data.get("contenido"),
            url=data["url"],
            fecha_publicacion=data.get("fecha_publicacion"),
            es_alerta_gobernadora=reglas["es_alerta_nahle"],
            es_crisis=reglas["es_crisis"],
            es_lluvias_pc=reglas["es_lluvias"],
            municipio_detectado=ia.get("municipio") if ia else reglas["municipio"],
            dependencia_detectada=ia.get("dependencia") if ia else reglas["dependencia"],
            sentimiento=ia.get("sentimiento") if ia else None,
            riesgo_politico=ia.get("riesgo_politico") if ia else None,
            riesgo_mediatico=ia.get("riesgo_mediatico") if ia else None,
            alerta_enviada=debe_ia
        )
        db.add(nuevo)

    try:
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

# ==============================================================================
# 7. SERVIDOR FLASK, SCHEDULER Y WEBHOOK
# ==============================================================================
app = Flask(__name__)
scheduler = BackgroundScheduler(daemon=True)

@app.route('/')
def home():
    return "Sistema de Inteligencia de Veracruz v2.0 - Activo"

@app.route('/webhook', methods=['POST'])
def webhook():
    datos = request.get_json()
    if datos and "message" in datos:
        msg = datos["message"]
        if msg.get("from", {}).get("id") == CHAT_ID:
            txt = msg.get("text", "").strip()
            if txt == "/escanear":
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                              json={"chat_id": CHAT_ID, "text": "🚀 _Iniciando rastreo integral..._", "parse_mode": "Markdown"})
                threading.Thread(target=ejecutar_ciclo, daemon=True).start()
    return "OK", 200

def registrar_webhook():
    time.sleep(3)
    endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={endpoint}", timeout=8)
    except Exception:
        pass

if __name__ == "__main__":
    scheduler.add_job(ejecutar_ciclo, 'interval', minutes=5, id='monitor_veracruz', replace_existing=True)
    scheduler.start()
    threading.Thread(target=registrar_webhook, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
