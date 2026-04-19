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
            "remained_inventory": 100,
            "alert_threshold": 10.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    data = response.json()
    assert data["total_inventory"] == 100, "总库存设置不正确"
    assert data["remained_inventory"] == 100, "剩余库存设置不正确"
    assert data["alert_threshold"] == 10.0, "预警阈值设置不正确"
    print(f"  ✓ 景点创建成功，总库存: {data['total_inventory']}, 剩余库存: {data['remained_inventory']}, 预警阈值: {data['alert_threshold']}%")
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
    
    print("  创建低库存景点 (总库存 10, 剩余库存 0, 预警阈值 10%)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "低库存景点",
            "description": "用于测试低库存预警",
            "total_inventory": 10,
            "remained_inventory": 0,
            "alert_threshold": 10.0
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
    print(f"  预警阈值: {data['alert_threshold']}%")
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["is_low_inventory"] == True, "低库存预警标志应该为 True"
    assert data["inventory_percentage"] == 0.0, "库存百分比应该为 0%"
    assert data["alert_threshold"] == 10.0, "预警阈值应该为 10%"
    
    print("  创建正常库存景点 (总库存 100, 剩余库存 50, 预警阈值 10%)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "正常库存景点",
            "description": "用于测试正常库存",
            "total_inventory": 100,
            "remained_inventory": 50,
            "alert_threshold": 10.0
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
    print(f"  预警阈值: {data['alert_threshold']}%")
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["is_low_inventory"] == False, "正常库存预警标志应该为 False"
    assert data["inventory_percentage"] == 50.0, "库存百分比应该为 50%"
    assert data["alert_threshold"] == 10.0, "预警阈值应该为 10%"
    
    print("  ✓ 低库存预警测试通过")


def test_get_all_low_inventory_spots():
    print("\n测试 5: 测试获取所有低库存景点...")
    
    response = client.get("/scenic-spots/inventory/low-alert")
    assert response.status_code == 200, f"获取低库存景点列表失败: {response.json()}"
    data = response.json()
    
    print(f"  低库存景点数量: {len(data)}")
    for spot in data:
        print(f"  - {spot['name']}: 总库存 {spot['total_inventory']}, 剩余库存 {spot['remained_inventory']}, 阈值 {spot['alert_threshold']}%, 百分比 {spot['inventory_percentage']}%")
    
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
            "remained_inventory": 0,
            "alert_threshold": 10.0
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


def test_different_alert_thresholds():
    print("\n测试 7: 测试不同景点设置不同预警阈值...")
    
    print("  场景 1: 景点 A - 预警阈值 30%")
    print("  创建景点 A (总库存 100, 剩余库存 25, 预警阈值 30%)...")
    print("  25% < 30% → 应该触发预警")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "高阈值景点 A",
            "description": "预警阈值 30%",
            "total_inventory": 100,
            "remained_inventory": 25,
            "alert_threshold": 30.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    spot_a_id = response.json()["id"]
    
    response = client.get(f"/scenic-spots/{spot_a_id}/inventory-status")
    data = response.json()
    
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  预警阈值: {data['alert_threshold']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["alert_threshold"] == 30.0, "预警阈值应该为 30%"
    assert data["inventory_percentage"] == 25.0, "库存百分比应该为 25%"
    assert data["is_low_inventory"] == True, "25% < 30% 应该触发预警"
    
    print("  ✓ 场景 1 通过")
    
    print("\n  场景 2: 景点 B - 预警阈值 20%")
    print("  创建景点 B (总库存 100, 剩余库存 25, 预警阈值 20%)...")
    print("  25% > 20% → 不触发预警")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "中阈值景点 B",
            "description": "预警阈值 20%",
            "total_inventory": 100,
            "remained_inventory": 25,
            "alert_threshold": 20.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    spot_b_id = response.json()["id"]
    
    response = client.get(f"/scenic-spots/{spot_b_id}/inventory-status")
    data = response.json()
    
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  预警阈值: {data['alert_threshold']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["alert_threshold"] == 20.0, "预警阈值应该为 20%"
    assert data["inventory_percentage"] == 25.0, "库存百分比应该为 25%"
    assert data["is_low_inventory"] == False, "25% > 20% 不应该触发预警"
    
    print("  ✓ 场景 2 通过")
    
    print("\n  场景 3: 景点 C - 预警阈值 50%")
    print("  创建景点 C (总库存 100, 剩余库存 45, 预警阈值 50%)...")
    print("  45% < 50% → 应该触发预警")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "超高阈值景点 C",
            "description": "预警阈值 50%",
            "total_inventory": 100,
            "remained_inventory": 45,
            "alert_threshold": 50.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    spot_c_id = response.json()["id"]
    
    response = client.get(f"/scenic-spots/{spot_c_id}/inventory-status")
    data = response.json()
    
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  预警阈值: {data['alert_threshold']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["alert_threshold"] == 50.0, "预警阈值应该为 50%"
    assert data["inventory_percentage"] == 45.0, "库存百分比应该为 45%"
    assert data["is_low_inventory"] == True, "45% < 50% 应该触发预警"
    
    print("  ✓ 场景 3 通过")
    
    print("\n  场景 4: 景点 D - 预警阈值 5%")
    print("  创建景点 D (总库存 100, 剩余库存 8, 预警阈值 5%)...")
    print("  8% > 5% → 不触发预警")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "低阈值景点 D",
            "description": "预警阈值 5%",
            "total_inventory": 100,
            "remained_inventory": 8,
            "alert_threshold": 5.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    spot_d_id = response.json()["id"]
    
    response = client.get(f"/scenic-spots/{spot_d_id}/inventory-status")
    data = response.json()
    
    print(f"  库存百分比: {data['inventory_percentage']}%")
    print(f"  预警阈值: {data['alert_threshold']}%")
    print(f"  是否低库存: {data['is_low_inventory']}")
    
    assert data["alert_threshold"] == 5.0, "预警阈值应该为 5%"
    assert data["inventory_percentage"] == 8.0, "库存百分比应该为 8%"
    assert data["is_low_inventory"] == False, "8% > 5% 不应该触发预警"
    
    print("  ✓ 场景 4 通过")
    
    print("\n  场景 5: 验证不同阈值景点在低库存列表中的表现")
    print("  获取所有低库存景点...")
    response = client.get("/scenic-spots/inventory/low-alert")
    data = response.json()
    
    print(f"  低库存景点数量: {len(data)}")
    
    spot_a_in_list = any(spot["name"] == "高阈值景点 A" for spot in data)
    spot_b_in_list = any(spot["name"] == "中阈值景点 B" for spot in data)
    spot_c_in_list = any(spot["name"] == "超高阈值景点 C" for spot in data)
    spot_d_in_list = any(spot["name"] == "低阈值景点 D" for spot in data)
    
    print(f"  高阈值景点 A (30%阈值, 25%库存) 是否在列表中: {spot_a_in_list}")
    print(f"  中阈值景点 B (20%阈值, 25%库存) 是否在列表中: {spot_b_in_list}")
    print(f"  超高阈值景点 C (50%阈值, 45%库存) 是否在列表中: {spot_c_in_list}")
    print(f"  低阈值景点 D (5%阈值, 8%库存) 是否在列表中: {spot_d_in_list}")
    
    assert spot_a_in_list == True, "高阈值景点 A 应该在低库存列表中"
    assert spot_b_in_list == False, "中阈值景点 B 不应该在低库存列表中"
    assert spot_c_in_list == True, "超高阈值景点 C 应该在低库存列表中"
    assert spot_d_in_list == False, "低阈值景点 D 不应该在低库存列表中"
    
    print("  ✓ 场景 5 通过")
    
    print("  ✓ 不同预警阈值测试通过")


def test_default_alert_threshold():
    print("\n测试 8: 测试默认预警阈值 (10%)...")
    
    print("  创建景点时不设置预警阈值 (应该使用默认值 10%)...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "默认阈值景点",
            "description": "使用默认预警阈值 10%",
            "total_inventory": 100,
            "remained_inventory": 8
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    data = response.json()
    
    print(f"  创建景点时返回的 alert_threshold: {data.get('alert_threshold')}")
    
    spot_id = data["id"]
    
    response = client.get(f"/scenic-spots/{spot_id}/inventory-status")
    inventory_data = response.json()
    
    print(f"  库存百分比: {inventory_data['inventory_percentage']}%")
    print(f"  预警阈值: {inventory_data['alert_threshold']}%")
    print(f"  是否低库存: {inventory_data['is_low_inventory']}")
    
    assert inventory_data["alert_threshold"] == 10.0, "默认预警阈值应该为 10%"
    assert inventory_data["inventory_percentage"] == 8.0, "库存百分比应该为 8%"
    assert inventory_data["is_low_inventory"] == True, "8% < 10% 应该触发预警"
    
    print("  ✓ 默认预警阈值测试通过")


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
        test_different_alert_thresholds()
        test_default_alert_threshold()
        
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
