import httpx
import asyncio

BASE_URL = "http://localhost:8000"

async def test_routes():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("测试根路径 / ...")
        try:
            response = await client.get(f"{BASE_URL}/")
            print(f"  状态码: {response.status_code}")
            print(f"  响应前 200 字符: {response.text[:200]}")
        except Exception as e:
            print(f"  错误: {e}")
        
        print("\n测试 /auth/login (POST) ...")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json={"username": "admin", "password": "admin123"}
            )
            print(f"  状态码: {response.status_code}")
            print(f"  响应: {response.text}")
        except Exception as e:
            print(f"  错误: {e}")
        
        print("\n测试 /auth/register (POST) ...")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/register",
                json={"username": "test123", "password": "test123", "email": "test123@test.com"}
            )
            print(f"  状态码: {response.status_code}")
            print(f"  响应: {response.text[:500]}")
        except Exception as e:
            print(f"  错误: {e}")
        
        print("\n测试不存在的路径 /nonexistent ...")
        try:
            response = await client.get(f"{BASE_URL}/nonexistent")
            print(f"  状态码: {response.status_code}")
            print(f"  响应: {response.text}")
        except Exception as e:
            print(f"  错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_routes())
