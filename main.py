import feedparser
import requests
import json
import os
import re
import time
import calendar
import unicodedata
from datetime import datetime, timedelta
from flask import Flask
import threading

# ==============================================================================
# 1. CONFIGURACIÓN E IDENTIFICACIÓN (Variables de Entorno de Render)
# ==============================================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID", "1468116225"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

MODO_LISTA = "AUTO" 

# ==============================================================================
# 2. DEFINICIÓN DE LISTAS DE MEDIOS RSS
# ==============================================================================
LISTA_1 = [
    "https://veracruz.quadratin.com.mx/feed/",
    "https://golpepolitico.com/feed/",
    "https://imagendeveracruz.mx/feed/",
    "https://niusdeveracruz.com/feed/",
    "https://e-veracruz.mx/rss",
    "https://forocoatza.com/feed/",
    "https://www.lapoliticaenrosa.com/feed/",
    "https://coatzadigital.mx/feed/",
    "https://surestesur.com/feed/",
    "https://www.imagenypolitica.com/feed/",
    "https://diariodelistmo.com/feed/",
    "https://sietediasnoticias.com/feed/",
    "https://laopinion.net/feed/",
    "https://heraldodexalapa.com.mx/feed/",
    "https://www.jornada.com.mx/rss/edicion.xml",
    "https://www.razon.com.mx/feed/",
    "https://www.excelsior.com.mx/rss.xml",
    "https://mvsnoticias.com/feed/"
]

LISTA_2 = [
    "https://www.jornada.com.mx/rss/edicion.xml",
    "https://www.excelsior.com.mx/rss.xml"
]

LISTA_FIN_DE_SEMANA = [
    "https://golpepolitico.com/feed/",
    "https://imagendelgolfo.mx/feed/",
    "https://www.elbuentono.com.mx/feed/",
    "https://veracruz.quadratin.com.mx/feed/",
    "https://www.alcalorpolitico.com/rss/",
    "https://www.diariodexalapa.com.mx/rss/",
    "https://horacero.mx/feed/",
    "https://diariodelistmo.com/feed/",
    "https://ventanaver.mx/feed/",
    "https://referentemx.com/feed/",
    "https://vanguardiaveracruz.com/feed/",
    "https://noreste.net/feed/",
    "https://imagendeveracruz.mx/feed/",
    "https://www.olivanoticias.com/feed/",
    "https://www.masnoticias.mx/feed/",
    "https://cambiodigitalnoticias.com/feed/"
]

# NUEVA LISTA 3 ADAPTADA A FORMATO ENRUTADOR RSS
LISTA_3 = [
    "https://www.masnoticias.mx/feed/",
    "https://xeu.mx/feed/",
    "https://horacero.mx/feed/",
    "https://jornadaveracruz.com.mx/feed/",
    "https://elementosmx.com/feed/",
    "https://tvsureste.com/feed/",
    "https://www.politicaaldia.com/feed/",
    "https://vanguardiaveracruz.com/feed/",
    "https://www.firmas.mx/feed/",
    "https://cambiodigitalnoticias.com/feed/",
    "https://www.diariodexalapa.com.mx/rss/",
    "https://x.gd/EDfoM",  # Redirección directa del acortador del Piñero
    "https://cronicadelpoder.com/feed/",
    "https://siguenzacomunica.com/feed/",
    "https://www.cronicaveracruz.com/feed/",
    "https://noticiaslafuente.com.mx/feed/",
    "https://alornoticias.com.mx/feed/",
    "https://coatzahoy.com/feed/",
    "https://olmecamultimedios.com.mx/feed/",
    "https://graficoaldia.mx/feed/",
    "https://diariolostuxtlas.com/feed/",
    "https://diariodelistmo.com/feed/",
    "https://www.elbuentono.com.mx/feed/",
    "https://versiones.com.mx/feed/",
    "https://formato7.com/feed/",
    "https://lasillarota.com/veracruz/feed/",
    "https://presencianoticias.com/feed/",
    "https://laizquierdanoticias.com.mx/feed/"
]

# ==============================================================================
# 3. PARÁMETROS DE FILTRADO GEOGRÁFICO Y POLÍTICO
# ==============================================================================
PARAMETROS = [
    "Inundación", "Rocio Nahle", "Nahle", "Mañanera", "DIF Estatal", "DIF Veracruz",
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
    "Zacualpan", "Zaragoza", "Zentla", "Zongolica", "Zontecomatlán", "Zozocolco"
]

