import asyncio
import asyncpg

async def reset_db():
    conn = await asyncpg.connect('postgresql://postgres:anandhu3527@localhost:5432/postgres')
    try:
        await conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('cryvex_cloud', 'cryvex_cloud_test');")
        await conn.execute('DROP DATABASE IF EXISTS cryvex_cloud')
        await conn.execute('DROP DATABASE IF EXISTS cryvex_cloud_test')
        await conn.execute('CREATE DATABASE cryvex_cloud')
        await conn.execute('CREATE DATABASE cryvex_cloud_test')
        print("Databases recreated successfully")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

asyncio.run(reset_db())
