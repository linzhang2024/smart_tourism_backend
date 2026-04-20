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


def test_create_scenic_spot():
    print("测试 1: 创建景点...")
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "测试景点",
            "description": "用于测试流量监控功能的景点",
            "location": "测试地址",
            "rating": 4.5,
            "price": 100.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    data = response.json()
    print(f"  [OK] 景点创建成功，ID: {data['id']}")
    return data["id"]


def test_create_traffic_records(spot_id):
    print("\n测试 2: 录入流量数据...")
    
    traffic_data = [
        {"scenic_spot_id": spot_id, "entry_count": 150},
        {"scenic_spot_id": spot_id, "entry_count": 200},
        {"scenic_spot_id": spot_id, "entry_count": 180},
        {"scenic_spot_id": spot_id, "entry_count": 220},
        {"scenic_spot_id": spot_id, "entry_count": 170},
        {"scenic_spot_id": spot_id, "entry_count": 250},
    ]
    
    for i, data in enumerate(traffic_data, 1):
        response = client.post("/traffic/record", json=data)
        assert response.status_code == 201, f"录入流量数据失败: {response.json()}"
        result = response.json()
        print(f"  [OK] 记录 {i}: 入园人数 {result['entry_count']}, 记录时间 {result['record_time']}")
    
    print("  [OK] 所有流量数据录入成功")


def test_get_traffic_analytics(spot_id):
    print("\n测试 3: 获取流量分析数据...")
    
    response = client.get(f"/traffic/analytics/{spot_id}")
    assert response.status_code == 200, f"获取流量分析数据失败: {response.json()}"
    data = response.json()
    
    print(f"  景点ID: {data['scenic_spot_id']}")
    print(f"  景点名称: {data['scenic_spot_name']}")
    print(f"  平均入园人数: {data['average_entry_count']}")
    print(f"  最近记录数量: {len(data['recent_records'])}")
    
    print("\n  最近 5 条记录:")
    for i, record in enumerate(data['recent_records'], 1):
        print(f"    {i}. 入园人数: {record['entry_count']}, 记录时间: {record['record_time']}")
    
    assert len(data['recent_records']) == 5, "应该返回最近 5 条记录"
    
    expected_average = (250 + 170 + 220 + 180 + 200) / 5
    assert data['average_entry_count'] == expected_average, f"平均人数计算不正确，期望 {expected_average}，实际 {data['average_entry_count']}"
    
    print("\n  [OK] 流量分析测试通过")


def test_traffic_analytics_with_no_records():
    print("\n测试 4: 测试无流量记录时的分析...")
    
    response = client.post(
        "/scenic-spots/",
        json={
            "name": "空景点",
            "description": "没有流量记录的景点",
            "location": "测试地址",
            "rating": 4.0,
            "price": 50.0
        },
    )
    assert response.status_code == 201, f"创建景点失败: {response.json()}"
    empty_spot_id = response.json()["id"]
    
    response = client.get(f"/traffic/analytics/{empty_spot_id}")
    assert response.status_code == 200, f"获取流量分析数据失败: {response.json()}"
    data = response.json()
    
    print(f"  景点ID: {data['scenic_spot_id']}")
    print(f"  景点名称: {data['scenic_spot_name']}")
    print(f"  平均入园人数: {data['average_entry_count']}")
    print(f"  最近记录数量: {len(data['recent_records'])}")
    
    assert len(data['recent_records']) == 0, "没有记录时应该返回空列表"
    assert data['average_entry_count'] == 0.0, "没有记录时平均人数应该为 0"
    
    print("  [OK] 无流量记录分析测试通过")


def test_traffic_record_with_invalid_spot():
    print("\n测试 5: 测试使用不存在的景点ID录入流量...")
    
    response = client.post(
        "/traffic/record",
        json={
            "scenic_spot_id": 999999,
            "entry_count": 100
        },
    )
    
    print(f"  响应状态码: {response.status_code}")
    print(f"  响应内容: {response.json()}")
    
    assert response.status_code == 404, "使用不存在的景点ID应该返回 404 错误"
    assert "景点不存在" in response.json()["detail"], "错误信息应该包含 '景点不存在'"
    
    print("  [OK] 无效景点ID测试通过")


def test_traffic_analytics_with_invalid_spot():
    print("\n测试 6: 测试使用不存在的景点ID获取分析数据...")
    
    response = client.get("/traffic/analytics/999999")
    
    print(f"  响应状态码: {response.status_code}")
    print(f"  响应内容: {response.json()}")
    
    assert response.status_code == 404, "使用不存在的景点ID应该返回 404 错误"
    assert "景点不存在" in response.json()["detail"], "错误信息应该包含 '景点不存在'"
    
    print("  [OK] 无效景点ID分析测试通过")


def run_all_tests():
    print("=" * 60)
    print("开始执行流量监控功能测试")
    print("=" * 60)
    
    try:
        spot_id = test_create_scenic_spot()
        test_create_traffic_records(spot_id)
        test_get_traffic_analytics(spot_id)
        test_traffic_analytics_with_no_records()
        test_traffic_record_with_invalid_spot()
        test_traffic_analytics_with_invalid_spot()
        
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
