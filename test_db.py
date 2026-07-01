import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect('postgresql://postgres@localhost/facebook_crm_db')
        print("Success")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
