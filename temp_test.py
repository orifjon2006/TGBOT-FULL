import asyncio
from typing import List

from database import init_db, session_scope, OrderRepository
from services import build_all_orders_excel, build_stats_excel
from datetime import datetime

async def main():
    await init_db()
    async with session_scope() as s:
        repo = OrderRepository(s)
        orders = await repo.get_all_orders()
        try:
            path1 = build_all_orders_excel(orders)
            print("All orders generated:", path1)
        except Exception as e:
            print("Error building all orders Excel:", e)

        try:
            stats = await repo.get_stats(datetime(2020, 1, 1), datetime.utcnow())
            path2 = build_stats_excel(stats, "All Time")
            print("Stats generated:", path2)
        except Exception as e:
            print("Error building stats Excel:", e)

if __name__ == "__main__":
    asyncio.run(main())
