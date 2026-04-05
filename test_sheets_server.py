import os
import json
import gspread
import logging
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone
import requests

# ═══════════════════════════════════════════════════════════════════════════
#  DIAGNOSTIKA — Server vaqti va Google API ulanishini tekshirish
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("Diagnostic")

CREDENTIALS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def check_server_time():
    logger.info("🕙 1. Server vaqtini tekshirmoqdamiz...")
    server_now = datetime.now(timezone.utc)
    
    try:
        # Haqiqiy vaqtni internetdan olamiz (WorldTimeAPI)
        response = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=5)
        if response.status_code == 200:
            real_now_str = response.json()['datetime']
            real_now = datetime.fromisoformat(real_now_str.replace('Z', '+00:00'))
            
            diff = abs((server_now - real_now).total_seconds())
            logger.info(f"   - Server vaqti (UTC): {server_now}")
            logger.info(f"   - Haqiqiy vaqt (UTC): {real_now}")
            
            if diff > 300: # 5 minutdan ko'p bo'lsa
                logger.error(f"❌ XATO: Serveringiz vaqti {int(diff)} soniyaga farq qilmoqda!")
                logger.error("👉 Google API vaqt noto'g'ri bo'lsa JWT tokenlarni qabul qilmaydi.")
                logger.error("🛑 YECHIM: Serverda vaqtni sinxronizatsiya qiling (ntpdate yoki chronyd).")
            else:
                logger.info(f"✅ Vaqt to'g'ri (farq: {int(diff)}s).")
        else:
            logger.warning("⚠️ Internetdan vaqtni olib bo'lmadi, date buyrug'ini tekshiring.")
    except Exception as e:
        logger.warning(f"⚠️ Vaqt tekshirishda muammo: {e}")

def check_credentials():
    logger.info(f"📂 2. '{CREDENTIALS_FILE}' faylini tekshirmoqdamiz...")
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error(f"❌ Fayl topilmadi: {CREDENTIALS_FILE}")
        return
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_data = json.load(f)
            logger.info(f"✅ Fayl o'qildi. Email: {creds_data.get('client_email')}")
            
        logger.info("🔑 3. Google API avtorizatsiyasini boshlaymiz...")
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)
        
        # Test: ochiq bepul jadval yoki shunchaki listni olish
        client.list_spreadsheet_files()
        logger.info("🚀 MUVAFFARIYAT: Google API ulanishi to'g'ri ishlamoqda!")
        
    except Exception as e:
        logger.error(f"❌ Avtorizatsiyada xatolik: {e}")
        if "Invalid JWT Signature" in str(e):
            logger.error("👉 Bu aniq VAQT MUAMMOSI (System Clock Desync).")

if __name__ == "__main__":
    print("\n--- GOOGLE SHEETS SERVER DIAGNOSTICS ---\n")
    check_server_time()
    check_credentials()
    print("\n----------------------------------------\n")
