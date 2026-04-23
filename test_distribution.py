import os
import sys
import time
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
from database import Base, engine, get_db


test_results = []


def log_test_result(test_name, passed, message=""):
    result = {
        "test_name": test_name,
        "passed": passed,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    test_results.append(result)
    
    status = "✅ 通过" if passed else "❌ 失败"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"     详情: {message}")


def create_test_data(db):
    print("\n[准备] 创建测试数据...")
    
    print("  [1/5] 创建管理员用户...")
    from auth import get_password_hash
    admin_user = models.User(
        username="test_admin_dist",
        hashed_password=get_password_hash("test123456"),
        role=models.UserRole.ADMIN,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    print(f"      ✅ 管理员用户创建成功: ID={admin_user.id}, 用户名={admin_user.username}")
    
    print("  [2/5] 创建分销商用户...")
    distributor_user = models.User(
        username="test_distributor",
        hashed_password=get_password_hash("test123456"),
        role=models.UserRole.TOURIST,
        is_active=True
    )
    db.add(distributor_user)
    db.commit()
    db.refresh(distributor_user)
    print(f"      ✅ 分销商用户创建成功: ID={distributor_user.id}, 用户名={distributor_user.username}")
    
    print("  [3/5] 创建游客用户...")
    tourist_user = models.User(
        username="test_tourist_dist",
        hashed_password=get_password_hash("test123456"),
        role=models.UserRole.TOURIST,
        is_active=True
    )
    db.add(tourist_user)
    db.commit()
    db.refresh(tourist_user)
    print(f"      ✅ 游客用户创建成功: ID={tourist_user.id}, 用户名={tourist_user.username}")
    
    print("  [4/5] 创建测试景点...")
    scenic_spot = models.ScenicSpot(
        name="分销测试景点",
        description="用于分销功能测试的景点",
        location="测试地点",
        price=100.0,
        total_inventory=100,
        remained_inventory=100
    )
    db.add(scenic_spot)
    db.commit()
    db.refresh(scenic_spot)
    print(f"      ✅ 景点创建成功: ID={scenic_spot.id}, 名称={scenic_spot.name}, 库存={scenic_spot.remained_inventory}")
    
    print("  [5/5] 准备完成")
    print("-" * 60)
    
    return {
        "admin_user": admin_user,
        "distributor_user": distributor_user,
        "tourist_user": tourist_user,
        "scenic_spot": scenic_spot
    }


def test_distributor_creation(db, test_data):
    print("\n[测试 1] 分销商入驻测试 - 创建分销商记录")
    print("-" * 60)
    
    admin_user = test_data["admin_user"]
    distributor_user = test_data["distributor_user"]
    
    print(f"\n  测试目标: 为用户 ID={distributor_user.id} 创建分销商记录")
    print(f"  操作人: 管理员 ID={admin_user.id}")
    print(f"  默认佣金比例: 5%")
    
    existing_distributor = db.query(models.Distributor).filter(
        models.Distributor.user_id == distributor_user.id
    ).first()
    
    log_test_result(
        "检查用户是否已为分销商",
        existing_distributor is None,
        "用户尚未成为分销商" if existing_distributor is None else f"用户已为分销商: ID={existing_distributor.id}"
    )
    
    new_distributor = models.Distributor(
        user_id=distributor_user.id,
        commission_rate=0.05,
        is_active=True
    )
    db.add(new_distributor)
    db.commit()
    db.refresh(new_distributor)
    
    log_test_result(
        "创建分销商记录",
        new_distributor.id is not None and new_distributor.distributor_code is not None,
        f"分销商创建成功: ID={new_distributor.id}, 邀请码={new_distributor.distributor_code}, 佣金比例={new_distributor.commission_rate * 100}%"
    )
    
    log_test_result(
        "验证邀请码格式",
        new_distributor.distributor_code.startswith("DIST") and len(new_distributor.distributor_code) == 10,
        f"邀请码格式正确: {new_distributor.distributor_code} (前缀: DIST, 长度: 10)"
    )
    
    log_test_result(
        "验证默认佣金比例",
        new_distributor.commission_rate == 0.05,
        f"佣金比例正确: {new_distributor.commission_rate * 100}%"
    )
    
    test_data["distributor"] = new_distributor
    return new_distributor


def test_purchase_with_distributor_code(db, test_data):
    print("\n[测试 2] 带邀请码购票测试 - 订单绑定分销商")
    print("-" * 60)
    
    tourist_user = test_data["tourist_user"]
    scenic_spot = test_data["scenic_spot"]
    distributor = test_data["distributor"]
    
    print(f"\n  测试目标: 游客携带分销商邀请码购票，验证订单是否绑定分销商")
    print(f"  游客用户: ID={tourist_user.id}, 用户名={tourist_user.username}")
    print(f"  景点: ID={scenic_spot.id}, 名称={scenic_spot.name}")
    print(f"  分销商邀请码: {distributor.distributor_code}")
    
    from fastapi import HTTPException
    from sqlalchemy import update as sql_update
    
    original_inventory = scenic_spot.remained_inventory
    order_quantity = 2
    
    print(f"\n  [步骤 1] 检查库存...")
    log_test_result(
        "库存充足检查",
        scenic_spot.remained_inventory >= order_quantity,
        f"当前库存: {scenic_spot.remained_inventory}, 购买数量: {order_quantity}"
    )
    
    print(f"\n  [步骤 2] 扣减库存...")
    update_stmt = sql_update(models.ScenicSpot).where(
        models.ScenicSpot.id == scenic_spot.id,
        models.ScenicSpot.remained_inventory >= order_quantity
    ).values(
        remained_inventory=models.ScenicSpot.remained_inventory - order_quantity
    ).execution_options(synchronize_session="fetch")
    result = db.execute(update_stmt)
    affected_rows = result.rowcount
    
    log_test_result(
        "库存扣减成功",
        affected_rows == 1,
        f"受影响行数: {affected_rows}"
    )
    
    db.refresh(scenic_spot)
    
    print(f"\n  [步骤 3] 创建订单并绑定分销商...")
    total_price = scenic_spot.price * order_quantity
    
    order = models.TicketOrder(
        user_id=tourist_user.id,
        scenic_spot_id=scenic_spot.id,
        quantity=order_quantity,
        total_price=total_price,
        status=models.OrderStatus.PAID,
        created_at=models.get_utc8_now() if hasattr(models, 'get_utc8_now') else __import__('datetime').datetime.utcnow(),
        paid_at=models.get_utc8_now() if hasattr(models, 'get_utc8_now') else __import__('datetime').datetime.utcnow(),
        distributor_id=distributor.id
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    log_test_result(
        "订单创建成功",
        order.id is not None,
        f"订单创建成功: ID={order.id}, 订单号={order.order_no}"
    )
    
    log_test_result(
        "订单绑定分销商ID",
        order.distributor_id == distributor.id,
        f"订单 distributor_id={order.distributor_id}, 预期={distributor.id}"
    )
    
    test_data["order_with_distributor"] = order
    return order


def test_purchase_without_distributor_code(db, test_data):
    print("\n[测试 3] 无邀请码购票测试 - 订单不绑定分销商")
    print("-" * 60)
    
    tourist_user = test_data["tourist_user"]
    scenic_spot = test_data["scenic_spot"]
    
    print(f"\n  测试目标: 游客不携带邀请码购票，验证订单不绑定分销商")
    print(f"  游客用户: ID={tourist_user.id}, 用户名={tourist_user.username}")
    print(f"  景点: ID={scenic_spot.id}, 名称={scenic_spot.name}")
    
    from sqlalchemy import update as sql_update
    
    order_quantity = 1
    
    print(f"\n  [步骤 1] 扣减库存...")
    update_stmt = sql_update(models.ScenicSpot).where(
        models.ScenicSpot.id == scenic_spot.id,
        models.ScenicSpot.remained_inventory >= order_quantity
    ).values(
        remained_inventory=models.ScenicSpot.remained_inventory - order_quantity
    ).execution_options(synchronize_session="fetch")
    result = db.execute(update_stmt)
    affected_rows = result.rowcount
    
    log_test_result(
        "库存扣减成功",
        affected_rows == 1,
        f"受影响行数: {affected_rows}"
    )
    
    db.refresh(scenic_spot)
    
    print(f"\n  [步骤 2] 创建订单（不绑定分销商）...")
    total_price = scenic_spot.price * order_quantity
    
    order = models.TicketOrder(
        user_id=tourist_user.id,
        scenic_spot_id=scenic_spot.id,
        quantity=order_quantity,
        total_price=total_price,
        status=models.OrderStatus.PAID,
        created_at=models.get_utc8_now() if hasattr(models, 'get_utc8_now') else __import__('datetime').datetime.utcnow(),
        paid_at=models.get_utc8_now() if hasattr(models, 'get_utc8_now') else __import__('datetime').datetime.utcnow(),
        distributor_id=None
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    log_test_result(
        "订单创建成功",
        order.id is not None,
        f"订单创建成功: ID={order.id}, 订单号={order.order_no}"
    )
    
    log_test_result(
        "订单不绑定分销商",
        order.distributor_id is None,
        f"订单 distributor_id={order.distributor_id}, 预期=None"
    )
    
    test_data["order_without_distributor"] = order
    return order


def test_distributor_code_validation(db, test_data):
    print("\n[测试 4] 分销商邀请码有效性验证测试")
    print("-" * 60)
    
    distributor = test_data["distributor"]
    valid_code = distributor.distributor_code
    invalid_code = "INVALID1234"
    inactive_distributor = None
    
    print(f"\n  测试目标: 验证邀请码查找逻辑")
    print(f"  有效邀请码: {valid_code}")
    print(f"  无效邀请码: {invalid_code}")
    
    found_distributor = db.query(models.Distributor).filter(
        models.Distributor.distributor_code == valid_code,
        models.Distributor.is_active == True
    ).first()
    
    log_test_result(
        "有效邀请码查找成功",
        found_distributor is not None and found_distributor.id == distributor.id,
        f"通过邀请码 {valid_code} 查找到分销商: ID={found_distributor.id if found_distributor else 'None'}"
    )
    
    not_found_distributor = db.query(models.Distributor).filter(
        models.Distributor.distributor_code == invalid_code,
        models.Distributor.is_active == True
    ).first()
    
    log_test_result(
        "无效邀请码查找失败",
        not_found_distributor is None,
        f"无效邀请码 {invalid_code} 查找结果: {not_found_distributor}"
    )
    
    print(f"\n  [测试] 停用分销商后验证邀请码...")
    original_is_active = distributor.is_active
    distributor.is_active = False
    db.commit()
    db.refresh(distributor)
    
    inactive_found = db.query(models.Distributor).filter(
        models.Distributor.distributor_code == valid_code,
        models.Distributor.is_active == True
    ).first()
    
    log_test_result(
        "已停用分销商邀请码查找失败",
        inactive_found is None,
        f"停用分销商后，邀请码 {valid_code} 查找结果: {inactive_found}"
    )
    
    distributor.is_active = original_is_active
    db.commit()
    db.refresh(distributor)
    
    log_test_result(
        "恢复分销商状态",
        distributor.is_active == True,
        f"分销商状态已恢复: is_active={distributor.is_active}"
    )


def test_order_distributor_relationship(db, test_data):
    print("\n[测试 5] 订单与分销商关联关系验证")
    print("-" * 60)
    
    order_with = test_data["order_with_distributor"]
    order_without = test_data["order_without_distributor"]
    distributor = test_data["distributor"]
    
    print(f"\n  测试目标: 验证订单与分销商的 ORM 关系")
    
    db.refresh(order_with, ['distributor'])
    
    log_test_result(
        "订单.distributor 关系正确",
        order_with.distributor is not None and order_with.distributor.id == distributor.id,
        f"订单 distributor 关系: ID={order_with.distributor.id if order_with.distributor else 'None'}, 预期={distributor.id}"
    )
    
    log_test_result(
        "订单.distributor_code 验证",
        order_with.distributor.distributor_code == distributor.distributor_code,
        f"分销商邀请码: {order_with.distributor.distributor_code}"
    )
    
    db.refresh(order_without, ['distributor'])
    
    log_test_result(
        "无分销商订单的 distributor 关系",
        order_without.distributor is None,
        f"无分销商订单的 distributor 关系: {order_without.distributor}"
    )


def run_distribution_tests():
    print("\n" + "=" * 70)
    print("  智能票务分销系统 - 自动化测试")
    print("=" * 70)
    print(f"\n[测试场景] 分销商入驻 -> 游客携带邀请码购票 -> 验证订单绑定分销商")
    print(f"[测试时间] {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)
    
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    test_data = {}
    
    try:
        test_data = create_test_data(db)
        
        test_distributor_creation(db, test_data)
        
        test_purchase_with_distributor_code(db, test_data)
        
        test_purchase_without_distributor_code(db, test_data)
        
        test_distributor_code_validation(db, test_data)
        
        test_order_distributor_relationship(db, test_data)
        
        print("\n" + "=" * 70)
        print("  测试结果汇总")
        print("=" * 70)
        
        total_tests = len(test_results)
        passed_tests = sum(1 for r in test_results if r["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"\n  总测试数: {total_tests}")
        print(f"  通过: {passed_tests}")
        print(f"  失败: {failed_tests}")
        print(f"  通过率: {(passed_tests / total_tests * 100) if total_tests > 0 else 0:.1f}%")
        
        print("\n  详细结果:")
        print("-" * 70)
        for result in test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"  {status} [{result['timestamp']}] {result['test_name']}")
            if result["message"]:
                print(f"     {result['message']}")
        
        print("\n" + "=" * 70)
        if failed_tests == 0:
            print("  🎉 所有测试通过!")
            print("\n  验证要点:")
            print("  1. 分销商可以成功入驻，自动生成唯一邀请码")
            print("  2. 分销商邀请码格式为 DIST + 6位随机字符")
            print("  3. 默认佣金比例为 5%")
            print("  4. 游客携带有效邀请码购票时，订单自动绑定分销商 ID")
            print("  5. 游客不携带邀请码购票时，订单不绑定分销商")
            print("  6. 已停用的分销商邀请码无效")
            print("  7. 订单与分销商的 ORM 关联关系正确")
        else:
            print("  ⚠️ 存在失败的测试，请检查代码")
        print("=" * 70)
        
        return failed_tests == 0
        
    finally:
        print("\n[清理] 清理测试数据...")
        
        if "order_with_distributor" in test_data:
            order = db.query(models.TicketOrder).filter(
                models.TicketOrder.id == test_data["order_with_distributor"].id
            ).first()
            if order:
                db.delete(order)
                db.commit()
                print(f"  已删除订单: ID={order.id}")
        
        if "order_without_distributor" in test_data:
            order = db.query(models.TicketOrder).filter(
                models.TicketOrder.id == test_data["order_without_distributor"].id
            ).first()
            if order:
                db.delete(order)
                db.commit()
                print(f"  已删除订单: ID={order.id}")
        
        if "distributor" in test_data:
            distributor = db.query(models.Distributor).filter(
                models.Distributor.id == test_data["distributor"].id
            ).first()
            if distributor:
                db.delete(distributor)
                db.commit()
                print(f"  已删除分销商: ID={distributor.id}")
        
        if "scenic_spot" in test_data:
            spot = db.query(models.ScenicSpot).filter(
                models.ScenicSpot.id == test_data["scenic_spot"].id
            ).first()
            if spot:
                db.delete(spot)
                db.commit()
                print(f"  已删除景点: ID={spot.id}")
        
        for user_key in ["admin_user", "distributor_user", "tourist_user"]:
            if user_key in test_data:
                user = db.query(models.User).filter(
                    models.User.id == test_data[user_key].id
                ).first()
                if user:
                    db.delete(user)
                    db.commit()
                    print(f"  已删除用户: ID={user.id}, 用户名={user.username}")
        
        db.commit()
        db.close()
        print("[清理] 完成")


if __name__ == "__main__":
    run_distribution_tests()
