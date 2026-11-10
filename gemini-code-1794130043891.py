import time
import json
import requests
from playwright.sync_api import sync_playwright

# --- НАСТРОЙКИ ---
GRIZZLY_API_KEY = "26306aa4c4c98f502543f6a36bb39308"
GRIZZLY_BASE_URL = "https://api.grizzlysms.com/stubs/handler_api.php"
SERVICE = "opt"       # Код OLX в Grizzly
COUNTRY = "2"         # Казахстан
NEW_PASSWORD = "Mega_Park9"
LOG_FILE = "success_accounts.json"

# Ссылка для смены IP от Proxy-Seller (вставьте вашу или оставьте пустой, если IP меняется автоматически)
PROXY_CHANGE_URL = "" 

# Данные вашего прокси для подключения в браузер (формат: http://user:pass@ip:port)
PROXY_SERVER = "" 


def grizzly_call(**params):
    try:
        resp = requests.get(GRIZZLY_BASE_URL, params={"api_key": GRIZZLY_API_KEY, **params}, timeout=30)
        return resp.text.strip()
    except:
        return None


def change_ip_proxy():
    if not PROXY_CHANGE_URL:
        print("ℹ️ Ссылка смены IP не задана, пропускаем шаг API-смены.")
        return
    
    print("🔄 Запрос на смену IP через Proxy-Seller...")
    try:
        resp = requests.get(PROXY_CHANGE_URL, timeout=15)
        if resp.status_code == 200:
            print("✅ IP-адрес успешно изменен на стороне прокси!")
            time.sleep(7)  # Паужа на поднятие нового IP
        else:
            print(f"⚠️ Ошибка смены IP: статус {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Не удалось отправить запрос смены IP: {e}")


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
    print(f"💾 Аккаунт сохранен в лог: +{phone} / {password} (IP: {proxy_ip})")


def run_worker():
    attempt = 1
    while True:
        print(f"\n================ Попытка восстановления №{attempt} ================")
        
        # 1. Меняем IP перед новой сессией
        change_ip_proxy()
        
        # 2. Покупаем номер через Grizzly
        res = grizzly_call(action="getNumber", service=SERVICE, country=COUNTRY)
        if not res or not res.startswith("ACCESS_NUMBER"):
            print(f"❌ Ошибка покупки номера: {res}. Повтор через 10 сек...")
            time.sleep(10)
            continue
            
        _, activation_id, phone = res.split(":", 2)
        print(f"📲 Куплен номер: +{phone} (ID: {activation_id})")
        
        # 3. Запускаем браузер с подключением прокси
        with sync_playwright() as p:
            browser_args = ["--disable-blink-features=AutomationControlled"]
            
            # Настройка прокси для браузера, если он задан
            browser_config = {"headless": False, "args": browser_args}
            if PROXY_SERVER:
                browser_config["proxy"] = {"server": PROXY_SERVER}
                
            browser = p.chromium.launch(**browser_config)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            try:
                # Шаг 4. Открываем форму восстановления OLX
                print("🌐 Открываем страницу восстановления OLX...")
                page.goto("https://www.olx.kz/forgot-password/", timeout=60000)
                time.sleep(3)
                
                # Проверка на срабатывание Cloudflare / антифрода
                if page.locator("text=подозрительную активность").is_visible():
                    print("🚫 Замечена блокировка антифрода на этом IP. Сбрасываем номер...")
                    grizzly_call(action="setStatus", id=activation_id, status=8) # Возврат средств
                    browser.close()
                    attempt += 1
                    time.sleep(5)
                    continue
                
                # Шаг 5. Ввод номера телефона
                print(f"✍️ Вводим номер: {phone}")
                page.locator("input[type='tel'], input[name='username']").fill(phone)
                page.locator("button:has-text('Отправить код')").click()
                time.sleep(2)
                
                # Шаг 6. Ожидание SMS-кода
                print("⏳ Ожидание SMS-кода от Grizzly...")
                code = None
                for _ in range(30):  # Ждем до 2.5 минут
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
                
                print(f"✅ Получен код из SMS: {code}")
                
                # Шаг 7. Ввод кода и установка пароля Mega_Park9
                print("🔑 Вводим код и задаем новый пароль (Mega_Park9)...")
                page.locator("input[name='code'], input[type='text']").first.fill(code)
                page.locator("input[type='password']").fill(NEW_PASSWORD)
                page.locator("button:has-text('Сохранить'), button:has-text('Подтвердить'), button[type='submit']").click()
                time.sleep(5)
                
                # Шаг 8. Проверка авторизации и сохранение
                print("🔍 Проверяем успешность входа...")
                page.goto("https://www.olx.kz/myaccount/", timeout=30000)
                time.sleep(3)
                
                if "myaccount" in page.url:
                    print("🎉 УСПЕХ! Аккаунт восстановлен, пароль обновлен, выполнен вход!")
                    save_to_log(phone, NEW_PASSWORD, PROXY_SERVER if PROXY_SERVER else "Direct_IP")
                    grizzly_call(action="setStatus", id=activation_id, status=6) # Завершить активацию
                    browser.close()
                    break
                else:
                    print("⚠️ Не удалось подтвердить авторизацию, сбрасываем номер.")
                    grizzly_call(action="setStatus", id=activation_id, status=8)
                    browser.close()
                
            except Exception as e:
                print(f"⚠️ Ошибка в процессе работы браузера: {e}")
                grizzly_call(action="setStatus", id=activation_id, status=8)
                browser.close()
                
        attempt += 1
        time.sleep(5)

if __name__ == "__main__":
    print("🤖 Автоматический воркер восстановления OLX запущен...")
    run_worker()