import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from main import app, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_create_scenic_spot_with_inventory():
    print("测试 1: 创建景点并设置库存...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "测试景点",
            "description": "用于测试库存功能的景点",
            "location": "测试地址",
            "rating": 4.5,
            "total_inventory": 100,
            "remained_inventory": 100
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    data = response.json()
    assert data["total_inventory"] == 100, "总库存设置不正确"
    assert data["remained_inventory"] == 100, "剩余库存设置不正确"
    print(f"  ✓ 景点创建成功，总库存: {data['total_inventory']}, 剩余库存: {data['remained_inventory']}")
    return data["id"]


def test_create_tourist():
    print("\n测试 2: 创建游客...")
    response = client.post(
        "/tourists/",
        json={
            "name": "测试游客",
            "id_card": "110101199001011234",
            "phone": "13800138000",
            "email": "test@example.com"
        },
    )
    assert response.status_code == 201, f"创建游客失败: {response.json()}"
    data = response.json()
    print(f"  ✓ 游客创建成功，ID: {data['id']}")
    return data["id"]


def test_inventory_deduction(scenic_spot_id, tourist_id):
    print("\n测试 3: 测试门票购买时的库存扣减...")
    
    response = client.get(f"/scenic-spots/{scenic_spot_id}")
    initial_inventory = response.json()["remained_inventory"]
    print(f"  初始剩余库存: {initial_inventory}")
    
    print("  购买门票 1...")
    response = client.post(
        "/tickets/",
        json={
            "scenic_spot_id": scenic_spot_id,
            "tourist_id": tourist_id,
            "ticket_type": "成人票",
            "price": 100.0
        },
    )
    assert response.status_code == 201, f"购买门票失败: {response.json()}"
    
    response = client.get(f"/scenic-spots/{scenic_spot_id}")
    inventory_after_first = response.json()["remained_inventory"]
    print(f"  购买门票 1 后剩余库存: {inventory_after_first}")
    assert inventory_after_first == initial_inventory - 1, "库存扣减不正确"
    
    print("  购买门票 2...")
    response = client.post(
        "/tickets/",
        json={
            "scenic_spot_id": scenic_spot_id,
            "tourist_id": tourist_id,
            "ticket_type": "成人票",
            "price": 100.0
        },
    )
    assert response.status_code == 201, f"购买门票失败: {response.json()}"
    
    response = client.get(f"/scenic-spots/{scenic_spot_id}")
    inventory_after_second = response.json()["remained_inventory"]
    print(f"  购买门票 2 后剩余库存: {inventory_after_second}")
    assert inventory_after_second == inventory_after_first - 1, "库存扣减不正确"
    
    print("  ✓ 库存扣减测试通过")


def test_low_inventory_alert():
    print("\n测试 4: 测试低库存预警...")
    
    print("  创建低库存景点 (总库存 10, 剩余库存 0)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "低库存景点",
            "description": "用于测试低库存预警",
            "total_inventory": 10,
            "remained_inventory": 0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    low_spot_id = response.json()["id"]
    
    print("  获取景点库存状态...")
    response = client.get(f"/scenic-spots/{low_spot_id}/inventory-status")
    assert response.status_code == 200, f"获取库存状态失败: {response.json()}"
    data = response.json()
    
    print(f"  总库存: {data['total_inventory']}")
    print(f"  剩余库存: {data['remained_inventory']}")
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["is_low_inventory"] == True, "低库存预警标志应该为 True"
    assert data["inventory_percentage"] == 0.0, "库存百分比应该为 0%"
    
    print("  创建正常库存景点 (总库存 100, 剩余库存 50)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "正常库存景点",
            "description": "用于测试正常库存",
            "total_inventory": 100,
            "remained_inventory": 50
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    normal_spot_id = response.json()["id"]
    
    print("  获取景点库存状态...")
    response = client.get(f"/scenic-spots/{normal_spot_id}/inventory-status")
    assert response.status_code == 200, f"获取库存状态失败: {response.json()}"
    data = response.json()
    
    print(f"  总库存: {data['total_inventory']}")
    print(f"  剩余库存: {data['remained_inventory']}")
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["is_low_inventory"] == False, "正常库存预警标志应该为 False"
    assert data["inventory_percentage"] == 50.0, "库存百分比应该为 50%"
    
    print("  ✓ 低库存预警测试通过")


def test_get_all_low_inventory_spots():
    print("\n测试 5: 测试获取所有低库存景点...")
    
    response = client.get("/scenic-spots/inventory/low-alert")
    assert response.status_code == 200, f"获取低库存景点列表失败: {response.json()}"
    data = response.json()
    
    print(f"  低库存景点数量: {len(data)}")
    for spot in data:
        print(f"  - {spot['name']}: 总库存 {spot['total_inventory']}, 剩余库存 {spot['remained_inventory']}, 百分比 {spot['inventory_percentage']}%")
    
    assert len(data) >= 1, "应该至少有一个低库存景点"
    
    print("  ✓ 获取所有低库存景点测试通过")


def test_out_of_stock():
    print("\n测试 6: 测试库存不足时的错误处理...")
    
    print("  创建零库存景点...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "零库存景点",
            "description": "用于测试库存不足",
            "total_inventory": 0,
            "remained_inventory": 0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    out_of_stock_id = response.json()["id"]
    
    print("  尝试购买门票...")
    response = client.post(
        "/tickets/",
        json={
            "scenic_spot_id": out_of_stock_id,
            "tourist_id": 1,
            "ticket_type": "成人票",
            "price": 100.0
        },
    )
    
    print(f"  响应状态码: {response.status_code}")
    print(f"  响应内容: {response.json()}")
    
    assert response.status_code == 400, "库存不足时应该返回 400 错误"
    assert "库存不足" in response.json()["detail"], "错误信息应该包含 '库存不足'"
    
    print("  ✓ 库存不足错误处理测试通过")


def test_10_percent_threshold():
    print("\n测试 7: 测试 10% 库存阈值...")
    
    print("  创建总库存 100, 剩余库存 9 的景点 (9% < 10%, 应该触发预警)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "临界库存景点",
            "description": "用于测试 10% 阈值",
            "total_inventory": 100,
            "remained_inventory": 9
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    spot_id = response.json()["id"]
    
    response = client.get(f"/scenic-spots/{spot_id}/inventory-status")
    data = response.json()
    
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["is_low_inventory"] == True, "9% 库存应该触发预警"
    assert data["inventory_percentage"] == 9.0, "库存百分比应该为 9%"
    
    print("  创建总库存 100, 剩余库存 10 的景点 (10% 不触发预警)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "刚好 10% 库存景点",
            "description": "用于测试 10% 阈值边界",
            "total_inventory": 100,
            "remained_inventory": 10
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    spot_id = response.json()["id"]
    
    response = client.get(f"/scenic-spots/{spot_id}/inventory-status")
    data = response.json()
    
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["is_low_inventory"] == False, "10% 库存不应该触发预警"
    assert data["inventory_percentage"] == 10.0, "库存百分比应该为 10%"
    
    print("  ✓ 10% 库存阈值测试通过")


def run_all_tests():
    print("=" * 60)
    print("开始执行库存管理功能测试")
    print("=" * 60)
    
    try:
        scenic_spot_id = test_create_scenic_spot_with_inventory()
        tourist_id = test_create_tourist()
        test_inventory_deduction(scenic_spot_id, tourist_id)
        test_low_inventory_alert()
        test_get_all_low_inventory_spots()
        test_out_of_stock()
        test_10_percent_threshold()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
