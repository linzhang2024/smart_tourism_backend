import threading
import time
import requests
import json
import random
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "http://localhost:8000"
CONCURRENT_USERS = 50
TEST_TOURIST_ID = 1
TEST_SCENIC_SPOT_ID = 1
TICKETS_PER_REQUEST = 1

results: List[Dict[str, Any]] = []
results_lock = threading.Lock()

response_times: List[float] = []
response_times_lock = threading.Lock()


def create_test_data() -> bool:
    """创建测试数据（游客和景点）"""
    print("[准备] 创建测试数据...")
    
    tourist_payload = {
        "name": "压力测试游客",
        "email": f"stress_test_{int(time.time())}@example.com",
        "phone": "13800000001"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tourists/", json=tourist_payload)
        if response.status_code == 201:
            global TEST_TOURIST_ID
            TEST_TOURIST_ID = response.json()["id"]
            print(f"[准备] 创建游客成功: ID={TEST_TOURIST_ID}")
        elif response.status_code == 422:
            print(f"[准备] 游客创建失败（数据验证错误）: {response.text}")
            return False
        else:
            print(f"[准备] 游客创建失败，尝试使用现有游客...")
            tourists = requests.get(f"{BASE_URL}/tourists/").json()
            if tourists:
                TEST_TOURIST_ID = tourists[0]["id"]
                print(f"[准备] 使用现有游客: ID={TEST_TOURIST_ID}")
            else:
                print("[准备] 没有可用的游客数据")
                return False
    except Exception as e:
        print(f"[准备] 创建游客时出错: {e}")
        return False
    
    scenic_payload = {
        "name": "压力测试景点",
        "description": "用于压力测试的景点",
        "location": "测试地点",
        "price": 100.0,
        "total_inventory": 1000,
        "remained_inventory": 1000
    }
    
    try:
        response = requests.post(f"{BASE_URL}/scenic-spots/", json=scenic_payload)
        if response.status_code == 201:
            global TEST_SCENIC_SPOT_ID
            TEST_SCENIC_SPOT_ID = response.json()["id"]
            print(f"[准备] 创建景点成功: ID={TEST_SCENIC_SPOT_ID}, 初始库存=1000")
        elif response.status_code == 422:
            print(f"[准备] 景点创建失败（数据验证错误）: {response.text}")
            return False
        else:
            print(f"[准备] 景点创建失败，尝试使用现有景点...")
            spots = requests.get(f"{BASE_URL}/scenic-spots/").json()
            if spots:
                TEST_SCENIC_SPOT_ID = spots[0]["id"]
                print(f"[准备] 使用现有景点: ID={TEST_SCENIC_SPOT_ID}")
            else:
                print("[准备] 没有可用的景点数据")
                return False
    except Exception as e:
        print(f"[准备] 创建景点时出错: {e}")
        return False
    
    return True


def purchase_ticket_request(user_id: int) -> Dict[str, Any]:
    """单个用户的购票请求"""
    payload = {
        "tourist_id": TEST_TOURIST_ID,
        "scenic_spot_id": TEST_SCENIC_SPOT_ID,
        "quantity": TICKETS_PER_REQUEST
    }
    
    start_time = time.time()
    result = {
        "user_id": user_id,
        "success": False,
        "status_code": 0,
        "detail": "",
        "response_time": 0.0
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/tickets/purchase",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        elapsed = time.time() - start_time
        result["response_time"] = elapsed
        
        with response_times_lock:
            response_times.append(elapsed)
        
        result["status_code"] = response.status_code
        
        if response.status_code == 201:
            result["success"] = True
            result["detail"] = "购票成功"
            data = response.json()
            result["order_no"] = data.get("order_no", "")
            result["total_price"] = data.get("total_price", 0)
        else:
            result["success"] = False
            try:
                error_detail = response.json().get("detail", response.text)
                result["detail"] = error_detail
            except:
                result["detail"] = response.text
        
    except requests.exceptions.ConnectionError:
        result["status_code"] = -1
        result["detail"] = "连接失败 - 服务器未启动"
    except Exception as e:
        result["status_code"] = -2
        result["detail"] = f"请求异常: {str(e)}"
    
    with results_lock:
        results.append(result)
    
    return result


def run_stress_test():
    """运行压力测试"""
    print("\n" + "=" * 70)
    print("  智慧旅游系统 - 压力测试脚本")
    print("=" * 70)
    print(f"\n[测试配置]")
    print(f"  并发用户数: {CONCURRENT_USERS}")
    print(f"  目标接口: POST {BASE_URL}/tickets/purchase")
    print(f"  测试游客ID: {TEST_TOURIST_ID}")
    print(f"  测试景点ID: {TEST_SCENIC_SPOT_ID}")
    print(f"  每请求购票数: {TICKETS_PER_REQUEST}")
    print("-" * 70)
    
    print("\n[检查] 确认服务器是否启动...")
    try:
        health_response = requests.get(f"{BASE_URL}/system/health", timeout=5)
        if health_response.status_code == 200:
            print("[检查] 服务器运行正常")
        else:
            print(f"[检查] 服务器响应异常: {health_response.status_code}")
    except requests.exceptions.ConnectionError:
        print("\n[错误] 无法连接到服务器！")
        print("[提示] 请先运行以下命令启动服务器:")
        print("       cd d:\\workspace\\Trae\\smart_tourism_backend-TouristFlow\\smart_tourism_backend")
        print("       python main.py")
        return False
    except Exception as e:
        print(f"\n[错误] 检查服务器时出错: {e}")
        return False
    
    if not create_test_data():
        print("\n[错误] 测试数据准备失败，无法进行压力测试")
        return False
    
    print("\n[准备] 获取初始库存信息...")
    try:
        spot_response = requests.get(f"{BASE_URL}/scenic-spots/{TEST_SCENIC_SPOT_ID}")
        if spot_response.status_code == 200:
            spot_data = spot_response.json()
            initial_inventory = spot_data.get("remained_inventory", 0)
            total_inventory = spot_data.get("total_inventory", 0)
            print(f"[准备] 景点 '{spot_data['name']}' 库存信息:")
            print(f"         总库存: {total_inventory}, 剩余库存: {initial_inventory}")
        else:
            print("[准备] 无法获取景点信息")
            initial_inventory = 0
    except Exception as e:
        print(f"[准备] 获取景点信息失败: {e}")
        initial_inventory = 0
    
    print(f"\n[开始] 启动 {CONCURRENT_USERS} 个并发用户进行购票请求...")
    print("-" * 70)
    
    global results, response_times
    results = []
    response_times = []
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = {
            executor.submit(purchase_ticket_request, i + 1): i + 1 
            for i in range(CONCURRENT_USERS)
        }
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            status = "✓" if result["success"] else "✗"
            print(f"  [{completed:2d}/{CONCURRENT_USERS}] 用户 {result['user_id']:2d}: {status} "
                  f"状态码={result['status_code']}, 响应时间={result['response_time']:.3f}s")
    
    total_time = time.time() - start_time
    print("\n" + "-" * 70)
    print(f"[完成] 所有请求完成，总耗时: {total_time:.2f} 秒")
    print("=" * 70)
    
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count
    
    inventory_shortage = sum(1 for r in results if not r["success"] and "库存不足" in r["detail"])
    connection_errors = sum(1 for r in results if r["status_code"] == -1)
    other_errors = failed_count - inventory_shortage - connection_errors
    
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    min_response_time = min(response_times) if response_times else 0
    max_response_time = max(response_times) if response_times else 0
    
    qps = CONCURRENT_USERS / total_time if total_time > 0 else 0
    
    print("\n[结果统计]")
    print("-" * 70)
    print(f"  总请求数: {len(results)}")
    print(f"  成功购票数: {success_count} ({success_count/len(results)*100:.1f}%)")
    print(f"  失败购票数: {failed_count} ({failed_count/len(results)*100:.1f}%)")
    print(f"    - 库存不足: {inventory_shortage}")
    print(f"    - 连接错误: {connection_errors}")
    print(f"    - 其他错误: {other_errors}")
    print("")
    print(f"  响应时间统计:")
    print(f"    平均响应时间: {avg_response_time*1000:.2f} ms")
    print(f"    最小响应时间: {min_response_time*1000:.2f} ms")
    print(f"    最大响应时间: {max_response_time*1000:.2f} ms")
    print(f"    QPS (每秒请求数): {qps:.2f}")
    print("")
    print(f"  总耗时: {total_time:.2f} 秒")
    
    print("\n[最终库存检查]")
    print("-" * 70)
    try:
        spot_response = requests.get(f"{BASE_URL}/scenic-spots/{TEST_SCENIC_SPOT_ID}")
        if spot_response.status_code == 200:
            spot_data = spot_response.json()
            final_inventory = spot_data.get("remained_inventory", 0)
            sold_count = initial_inventory - final_inventory
            print(f"  初始库存: {initial_inventory}")
            print(f"  最终库存: {final_inventory}")
            print(f"  已售出: {sold_count}")
            
            if sold_count == success_count:
                print(f"  [验证通过] 售出数量 ({sold_count}) 与成功订单数 ({success_count}) 一致")
            else:
                print(f"  [验证警告] 售出数量 ({sold_count}) 与成功订单数 ({success_count}) 不一致")
            
            if final_inventory >= 0:
                print(f"  [验证通过] 库存非负: {final_inventory}")
            else:
                print(f"  [验证失败] 库存为负: {final_inventory} - 可能存在超卖!")
        else:
            print("  无法获取最终库存信息")
    except Exception as e:
        print(f"  检查最终库存失败: {e}")
    
    print("\n[日志文件检查]")
    print("-" * 70)
    log_file = "app.log"
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        valid_json_count = 0
        for line in lines:
            try:
                json.loads(line.strip())
                valid_json_count += 1
            except:
                pass
        
        print(f"  日志文件: {log_file}")
        print(f"  总行数: {len(lines)}")
        print(f"  有效 JSON 日志: {valid_json_count}")
        
        if valid_json_count == len(lines) and len(lines) > 0:
            print("  [验证通过] 所有日志行都是有效的 JSON 格式")
        elif len(lines) > 0:
            print(f"  [验证警告] 存在 {len(lines) - valid_json_count} 行无效 JSON")
            print("                 可能是并发写入导致的日志交错")
        
    except FileNotFoundError:
        print(f"  日志文件不存在: {log_file}")
    except Exception as e:
        print(f"  检查日志文件失败: {e}")
    
    print("\n" + "=" * 70)
    print("  压力测试完成")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    run_stress_test()
