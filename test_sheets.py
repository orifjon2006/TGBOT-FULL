import asyncio
from google_sheets import append_order_to_sheet
from datetime import datetime

async def test():
    print("Testing Google Sheets API...")
    order_data = [
        "TEST-001",
        "Test Usta",
        "+998901234567",
        "Test Xizmat",
        "100,000",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]
    res = append_order_to_sheet(order_data)
    print("Result:", res)

if __name__ == "__main__":
    asyncio.run(test())
