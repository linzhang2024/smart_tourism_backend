"""
直接测试脚本 - 直接测试路由
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

print("=" * 60)
print("直接测试路由")
print("=" * 60)

print("\n[1] 测试根路径 / ...")
response = client.get("/")
print(f"    状态码: {response.status_code}")

print("\n[2] 测试路由列表:")
for route in main.app.routes:
    if hasattr(route, 'path'):
        print(f"    {route.path}")

print("\n[3] 测试 /auth/login (POST) ...")
response = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
print(f"    状态码: {response.status_code}")
if response.status_code != 200:
    print(f"    响应: {response.text}")
else:
    print(f"    响应: {response.json()}")

print("\n[4] 测试 /auth/register (POST) ...")
response = client.post("/auth/register", json={"username": "testuser", "password": "test123", "email": "test@example.com"})
print(f"    状态码: {response.status_code}")
if response.status_code != 200:
    print(f"    响应: {response.text}")
else:
    print(f"    响应: {response.json()}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
