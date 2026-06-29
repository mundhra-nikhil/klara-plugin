import asyncio
import asyncpg
import sys

async def main():
    try:
        conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/postgres')
        print("Success")
        await conn.execute("CREATE USER grss_user WITH PASSWORD 'changeme';")
        await conn.execute("CREATE DATABASE grss_db OWNER grss_user;")
        await conn.close()
    except Exception as e:
        print(f"Failed: {e}")
        try:
            conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/grss_db')
            await conn.execute("CREATE USER grss_user WITH PASSWORD 'changeme';")
            await conn.close()
            print("Already existed, created user")
        except Exception as e2:
            print(f"Failed again: {e2}")

if __name__ == '__main__':
    asyncio.run(main())
