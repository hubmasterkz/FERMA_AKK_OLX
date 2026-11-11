import os
import time
import json
import logging
from playwright.sync_api import sync_playwright
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BotWorker")

GRIZZLY_API_KEY = os.getenv("GRIZZLY_API_KEY", "")
SERVICE_CODE = "sn"  # OLX
COUNTRY_ID = "2"     # Казахстан

def get_number():
    url = f"https://api.grizzlysms.com/st/api/v1/getState/{GRIZZLY_API_KEY}/getNumber/{SERVICE_CODE}/{COUNTRY_ID}"
    try:
        resp = requests.get(url).json()
        if resp.get("status") == "success":
            return resp.get("id"), resp.get("phone")
        logger.error(f"Ошибка получения номера: {resp}")
    except Exception as e:
        logger.error(f"Исключение при запросе номера: {e}")
    return None, None

def get_sms(activation_id):
    url = f"https://api.grizzlysms.com/st/api/v1/getState/{GRIZZLY_API_KEY}/getStatus/{activation_id}"
    try:
        resp = requests.get(url).json()
        if resp.get("status") == "STATUS_OK":
            return resp.get("code")
    except Exception as e:
        logger.error(f"Ошибка проверки SMS: {e}")
    return None

def run_automation(headless=True):
    if not GRIZZLY_API_KEY:
        logger.error("GRIZZLY_API_KEY не задан в переменных окружения!")
        return

    logger.info("Запрос номера у GrizzlySMS...")
    act_id, phone = get_number()
    if not act_id or not phone:
        logger.error("Не удалось получить номер.")
        return

    logger.info(f"Получен номер: {phone} (ID: {act_id})")

    with sync_playwright() as p:
        # Используем Dolphin Anty через CDP если настроено, либо обычный Chromium
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        try:
            logger.info("Открытие страницы авторизации OLX...")
            page.goto("https://www.olx.kz/account/", timeout=60000)
            
            # Пример ввода номера (селекторы могут потребовать небольшой адаптации под актуальную верстку OLX)
            logger.info("Ввод номера телефона...")
            phone_input = page.locator("input[name='phone'], input[data-testid='phone-input']").first
            phone_input.fill(phone)
            
            # Ожидание и получение SMS
            logger.info("Ожидание SMS-кода...")
            code = None
            for _ in range(30): # ждем до 2.5 минут
                code = get_sms(act_id)
                if code:
                    break
                time.sleep(5)

            if code:
                logger.info(f"Получен код подтверждения: {code}")
                code_input = page.locator("input[name='code'], input[data-testid='code-input']").first
                code_input.fill(code)
                
                # Сохранение успешного аккаунта
                os.makedirs("data", exist_ok=True)
                with open("data/success_accounts.json", "a", encoding="utf-8") as f:
                    json.dump({"phone": phone, "code": code, "time": time.time()}, f, ensure_ascii=False)
                    f.write("\n")
                logger.info("Аккаунт успешно обработан и сохранен!")
            else:
                logger.warning("Время ожидания SMS истекло.")

        except Exception as e:
            logger.error(f"Ошибка в процессе выполнения Playwright: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_automation(headless=False)
