import os
import threading
import json
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
PORT = int(os.getenv("PORT", 5050))
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

bot_status = {"running": False, "last_log": "Инициализация системы..."}

def background_worker():
    global bot_status
    bot_status["running"] = True
    bot_status["last_log"] = "Воркер запущен..."
    try:
        from bot_worker import run_automation
        run_automation(headless=True)
        bot_status["last_log"] = "Воркер успешно завершил работу."
    except Exception as e:
        bot_status["last_log"] = f"Ошибка воркера: {str(e)}"
    finally:
        bot_status["running"] = False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(bot_status)

@app.route("/api/start", methods=["POST"])
def api_start():
    if bot_status["running"]:
        return jsonify({"success": False, "message": "Воркер уже запущен!"})
    
    thread = threading.Thread(target=background_worker)
    thread.daemon = True
    thread.start()
    return jsonify({"success": True, "message": "Воркер запущен в фоновом режиме."})

@app.route("/api/accounts", methods=["GET"])
def api_accounts():
    accs = []
    path = "data/success_accounts.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        accs.append(json.loads(line))
                    except:
                        pass
    return jsonify({"success": True, "accounts": accs})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=DEBUG)
