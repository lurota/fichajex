import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Servidor HTTP ligero para el health check de Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot activo y escuchando")

    def log_message(self, format, *args):
        pass  # Silencia los logs de peticiones HTTP para mantener limpia la consola

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Iniciar servidor web en un hilo independiente
threading.Thread(target=run_health_server, daemon=True).start()

# --- Configuración de Logs ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Carga de variables de entorno
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://transfermarkt-api.fly.dev")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy tu bot de Transfermarkt.\n\n"
        "Comandos disponibles:\n"
        "• `/fichaje <nombre_jugador>` - Consulta el historial de traspasos de un jugador.",
        parse_mode="Markdown"
    )

async def buscar_fichaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Por favor, introduce el nombre de un jugador.\nEjemplo: `/fichaje Vinicius`", 
            parse_mode="Markdown"
        )
        return

    nombre_jugador = " ".join(context.args)
    await update.message.reply_text(f"Buscando datos de *{nombre_jugador}*...", parse_mode="Markdown")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        # 1. Búsqueda del ID del jugador
        base_url = API_BASE_URL.rstrip('/')
        search_res = requests.get(f"{base_url}/players/search/{nombre_jugador}", headers=headers, timeout=10)
        
        if search_res.status_code != 200 or not search_res.json().get("results"):
            await update.message.reply_text("No se encontró ningún jugador con ese nombre.")
            return

        jugador = search_res.json()["results"][0]
        player_id = jugador["id"]
        player_name = jugador["name"]

        # 2. Búsqueda de los fichajes del jugador
        transfers_res = requests.get(f"{base_url}/players/{player_id}/transfers", headers=headers, timeout=10)
        
        if transfers_res.status_code == 200:
            data = transfers_res.json()
            transfers = data.get("transfers", [])
            
            if not transfers:
                await update.message.reply_text(f"No hay registros de traspasos disponibles para {player_name}.")
                return

            # Extraer el último traspaso registrado
            ultimo = transfers[0]
            origen = ultimo.get("from", {}).get("clubName", "Desconocido")
            destino = ultimo.get("to", {}).get("clubName", "Desconocido")
            precio = ultimo.get("fee", "N/A")
            temporada = ultimo.get("season", "N/A")

            mensaje = (
                f"⚽ *Fichaje de {player_name}*\n\n"
                f"• *Temporada:* {temporada}\n"
                f"• *Origen:* {origen}\n"
                f"• *Destino:* {destino}\n"
                f"• *Coste/Valor:* {precio}\n"
            )
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        else:
            await update.message.reply_text("Ocurrió un error al consultar el historial de fichajes.")

    except Exception as e:
        logging.error(f"Error en la petición: {e}")
        await update.message.reply_text("Hubo un problema de conexión al consultar la API.")

def main():
    if not TOKEN:
        logging.error("ERROR CRÍTICO: La variable TELEGRAM_BOT_TOKEN no está configurada.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fichaje", buscar_fichaje))
    
    logging.info("Bot en marcha y escuchando peticiones...")
    app.run_polling()

if __name__ == "__main__":
    main()
