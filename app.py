import os, time, json, threading, requests
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent

def load_env_file(path):
    if not path.exists(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env_file(BASE_DIR / ".env")
API_KEY = os.environ.get("GRIZZLY_API_KEY", "")
BASE_URL = "https://api.grizzlysms.com/stubs/handler_api.php"
NEW_PASSWORD = "Mega_Park9"
LOG_FILE = BASE_DIR / "success_accounts.json"

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

bot_status = {"running": False, "last_action": "Остановлен", "total_used": 0, "failed": 0, "success": 0, "logs": []}
bot_thread = None

def add_log(msg):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    bot_status["logs"].insert(0, line)
    if len(bot_status["logs"]) > 50: bot_status["logs"].pop()

def api_call(**params):
    try:
        return requests.get(BASE_URL, params={"api_key": API_KEY, **params}, timeout=30).text.strip()
    except: return None

def get_balance():
    res = api_call(action="getBalance")
    if res and res.startswith("ACCESS_BALANCE"): return res.split(":", 1)[1]
    return "0.1000"

def save_to_log(phone, password):
    rec = {"phone": phone, "password": password, "status": "Success_Restored", "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    data = []
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "r", encoding="utf-8") as f: data = json.load(f)
    except: pass
    data.append(rec)
    with open(LOG_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def worker_loop(service, country):
    global bot_status
    bot_status["running"] = True
    add_log("Воркер запущен. Покупаем строго 1 номер...")
    
    aid, phone, code = None, None, None
    try:
        add_log("Запрос номера у GrizzlySMS...")
        res = api_call(action="getNumber", service=service, country=country)
        if not res or not res.startswith("ACCESS_NUMBER"):
            add_log(f"Нет номеров ({res}). Остановка.")
            bot_status["running"] = False
            return
        _, aid, phone = res.split(":", 2)
        bot_status["total_used"] += 1
        add_log(f"Куплен номер: +{phone} (ID: {aid})")
        pure_phone = phone[-10:]

        add_log("Подключаемся к уже открытому браузеру Dolphin...")
        cdp_url = None
        for port in [9222, 9223, 3001, 3002]:
            try:
                r = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=2)
                if r.status_code == 200:
                    cdp_url = f"http://127.0.0.1:{port}"
                    break
            except: pass

        if not cdp_url:
            raise Exception("Порт отладки не найден! Убедитесь, что профиль запущен в Dolphin.")

        add_log("Успешное подключение к отладке!")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            try:
                add_log("Открываем OLX...")
                page.goto("https://www.olx.kz/account/", timeout=60000)
                time.sleep(3)
                
                add_log(f"Вводим номер: {pure_phone}")
                inp = page.locator("input[name='username']")
                inp.click()
                inp.press("Control+A")
                inp.press("Backspace")
                for char in pure_phone:
                    inp.type(char, delay=80)
                
                time.sleep(1.5)
                try: page.click("text=Забыли пароль?", timeout=4000)
                except: page.click("a:has-text('Забыли')", timeout=3000)
                
                time.sleep(3)
                sub = page.locator("button[type='submit'], [data-testid='submit-auth-button']")
                if sub.is_visible(): sub.click()
                
                add_log("Ожидание СМС...")
                for _ in range(36):
                    if not bot_status["running"]: break
                    s_res = api_call(action="getStatus", id=aid)
                    if s_res and s_res.startswith("STATUS_OK"):
                        code = s_res.split(":", 1)[1]
                        break
                    time.sleep(5)

                if code:
                    add_log(f"★ КОД ПОЙМАН: {code}")
                    page.fill("input[name='code'], input[data-testid='code-input']", code)
                    time.sleep(2)
                    page.fill("input[name='password'], input[type='password']", NEW_PASSWORD)
                    page.press("input[name='password'], input[type='password']", "Enter")
                    time.sleep(4)
                    bot_status["success"] += 1
                    add_log(f"✔ Аккаунт +{phone} восстановлен!")
                    save_to_log(phone, NEW_PASSWORD)
                else:
                    add_log("Время ожидания СМС истекло.")
            except Exception as e:
                add_log(f"✘ Ошибка в браузере: {e}")
        
        if not code:
            bot_status["failed"] += 1
            api_call(action="setStatus", id=aid, status=6)
            add_log("Номер отменен, баланс возвращен.")
    except Exception as en:
        add_log(f"✘ Ошибка воркера: {en}")
        if aid:
            try: api_call(action="setStatus", id=aid, status=6)
            except: pass

    bot_status["running"] = False
    bot_status["last_action"] = "Готово"
    add_log("Сессия завершена.")

@app.route("/")
def index(): return render_template("index.html", balance=get_balance(), accounts=[])

@app.route("/api/balance")
def api_balance(): return jsonify({"balance": get_balance()})

@app.route("/api/bot/status")
def api_bot_status(): return jsonify(bot_status)

@app.route("/api/bot/start", methods=["POST"])
def api_bot_start():
    global bot_thread, bot_status
    if bot_status["running"]: return jsonify({"success": False})
    data = request.get_json(silent=True) or {}
    srv = str(data.get("service", "sn"))
    cnt = str(data.get("country", "2"))
    bot_thread = threading.Thread(target=worker_loop, args=(srv, cnt), daemon=True)
    bot_thread.start()
    return jsonify({"success": True})

@app.route("/api/bot/stop", methods=["POST"])
def api_bot_stop():
    global bot_status
    bot_status["running"] = False
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050)