ARCHIVO_HISTORIAL = "historial_noticias.json"
ARCHIVO_MANUALES = "noticias_manuales.json"

# ==============================================================================
# 4. FUNCIONES LÓGICAS Y CONEXIÓN CON IA GEMINI
# ==============================================================================
def normalizar_texto(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

def determinar_lista_medios():
    if MODO_LISTA == "LISTA_1": return LISTA_1, "Lista 1 (Manual)"
    if MODO_LISTA == "LISTA_2": return LISTA_2, "Lista 2 (Manual)"
    if MODO_LISTA == "LISTA_3": return LISTA_3, "Lista 3 (Manual)"
    return (LISTA_2, "Lista 2 (Fin de Semana)") if datetime.today().weekday() >= 5 else (LISTA_1, "Lista 1 (Entre Semana)")

def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def guardar_historial(historial):
    if len(historial) > 1500: historial = historial[-1500:]
    try:
        with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f: json.dump(historial, f, ensure_ascii=False, indent=4)
    except: pass

def cargar_noticias_manuales():
    if os.path.exists(ARCHIVO_MANUALES):
        try:
            with open(ARCHIVO_MANUALES, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def guardar_noticias_manuales(lista):
    try:
        with open(ARCHIVO_MANUALES, "w", encoding="utf-8") as f: json.dump(lista, f, ensure_ascii=False, indent=4)
    except: pass

def evaluar_texto(texto, palabras_clave):
    texto_norm = normalizar_texto(texto)
    for kw in palabras_clave:
        kw_norm = normalizar_texto(kw)
        if " " in kw_norm:
            if kw_norm in texto_norm: return True, kw
        else:
            if re.search(rf"\b{re.escape(kw_norm)}\b", texto_norm): return True, kw
    return False, None

def analizar_nota_con_ia(titulo, resumen):
    if not GEMINI_API_KEY: return "⚠️ Error: GEMINI_API_KEY no configurada en Render."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        f"Eres un analista de comunicación política experto en el estado de Veracruz. "
        f"Analiza la siguiente nota informativa (Título y/o Resumen) y genera estrictamente lo siguiente:\n"
        f"1) Un resumen ejecutivo muy conciso en exactamente 3 viñetas cortas.\n"
        f"2) Sentimiento de la nota hacia la administración pública (Positivo, Neutral o Negativo).\n"
        f"3) Nivel de Riesgo Político o Potencial Crisis para el Gobierno del Estado (Bajo, Medio o Alto) con una breve línea del porqué.\n\n"
        f"Título: {titulo}\n"
        f"Contexto: {resumen}\n\n"
        f"Responde usando formato Markdown limpio. Sé directo, institucional y preciso."
    )
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return f"⚠️ Error {response.status_code} de Google Gemini."
    except:
        return f"⚠️ Error de conexión con la IA."

def enviar_mensaje_telegram(texto):
    if not TELEGRAM_TOKEN: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 400:
            payload["parse_mode"] = ""
            response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except: return False

def ejecutar_busqueda_prioritaria(tema_objetivo):
    medios_activos, _ = determinar_lista_medios()
    palabras_clave = [normalizar_texto(w) for w in tema_objetivo.split() if len(w) >= 3]
    if not palabras_clave: return 0
    coincidencias = 0
    
    for url_rss in medios_activos:
        try:
            feed = feedparser.parse(url_rss)
            nombre_medio = feed.feed.get("title", url_rss.split("//")[-1].split("/")[0])
            for entrada in feed.entries:
                titulo = entrada.get("title", "")
                resumen = entrada.get("summary", "")
                texto_analisis_norm = normalizar_texto(titulo + " " + resumen)
                
                if all(palabra in texto_analisis_norm for palabra in palabras_clave):
                    link = entrada.get("link", "#")
                    analisis_ia = analizar_nota_con_ia(titulo, resumen)
                    
                    fecha_parsed = entrada.get("published_parsed") or entrada.get("updated_parsed")
                    if fecha_parsed:
                        dt_utc = datetime(*fecha_parsed[:6])
                        dt_veracruz = dt_utc - timedelta(hours=6)
                        timestamp_noticia = dt_veracruz.strftime("%H:%M del %d/%m/%Y")
                    else:
                        timestamp_noticia = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M del %d/%m/%Y")
                    
                    mensaje = (
                        f"🔥 *HALLAZGO PRIORITARIO / COMUNICADO*\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📌 *Medio:* {nombre_medio}\n"
                        f"🎯 *Idea Central Investigada:* `{tema_objetivo}`\n"
                        f"📝 *Título:* {titulo}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🧠 *ANÁLISIS DE INTELIGENCIA (IA PRO):*\n"
                        f"{analisis_ia}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🕒 _Publicado a las {timestamp_noticia}_\n"
                        f"🔗 [Abrir Nota del Comunicado]({link})"
                    )
                    enviar_mensaje_telegram(mensaje)
                    coincidencias += 1
                    time.sleep(0.5)
        except: continue
    return coincidencias

def ejecutar_monitoreo_silencioso(usar_ia=False, horas_atras=None, lista_forzada=None):
    if lista_forzada:
        medios_activos = lista_forzada
        nombre_lista = "Lista Asignada"
    else:
        medios_activos, nombre_lista = determinar_lista_medios()
        
    historial = cargar_historial()
    noticias_manuales = cargar_noticias_manuales()
    alertas_enviadas = 0
    
    if horas_atras:
        epoch_threshold = calendar.timegm(time.gmtime()) - (horas_atras * 3600)
    else:
        ahora_utc = datetime.utcnow()
        ahora_veracruz = ahora_utc - timedelta(hours=6)
        if ahora_veracruz.hour >= 22:
            fecha_10pm_veracruz = ahora_veracruz.replace(hour=22, minute=0, second=0, microsecond=0)
        else:
            fecha_10pm_veracruz = (ahora_veracruz - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
        epoch_threshold = calendar.timegm((fecha_10pm_veracruz + timedelta(hours=6)).utctimetuple())

    for url_rss in medios_activos:
        try:
            feed = feedparser.parse(url_rss)
            nombre_medio = feed.feed.get("title", url_rss.split("//")[-1].split("/")[0])
            for entrada in feed.entries:
                link = entrada.get("link")
                if not link or link in historial: continue
                
                titulo = entrada.get("title", "")
                resumen = entrada.get("summary", "")
                titulo_norm = normalizar_texto(titulo)
                
                if any(linea_manual in titulo_norm for linea_manual in noticias_manuales if len(linea_manual) > 8):
                    continue
                
                fecha_parsed = entrada.get("published_parsed") or entrada.get("updated_parsed")
                timestamp_noticia = None
                
                if fecha_parsed:
                    try:
                        nota_epoch = calendar.timegm(fecha_parsed)
                        if nota_epoch < epoch_threshold: continue 
                        dt_utc = datetime(*fecha_parsed[:6])
                        dt_veracruz = dt_utc - timedelta(hours=6)
                        timestamp_noticia = dt_veracruz.strftime("%H:%M del %d/%m/%Y")
                    except: pass
                
                if not timestamp_noticia:
                    timestamp_noticia = (datetime.utcnow() - timedelta(hours=6)).strftime("%H:%M del %d/%m/%Y")

                hizo_match, kw_detectada = evaluar_texto(titulo, PARAMETROS)
                if not hizo_match: hizo_match, kw_detectada = evaluar_texto(resumen, PARAMETROS)
                
                if hizo_match:
                    if usar_ia:
                        analisis_ia = analizar_nota_con_ia(titulo, resumen)
                        mensaje = (
                            f"🚨 *ALERTA CRÍTICA [{nombre_lista.upper()}] (CON IA)*\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"📌 *Medio:* {nombre_medio}\n"
                            f"🎯 *Match:* `{kw_detectada}`\n"
                            f"📝 *Título:* {titulo}\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"🧠 *ANÁLISIS DE INTELIGENCIA (IA PRO):*\n"
                            f"{analisis_ia}\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"🕒 _Publicado a las {timestamp_noticia}_\n"
                            f"🔗 [Abrir Nota Completa]({link})"
                        )
                    else:
                        mensaje = (
                            f"🚨 *ALERTA CRÍTICA [{nombre_lista.upper()}] (ESTÁNDAR)*\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"📌 *Medio:* {nombre_medio}\n"
                            f"🎯 *Match:* `{kw_detectada}`\n"
                            f"📝 *Título:* {titulo}\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"🕒 _Publicado a las {timestamp_noticia}_\n"
                            f"🔗 [Abrir Nota Completa]({link})"
                        )
                    enviar_mensaje_telegram(mensaje)
                    alertas_enviadas += 1
                    time.sleep(0.4)
                historial.append(link)
        except: continue
            
    guardar_historial(historial)
    return alertas_enviadas, nombre_lista

# ==============================================================================
# 5. ESCUCHA DE TELEGRAM EN SEGUNDO PLANO
# ==============================================================================
def iniciar_interfaz_bot():
    global MODO_LISTA
    offset = 0
    time.sleep(5)  
    enviar_mensaje_telegram("🤖 *Bot RSS de Monitoreo Web Operando de forma Ligera en Render*")

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=20"
            respuesta = requests.get(url, timeout=25).json()
            if not respuesta.get("ok") or not respuesta.get("result"):
                time.sleep(1)
                continue
            for actualizacion in respuesta["result"]:
                offset = actualizacion["update_id"] + 1
                mensaje = actualizacion.get("message", {})
                usuario_id = mensaje.get("from", {}).get("id")
                texto_comando = mensaje.get("text", "").strip()
                
                if usuario_id != CHAT_ID: continue
                
                if texto_comando == "/start" or texto_comando == "/ayuda":
                    menu = (
                        "📱 *Panel de Control RSS (Render)*\n\n"
                        "📰 *MEDIOS WEB (RSS):*\n"
                        "👉 `/escanear` o `/escanear X` : Rastreo estándar Lista Regular (Sin IA).\n"
                        "👉 `/escanearIA` o `/escanearIA X` : Rastreo Lista Regular con IA Pro.\n"
                        "👉 `/escaneard` o `/escaneard X` : Rastreo estándar Lista Fin de Semana.\n"
                        "👉 `/escanearb` o `/escanearb X` : Rastreo estándar Lista 3 (Nuevos Medios).\n"
                        "👉 `/buscar IDEA` : Localizar comunicados urgentes.\n"
                        "👉 `/ayer BLOQUE` : Bloquear notas de hoy.\n\n"
                        "⚙️ *SISTEMA:*\n"
                        "👉 `/modo` : Ver o forzar listas.\n"
                        "👉 `/limpiar` : Vaciar historial de enlaces web."
                    )
                    enviar_mensaje_telegram(menu)
                    
                elif texto_comando.startswith("/ayer"):
                    contenido = re.sub(r'^/ayer[\s\n]*', '', texto_comando).strip()
                    if contenido:
                        lineas = contenido.split("\n")
                        nuevas_notas = [normalizar_texto(l.strip()) for l in lineas if l.strip()]
                        existentes = cargar_noticias_manuales()
                        existentes.extend(nuevas_notas)
                        existentes = list(set(existentes))
                        guardar_noticias_manuales(existentes)
                        enviar_mensaje_telegram(f"✅ Registradas `{len(nuevas_notas)}` notas en el filtro.")
                    else:
                        guardar_noticias_manuales([])
                        enviar_mensaje_telegram("🗑️ Filtro de notas manuales vaciado.")
                        
                elif texto_comando.startswith("/buscar "):
                    partes = texto_comando.split(" ", 1)
                    if len(partes) > 1:
                        tema_a_rastrear = partes[1].strip()
                        enviar_mensaje_telegram(f"🔍 _Buscando coincidencias para:_ `{tema_a_rastrear}`...")
                        encontrados = ejecutar_busqueda_prioritaria(tema_a_rastrear)
                        enviar_mensaje_telegram(f"✅ *Búsqueda terminada. Hallados:* `{encontrados}`")
                        
                elif texto_comando.startswith("/escanearb"):
                    arg = texto_comando.replace("/escanearb", "").strip()
                    num = re.findall(r'\d+', arg)
                    horas = int(num[0]) if num else None
                    if horas:
                        enviar_mensaje_telegram(f"🔍 _Rastreando Lista 3 (Últimas {horas} horas)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=False, horas_atras=horas, lista_forzada=LISTA_3)
                    else:
                        enviar_mensaje_telegram("🔍 _Rastreando Lista 3 (Corte desde 10:00 PM)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=False, lista_forzada=LISTA_3)
                    enviar_mensaje_telegram(f"✅ *Escaneo Lista 3 Terminado.*\n✨ Alertas enviadas: `{total}`")
                        
                elif texto_comando.startswith("/escaneard"):
                    arg = texto_comando.replace("/escaneard", "").strip()
                    num = re.findall(r'\d+', arg)
                    horas = int(num[0]) if num else None
                    if horas:
                        enviar_mensaje_telegram(f"🔍 _Rastreando Lista Fin de Semana (Últimas {horas} horas)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=False, horas_atras=horas, lista_forzada=LISTA_FIN_DE_SEMANA)
                    else:
                        enviar_mensaje_telegram("🔍 _Rastreando Lista Fin de Semana (Corte desde 10:00 PM)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=False, lista_forzada=LISTA_FIN_DE_SEMANA)
                    enviar_mensaje_telegram(f"✅ *Escaneo Fin de Semana Terminado.*\n✨ Alertas enviadas: `{total}`")
                    
                elif texto_comando.startswith("/escanearIA"):
                    arg = texto_comando.replace("/escanearIA", "").strip()
                    num = re.findall(r'\d+', arg)
                    horas = int(num[0]) if num else None
                    if horas:
                        enviar_mensaje_telegram(f"🔍 _Rastreando portales regulares (Últimas {horas} horas con IA)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=True, horas_atras=horas)
                    else:
                        enviar_mensaje_telegram("🔍 _Rastreando portales regulares (Corte desde 10:00 PM con IA)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=True)
                    enviar_mensaje_telegram(f"✅ *Escaneo Terminado.*\n✨ Alertas procesadas por IA Pro: `{total}`")
                    
                elif texto_comando.startswith("/escanear"):
                    arg = texto_comando.replace("/escanear", "").strip()
                    num = re.findall(r'\d+', arg)
                    horas = int(num[0]) if num else None
                    if horas:
                        enviar_mensaje_telegram(f"🔍 _Rastreando portales regulares (Últimas {horas} horas)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=False, horas_atras=horas)
                    else:
                        enviar_mensaje_telegram("🔍 _Rastreando portales regulares (Corte desde 10:00 PM)..._")
                        total, _ = ejecutar_monitoreo_silencioso(usar_ia=False)
                    enviar_mensaje_telegram(f"✅ *Escaneo Terminado.*\n✨ Alertas enviadas: `{total}`")
                    
                elif texto_comando == "/modo":
                    msg_modo = f"⚙️ Modo actual: `{MODO_LISTA}`\n\n👉 `/set_auto` | `/set_lista1` | `/set_lista2` | `/set_lista3`"
                    enviar_mensaje_telegram(msg_modo)
                elif texto_comando == "/set_auto":
                    MODO_LISTA = "AUTO"
                    enviar_mensaje_telegram("🔄 Modo: `AUTOMÁTICO`")
                elif texto_comando == "/set_lista1":
                    MODO_LISTA = "LISTA_1"
                    enviar_mensaje_telegram("📌 Modo: `FORZAR LISTA 1`")
                elif texto_comando == "/set_lista2":
                    MODO_LISTA = "LISTA_2"
                    enviar_mensaje_telegram("📌 Modo: `FORZAR LISTA 2`")
                elif texto_comando == "/set_lista3":
                    MODO_LISTA = "LISTA_3"
                    enviar_mensaje_telegram("📌 Modo: `FORZAR LISTA 3`")
                elif texto_comando == "/limpiar":
                    if os.path.exists(ARCHIVO_HISTORIAL): os.remove(ARCHIVO_HISTORIAL)
                    enviar_mensaje_telegram("🗑 *Historial de enlaces limpio.*")
        except: time.sleep(2)

# ==============================================================================
# 6. SERVIDOR WEB (Keep Alive de Render)
# ==============================================================================
web_app = Flask('')
@web_app.route('/')
def home(): return "Servicio RSS Operando de forma Ligera en Render"

if __name__ == "__main__":
    threading.Thread(target=iniciar_interfaz_bot, daemon=True).start()
    puerto = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=puerto)
