import time
import json
import requests
from playwright.sync_api import sync_playwright

GRIZZLY_API_KEY = "26306aa4c4c98f502543f6a36bb39308"
GRIZZLY_BASE_URL = "https://api.grizzlysms.com/stubs/handler_api.php"
SERVICE = "sn"        # OLX
COUNTRY = "2"         # Строго Казахстан
NEW_PASSWORD = "Mega_Park9"
LOG_FILE = "success_accounts.json"

PROXY_CHANGE_URL = "" 
PROXY_SERVER = ""     

def grizzly_call(**params):
    try:
        resp = requests.get(GRIZZLY_BASE_URL, params={"api_key": GRIZZLY_API_KEY, **params}, timeout=30)
        return resp.text.strip()
    except Exception as e:
        print(f"⚠️ Ошибка сети при запросе к Grizzly: {e}")
        return None

def change_ip_proxy():
    if not PROXY_CHANGE_URL:
        return
    try:
        requests.get(PROXY_CHANGE_URL, timeout=15)
        time.sleep(7)
    except:
        pass

def save_to_log(phone, password, proxy_ip):
    record = {
        "phone": phone,
        "password": password,
        "ip": proxy_ip,
        "status": "Success_Restored",
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    data = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        pass
    data.append(record)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"💾 Успешно сохранено в лог: +{phone} / {password}")

def run_worker():
    attempt = 1
    while True:
        print(f"\n================ Попытка восстановления №{attempt} ================")
        change_ip_proxy()
        
        # Запрашиваем номер именно для Казахстана (country=2)
        res = grizzly_call(action="getNumber", service=SERVICE, country=COUNTRY)
        print(f"💬 Ответ от Grizzly: {res}")
        
        if not res or not res.startswith("ACCESS_NUMBER"):
            print(f"❌ Нет свободных номеров по Казахстану. Повтор через 10 сек...")
            time.sleep(10)
            attempt += 1
            continue
            
        _, activation_id, phone = res.split(":", 2)
        print(f"📲 Куплен казахстанский номер: +{phone} (ID: {activation_id})")
        
        with sync_playwright() as p:
            browser_args = ["--disable-blink-features=AutomationControlled"]
            browser_config = {"headless": False, "args": browser_args}
            if PROXY_SERVER:
                browser_config["proxy"] = {"server": PROXY_SERVER}
                
            browser = p.chromium.launch(**browser_config)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            try:
                print("🌐 Открываем OLX...")
                page.goto("https://www.olx.kz/", timeout=60000)
                time.sleep(4)
                
                if page.locator("text=подозрительную активность").is_visible():
                    print("🚫 Блокировка антифрода. Сбрасываем номер в Grizzly...")
                    grizzly_call(action="setStatus", id=activation_id, status=8)
                    browser.close()
                    attempt += 1
                    time.sleep(5)
                    continue
                
                try:
                    page.locator("text=Ваш профиль, text=Вход, [data-cy='profile-link']").first.click(timeout=5000)
                    time.sleep(2)
                except:
                    pass
                
                print(f"✍️ Вводим номер: {phone}")
                page.locator("input[type='tel'], input[name='username']").fill(phone)
                page.locator("button:has-text('Отправить код'), button:has-text('Далее')").click()
                time.sleep(2)
                
                print("⏳ Ожидание SMS-кода...")
                code = None
                for _ in range(30):
                    time.sleep(5)
                    status_res = grizzly_call(action="getStatus", id=activation_id)
                    if status_res and status_res.startswith("STATUS_OK"):
                        code = status_res.split(":", 1)[1]
                        break
                    elif status_res == "STATUS_CANCEL":
                        break
                
                if not code:
                    print("⌛ Время ожидания SMS истекло. Отменяем номер...")
                    grizzly_call(action="setStatus", id=activation_id, status=8)
                    browser.close()
                    attempt += 1
                    continue
                
                print(f"✅ Получен код: {code}")
                
                print("🔑 Вводим код и устанавливаем пароль (Mega_Park9)...")
                page.locator("input[name='code'], input[type='text']").first.fill(code)
                page.locator("input[type='password']").fill(NEW_PASSWORD)
                page.locator("button:has-text('Сохранить'), button:has-text('Подтвердить'), button[type='submit']").click()
                time.sleep(5)
                
                print("🔍 Проверяем вход...")
                page.goto("https://www.olx.kz/myaccount/", timeout=30000)
                time.sleep(3)
                
                if "myaccount" in page.url:
                    print("🎉 УСПЕХ! Аккаунт восстановлен и пароль изменен!")
                    save_to_log(phone, NEW_PASSWORD, PROXY_SERVER if PROXY_SERVER else "Direct_IP")
                    grizzly_call(action="setStatus", id=activation_id, status=6)
                    browser.close()
                    break
                else:
                    print("⚠️ Авторизация не подтверждена, сбрасываем номер.")
                    grizzly_call(action="setStatus", id=activation_id, status=8)
                    browser.close()
                
            except Exception as e:
                print(f"⚠️ Ошибка: {e}")
                grizzly_call(action="setStatus", id=activation_id, status=8)
                browser.close()
                
        attempt += 1
        time.sleep(5)

if __name__ == "__main__":
    print("🤖 Автоматический воркер запущен...")
    run_worker()
