import threading
import time
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
from database import Base, engine, get_db


INITIAL_INVENTORY = 5
CONCURRENT_REQUESTS = 10
TICKETS_PER_REQUEST = 1

results = []
results_lock = threading.Lock()


def create_test_data(db):
    print("[准备] 创建测试数据...")
    
    tourist = models.Tourist(
        name="测试游客",
        email="test@example.com",
        phone="13800138000"
    )
    db.add(tourist)
    db.commit()
    db.refresh(tourist)
    print(f"[准备] 创建游客: ID={tourist.id}, 名称={tourist.name}")
    
    scenic_spot = models.ScenicSpot(
        name="测试景点",
        description="用于并发测试的景点",
        location="测试地点",
        price=100.0,
        total_inventory=INITIAL_INVENTORY,
        remained_inventory=INITIAL_INVENTORY
    )
    db.add(scenic_spot)
    db.commit()
    db.refresh(scenic_spot)
    print(f"[准备] 创建景点: ID={scenic_spot.id}, 名称={scenic_spot.name}, 库存={scenic_spot.remained_inventory}")
    
    return tourist.id, scenic_spot.id


def purchase_ticket_request(tourist_id, scenic_spot_id, quantity, session_factory, request_id):
    from main import purchase_ticket
    from fastapi import HTTPException
    
    db = session_factory()
    try:
        order_data = schemas.TicketOrderCreate(
            tourist_id=tourist_id,
            scenic_spot_id=scenic_spot_id,
            quantity=quantity
        )
        
        result = purchase_ticket(order_data, db)
        with results_lock:
            results.append({
                "request_id": request_id,
                "success": True,
                "order_no": result.order_no,
                "status": result.status.value,
                "quantity": result.quantity
            })
            print(f"[请求 {request_id}] 成功: 订单号={result.order_no}, 状态={result.status.value}")
            
    except HTTPException as e:
        with results_lock:
            results.append({
                "request_id": request_id,
                "success": False,
                "detail": e.detail,
                "status_code": e.status_code
            })
            print(f"[请求 {request_id}] 失败: 状态码={e.status_code}, 详情={e.detail}")
    except Exception as e:
        with results_lock:
            results.append({
                "request_id": request_id,
                "success": False,
                "detail": str(e),
                "status_code": 500
            })
            print(f"[请求 {request_id}] 错误: {str(e)}")
    finally:
        db.close()


def run_concurrent_test():
    print("\n" + "=" * 60)
    print("  门票支付并发测试")
    print("=" * 60)
    print(f"\n[参数] 初始库存: {INITIAL_INVENTORY}")
    print(f"[参数] 并发请求数: {CONCURRENT_REQUESTS}")
    print(f"[参数] 每请求购买数量: {TICKETS_PER_REQUEST}")
    print(f"[参数] 总需求: {CONCURRENT_REQUESTS * TICKETS_PER_REQUEST}")
    print(f"[预期] 成功订单数: {INITIAL_INVENTORY // TICKETS_PER_REQUEST}")
    print(f"[预期] 失败订单数: {CONCURRENT_REQUESTS - (INITIAL_INVENTORY // TICKETS_PER_REQUEST)}")
    print("-" * 60)
    
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        tourist_id, scenic_spot_id = create_test_data(db)
        
        print("\n[开始] 启动并发请求...")
        start_time = time.time()
        
        threads = []
        for i in range(CONCURRENT_REQUESTS):
            t = threading.Thread(
                target=purchase_ticket_request,
                args=(tourist_id, scenic_spot_id, TICKETS_PER_REQUEST, SessionLocal, i + 1)
            )
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        end_time = time.time()
        print(f"\n[完成] 所有请求完成，耗时: {end_time - start_time:.2f} 秒")
        print("-" * 60)
        
        final_spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
        all_orders = db.query(models.TicketOrder).filter(
            models.TicketOrder.scenic_spot_id == scenic_spot_id
        ).all()
        
        print("\n[结果统计]")
        print("-" * 60)
        
        success_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - success_count
        paid_orders = sum(1 for o in all_orders if o.status == models.OrderStatus.PAID)
        failed_orders = sum(1 for o in all_orders if o.status == models.OrderStatus.FAILED)
        
        print(f"  总请求数: {len(results)}")
        print(f"  成功请求数: {success_count}")
        print(f"  失败请求数: {failed_count}")
        print(f"\n  数据库统计:")
        print(f"    订单总数: {len(all_orders)}")
        print(f"    支付成功订单: {paid_orders}")
        print(f"    支付失败订单: {failed_orders}")
        print(f"    剩余库存: {final_spot.remained_inventory}")
        print(f"    初始库存: {INITIAL_INVENTORY}")
        print(f"    已售出: {INITIAL_INVENTORY - final_spot.remained_inventory}")
        
        print("\n[验证结果]")
        print("-" * 60)
        
        validation_passed = True
        
        if final_spot.remained_inventory >= 0:
            print(f"  [通过] 库存非负: {final_spot.remained_inventory}")
        else:
            print(f"  [失败] 库存为负: {final_spot.remained_inventory}")
            validation_passed = False
        
        expected_sold = min(INITIAL_INVENTORY, CONCURRENT_REQUESTS * TICKETS_PER_REQUEST)
        actual_sold = INITIAL_INVENTORY - final_spot.remained_inventory
        if actual_sold == paid_orders * TICKETS_PER_REQUEST:
            print(f"  [通过] 售出数量与成功订单数一致")
        else:
            print(f"  [失败] 售出数量({actual_sold})与成功订单数({paid_orders})不一致")
            validation_passed = False
        
        if success_count == paid_orders:
            print(f"  [通过] 成功请求数与成功订单数一致")
        else:
            print(f"  [失败] 成功请求数({success_count})与成功订单数({paid_orders})不一致")
            validation_passed = False
        
        print("\n[日志检查]")
        print("-" * 60)
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
            
            inventory_errors = [line for line in log_lines if '库存不足' in line]
            order_success = [line for line in log_lines if '订单创建成功' in line]
            payment_success = [line for line in log_lines if '支付成功' in line]
            
            print(f"  日志文件存在，共 {len(log_lines)} 行")
            print(f"  库存不足记录: {len(inventory_errors)} 条")
            print(f"  订单创建成功记录: {len(order_success)} 条")
            print(f"  支付成功记录: {len(payment_success)} 条")
            
            if len(order_success) == paid_orders:
                print(f"  [通过] 成功订单日志记录完整")
            else:
                print(f"  [警告] 成功订单日志记录({len(order_success)})与实际成功订单数({paid_orders})不一致")
        else:
            print(f"  [警告] 日志文件不存在: {log_file}")
        
        print("\n" + "=" * 60)
        if validation_passed:
            print("  测试通过! 并发处理正常。")
        else:
            print("  测试失败! 存在问题需要修复。")
        print("=" * 60)
        
        return validation_passed
        
    finally:
        tourist = db.query(models.Tourist).filter(models.Tourist.id == tourist_id).first()
        if tourist:
            orders = db.query(models.TicketOrder).filter(models.TicketOrder.tourist_id == tourist_id).all()
            for order in orders:
                db.delete(order)
            db.commit()
            db.delete(tourist)
        
        spot = db.query(models.ScenicSpot).filter(models.ScenicSpot.id == scenic_spot_id).first()
        if spot:
            orders = db.query(models.TicketOrder).filter(models.TicketOrder.scenic_spot_id == scenic_spot_id).all()
            for order in orders:
                db.delete(order)
            db.commit()
            db.delete(spot)
        
        db.commit()
        db.close()


if __name__ == "__main__":
    run_concurrent_test()
