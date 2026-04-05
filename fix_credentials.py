import json
import os

def fix_credentials():
    file_path = "credentials.json"
    if not os.path.exists(file_path):
        print(f"❌ '{file_path}' topilmadi.")
        return

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        
        # Private key dagi ortiqcha \r yoki noto'g'ri belgilarni tozalaymiz
        if "private_key" in data:
            original_key = data["private_key"]
            # Tozalash: Faqat \n saqlanadi, boshqa g'alati belgilar o'chiriladi
            fixed_key = original_key.replace("\\n", "\n").replace("\r", "")
            # Qayta formatlash (JSON uchun yana \n ko'rinishiga qaytaramiz)
            data["private_key"] = fixed_key.strip()
            
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            print("✅ 'credentials.json' muvaffaqiyatli tozalandi va formatlandi.")
        else:
            print("❌ 'private_key' maydoni topilmadi.")
            
    except Exception as e:
        print(f"❌ Xatolik: {e}")

if __name__ == "__main__":
    fix_credentials()
