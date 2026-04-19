import httpx

base_url = "http://127.0.0.1:8000"

test_spots = [
    {"name": "故宫博物院", "description": "中国明清两代的皇家宫殿", "price": 60.0, "total_inventory": 100, "remained_inventory": 8},
    {"name": "八达岭长城", "description": "中国古代的军事防御工程", "price": 40.0, "total_inventory": 200, "remained_inventory": 15},
    {"name": "颐和园", "description": "中国清朝时期皇家园林", "price": 30.0, "total_inventory": 150, "remained_inventory": 5},
    {"name": "天坛公园", "description": "明清两代皇帝祭祀皇天", "price": 15.0, "total_inventory": 100, "remained_inventory": 50},
]

print("创建测试景点...")
for spot in test_spots:
    r = httpx.post(f"{base_url}/scenic-spots/", json=spot, timeout=5.0)
    if r.status_code == 201:
        print(f"  已创建: {spot['name']} (库存: {spot['remained_inventory']}/{spot['total_inventory']})")
    else:
        print(f"  创建失败: {spot['name']} - {r.text}")

print()
print("检查低库存景点...")
r = httpx.get(f"{base_url}/scenic-spots/low-alert", timeout=5.0)
if r.status_code == 200:
    data = r.json()
    print(f"找到 {len(data)} 个低库存景点:")
    for spot in data:
        print(f"  - {spot['name']}: {spot['remained_inventory']}/{spot['total_inventory']} ({spot['inventory_ratio']*100:.1f}%)")
else:
    print(f"错误: {r.status_code} - {r.text}")
