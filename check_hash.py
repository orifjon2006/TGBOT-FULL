import json
import hashlib
import os

def calculate_key_hash():
    file_path = "credentials.json"
    if not os.path.exists(file_path):
        print(f"❌ '{file_path}' topilmadi.")
        return

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        
        key = data.get("private_key", "")
        # Hashni hisoblash (SHA-256)
        h = hashlib.sha256(key.encode()).hexdigest()
        print(f"\n🔑 Sizning maxfiy kalit hash kodingiz:\n👉 {h}\n")
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")

if __name__ == "__main__":
    calculate_key_hash()
