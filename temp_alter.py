import sqlite3
try:
    c = sqlite3.connect('bot.db')
    c.execute('ALTER TABLE orders ADD COLUMN access_code VARCHAR(5)')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_access_code ON orders (access_code)')
    c.execute('ALTER TABLE orders ADD COLUMN client_telegram_id INTEGER')
    c.commit()
    print("Database altered successfully.")
except Exception as e:
    print("Error:", e)
