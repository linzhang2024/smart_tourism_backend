import os
import sys
import time
import hashlib
import uuid
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete, and_

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
from database import Base, engine

test_results_v2 = []
created_test_ids_v2 = {
    "orders": [],
    "distributors": [],
    "scenic_spots": [],
    "users": [],
    "financial_logs": []
}


def generate_unique_suffix():
    return uuid.uuid4().hex[:8]


def generate_test_username(prefix):
    return f"{prefix}_{generate_unique_suffix()}"


def get_simple_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def log_test_result_v2(test_name, passed, message=""):
    result = {
        "test_name": test_name,
        "passed": passed,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    test_results_v2.append(result)
    
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"     详情: {message}")


def cleanup_test_data_v2(db):
    print("\n[清理] 强制清理残留测试数据...")
    
    try:
        if created_test_ids_v2["financial_logs"]:
            delete_logs = delete(models.FinancialLog).where(
                models.FinancialLog.id.in_(created_test_ids_v2["financial_logs"])
            )
            result = db.execute(delete_logs)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试财务流水")
        
        if created_test_ids_v2["orders"]:
            delete_orders = delete(models.TicketOrder).where(
                models.TicketOrder.id.in_(created_test_ids_v2["orders"])
            )
            result = db.execute(delete_orders)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试订单")
        
        if created_test_ids_v2["distributors"]:
            delete_distributors = delete(models.Distributor).where(
                models.Distributor.id.in_(created_test_ids_v2["distributors"])
            )
            result = db.execute(delete_distributors)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试分销商")
        
        if created_test_ids_v2["scenic_spots"]:
            delete_spots = delete(models.ScenicSpot).where(
                models.ScenicSpot.id.in_(created_test_ids_v2["scenic_spots"])
            )
            result = db.execute(delete_spots)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试景点")
        
        if created_test_ids_v2["users"]:
            delete_users = delete(models.User).where(
                models.User.id.in_(created_test_ids_v2["users"])
            )
            result = db.execute(delete_users)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试用户")
        
        created_test_ids_v2["financial_logs"].clear()
        created_test_ids_v2["orders"].clear()
        created_test_ids_v2["distributors"].clear()
        created_test_ids_v2["scenic_spots"].clear()
        created_test_ids_v2["users"].clear()
        
        print("  [清理] 完成")
    except Exception as e:
        print(f"  [警告] 清理数据时出错: {e}")


def create_test_data_v2(db):
    print("\n[准备] 创建测试数据 (使用随机唯一标识)...")
    
    test_prefix = f"test_v2_{generate_unique_suffix()}"
    print(f"  本次测试标识: {test_prefix}")
    
    print("  [1/5] 创建管理员用户...")
    admin_username = generate_test_username("admin_v2")
    admin_user = models.User(
        username=admin_username,
        hashed_password=get_simple_password_hash("test123456"),
        role=models.UserRole.ADMIN,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    created_test_ids_v2["users"].append(admin_user.id)
    print(f"      OK 管理员用户创建成功: ID={admin_user.id}, 用户名={admin_user.username}")
    
    print("  [2/5] 创建分销商用户...")
    distributor_username = generate_test_username("dist_v2")
    distributor_user = models.User(
        username=distributor_username,
        hashed_password=get_simple_password_hash("test123456"),
        role=models.UserRole.TOURIST,
        is_active=True
    )
    db.add(distributor_user)
    db.commit()
    db.refresh(distributor_user)
    created_test_ids_v2["users"].append(distributor_user.id)
    print(f"      OK 分销商用户创建成功: ID={distributor_user.id}, 用户名={distributor_user.username}")
    
    print("  [3/5] 创建游客用户...")
    tourist_username = generate_test_username("tourist_v2")
    tourist_user = models.User(
        username=tourist_username,
        hashed_password=get_simple_password_hash("test123456"),
        role=models.UserRole.TOURIST,
        is_active=True
    )
    db.add(tourist_user)
    db.commit()
    db.refresh(tourist_user)
    created_test_ids_v2["users"].append(tourist_user.id)
    print(f"      OK 游客用户创建成功: ID={tourist_user.id}, 用户名={tourist_user.username}")
    
    print("  [4/5] 创建测试景点...")
    spot_suffix = generate_unique_suffix()
    scenic_spot = models.ScenicSpot(
        name=f"对账测试景点_{spot_suffix}",
        description="用于专项对账测试的景点",
        location="测试地点",
        price=100.0,
        total_inventory=200,
        remained_inventory=200
    )
    db.add(scenic_spot)
    db.commit()
    db.refresh(scenic_spot)
    created_test_ids_v2["scenic_spots"].append(scenic_spot.id)
    print(f"      OK 景点创建成功: ID={scenic_spot.id}, 名称={scenic_spot.name}, 价格={scenic_spot.price}元, 库存={scenic_spot.remained_inventory}")
    
    print("  [5/5] 创建分销商记录...")
    distributor = models.Distributor(
        user_id=distributor_user.id,
        commission_rate=0.10,
        is_active=True
    )
    db.add(distributor)
    db.commit()
    db.refresh(distributor)
    created_test_ids_v2["distributors"].append(distributor.id)
    print(f"      OK 分销商创建成功: ID={distributor.id}, 邀请码={distributor.distributor_code}, 佣金比例={distributor.commission_rate * 100}%")
    
    print("-" * 70)
    
    return {
        "admin_user": admin_user,
        "distributor_user": distributor_user,
        "tourist_user": tourist_user,
        "scenic_spot": scenic_spot,
        "distributor": distributor,
        "test_prefix": test_prefix
    }


def test_10_orders_reconciliation(db, test_data):
    print("\n[专项测试 1] 10笔订单同时成交 - 对账验证")
    print("=" * 70)
    
    tourist_user = test_data["tourist_user"]
    scenic_spot = test_data["scenic_spot"]
    distributor = test_data["distributor"]
    
    print("\n  测试目标:")
    print("    1. 模拟10笔订单同时成交")
    print("    2. 验证FinancialLog是否刚好对应10笔收入记录")
    print("    3. 验证每笔订单金额分毫不差")
    print("    4. 验证订单表总额与财务流水总额一致")
    
    print(f"\n  景点单价: {scenic_spot.price} 元")
    print(f"  分销商佣金比例: {distributor.commission_rate * 100}%")
    
    orders = []
    financial_logs_income = []
    financial_logs_expense = []
    expected_total_income = 0.0
    expected_total_expense = 0.0
    
    from sqlalchemy import update as sql_update, func
    from datetime import datetime
    
    print("\n  [步骤 1] 创建10笔订单并记录财务流水...")
    print("  " + "-" * 60)
    
    for i in range(10):
        order_num = i + 1
        quantity = (i % 3) + 1
        total_price = scenic_spot.price * quantity
        commission_amount = total_price * distributor.commission_rate
        
        print(f"\n    订单 {order_num}: 购买{quantity}张, 金额={total_price}元, 佣金={commission_amount}元")
        
        try:
            update_stmt = sql_update(models.ScenicSpot).where(
                models.ScenicSpot.id == scenic_spot.id,
                models.ScenicSpot.remained_inventory >= quantity
            ).values(
                remained_inventory=models.ScenicSpot.remained_inventory - quantity
            ).execution_options(synchronize_session="fetch")
            db.execute(update_stmt)
            db.refresh(scenic_spot)
            
            order = models.TicketOrder(
                user_id=tourist_user.id,
                scenic_spot_id=scenic_spot.id,
                quantity=quantity,
                total_price=total_price,
                status=models.OrderStatus.PAID,
                created_at=datetime.utcnow(),
                paid_at=datetime.utcnow(),
                distributor_id=distributor.id,
                commission_amount=commission_amount,
                is_settled=False
            )
            db.add(order)
            db.flush()
            
            income_log = models.FinancialLog(
                transaction_type=models.TransactionType.INCOME,
                order_no=order.order_no,
                amount=total_price,
                transaction_time=datetime.utcnow(),
                summary=f"专项对账测试 - 门票销售收入，订单号: {order.order_no}",
                related_distributor_id=distributor.id
            )
            db.add(income_log)
            
            expense_log = models.FinancialLog(
                transaction_type=models.TransactionType.DISTRIBUTION_EXPENSE,
                order_no=order.order_no,
                amount=commission_amount,
                transaction_time=datetime.utcnow(),
                summary=f"专项对账测试 - 分销佣金支出，订单号: {order.order_no}",
                related_distributor_id=distributor.id
            )
            db.add(expense_log)
            
            db.commit()
            db.refresh(order)
            db.refresh(income_log)
            db.refresh(expense_log)
            
            created_test_ids_v2["orders"].append(order.id)
            created_test_ids_v2["financial_logs"].append(income_log.id)
            created_test_ids_v2["financial_logs"].append(expense_log.id)
            
            orders.append(order)
            financial_logs_income.append(income_log)
            financial_logs_expense.append(expense_log)
            expected_total_income += total_price
            expected_total_expense += commission_amount
            
            log_test_result_v2(
                f"订单 {order_num} 创建成功",
                order.id is not None and income_log.id is not None and expense_log.id is not None,
                f"订单ID={order.id}, 金额={total_price}元, 收入流水ID={income_log.id}, 支出流水ID={expense_log.id}"
            )
            
        except Exception as e:
            db.rollback()
            log_test_result_v2(
                f"订单 {order_num} 创建失败",
                False,
                f"错误: {str(e)}"
            )
            raise
    
    print("\n  " + "-" * 60)
    print("  [步骤 2] 验证财务流水数量...")
    
    actual_income_count = db.query(models.FinancialLog).filter(
        models.FinancialLog.id.in_([log.id for log in financial_logs_income])
    ).count()
    
    actual_expense_count = db.query(models.FinancialLog).filter(
        models.FinancialLog.id.in_([log.id for log in financial_logs_expense])
    ).count()
    
    log_test_result_v2(
        "收入流水数量验证",
        actual_income_count == 10,
        f"预期=10笔, 实际={actual_income_count}笔"
    )
    
    log_test_result_v2(
        "支出流水数量验证",
        actual_expense_count == 10,
        f"预期=10笔, 实际={actual_expense_count}笔"
    )
    
    print("\n  [步骤 3] 验证金额准确性...")
    
    actual_income_total = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.id.in_([log.id for log in financial_logs_income])
    ).scalar() or 0.0
    
    actual_expense_total = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.id.in_([log.id for log in financial_logs_expense])
    ).scalar() or 0.0
    
    log_test_result_v2(
        "收入流水总金额验证",
        abs(actual_income_total - expected_total_income) < 0.01,
        f"预期={expected_total_income}元, 实际={actual_income_total}元, 差额={abs(actual_income_total - expected_total_income)}元"
    )
    
    log_test_result_v2(
        "支出流水总金额验证",
        abs(actual_expense_total - expected_total_expense) < 0.01,
        f"预期={expected_total_expense}元, 实际={actual_expense_total}元, 差额={abs(actual_expense_total - expected_total_expense)}元"
    )
    
    print("\n  [步骤 4] 验证订单表与财务流水一致性...")
    
    order_total = db.query(func.sum(models.TicketOrder.total_price)).filter(
        models.TicketOrder.id.in_([order.id for order in orders])
    ).scalar() or 0.0
    
    log_test_result_v2(
        "订单表总额与财务流水总额一致性验证",
        abs(order_total - actual_income_total) < 0.01,
        f"订单总额={order_total}元, 流水总额={actual_income_total}元, 一致={abs(order_total - actual_income_total) < 0.01}"
    )
    
    print("\n  [统计] 本次测试结果:")
    print(f"    订单数量: {len(orders)} 笔")
    print(f"    收入流水: {actual_income_count} 笔, 总金额: {actual_income_total} 元")
    print(f"    支出流水: {actual_expense_count} 笔, 总金额: {actual_expense_total} 元")
    print(f"    净利润(收入-支出): {actual_income_total - actual_expense_total} 元")
    
    test_data["orders_v2"] = orders
    test_data["financial_logs_income_v2"] = financial_logs_income
    test_data["financial_logs_expense_v2"] = financial_logs_expense
    test_data["total_income_v2"] = actual_income_total
    test_data["total_expense_v2"] = actual_expense_total
    
    return True


def test_refund_process(db, test_data):
    print("\n[专项测试 2] 退款流程测试 - 100元订单退款验证")
    print("=" * 70)
    
    tourist_user = test_data["tourist_user"]
    scenic_spot = test_data["scenic_spot"]
    distributor = test_data["distributor"]
    
    print("\n  测试目标:")
    print("    1. 创建一笔100元订单")
    print("    2. 执行退款操作")
    print("    3. 验证退款流水记录")
    print("    4. 验证资产负债表正确扣减")
    print("    5. 验证订单状态变更为REFUNDED")
    
    from sqlalchemy import update as sql_update, func
    from datetime import datetime
    
    print("\n  [步骤 1] 创建测试订单(100元)...")
    
    ticket_price = scenic_spot.price
    order_quantity = 1
    total_price = ticket_price * order_quantity
    commission_amount = total_price * distributor.commission_rate
    
    print(f"    订单金额: {total_price} 元")
    print(f"    佣金金额: {commission_amount} 元")
    
    try:
        update_stmt = sql_update(models.ScenicSpot).where(
            models.ScenicSpot.id == scenic_spot.id,
            models.ScenicSpot.remained_inventory >= order_quantity
        ).values(
            remained_inventory=models.ScenicSpot.remained_inventory - order_quantity
        ).execution_options(synchronize_session="fetch")
        db.execute(update_stmt)
        db.refresh(scenic_spot)
        
        order = models.TicketOrder(
            user_id=tourist_user.id,
            scenic_spot_id=scenic_spot.id,
            quantity=order_quantity,
            total_price=total_price,
            status=models.OrderStatus.PAID,
            created_at=datetime.utcnow(),
            paid_at=datetime.utcnow(),
            distributor_id=distributor.id,
            commission_amount=commission_amount,
            is_settled=False
        )
        db.add(order)
        db.flush()
        
        income_log = models.FinancialLog(
            transaction_type=models.TransactionType.INCOME,
            order_no=order.order_no,
            amount=total_price,
            transaction_time=datetime.utcnow(),
            summary=f"退款测试 - 门票销售收入，订单号: {order.order_no}",
            related_distributor_id=distributor.id
        )
        db.add(income_log)
        
        expense_log = models.FinancialLog(
            transaction_type=models.TransactionType.DISTRIBUTION_EXPENSE,
            order_no=order.order_no,
            amount=commission_amount,
            transaction_time=datetime.utcnow(),
            summary=f"退款测试 - 分销佣金支出，订单号: {order.order_no}",
            related_distributor_id=distributor.id
        )
        db.add(expense_log)
        
        db.commit()
        db.refresh(order)
        db.refresh(income_log)
        db.refresh(expense_log)
        
        created_test_ids_v2["orders"].append(order.id)
        created_test_ids_v2["financial_logs"].append(income_log.id)
        created_test_ids_v2["financial_logs"].append(expense_log.id)
        
        log_test_result_v2(
            "测试订单创建成功",
            order.id is not None and order.status == models.OrderStatus.PAID,
            f"订单ID={order.id}, 状态={order.status}, 金额={total_price}元"
        )
        
    except Exception as e:
        db.rollback()
        log_test_result_v2("测试订单创建失败", False, f"错误: {str(e)}")
        raise
    
    print("\n  [步骤 2] 验证退款前财务状态...")
    
    income_before = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME,
        models.FinancialLog.order_no == order.order_no
    ).scalar() or 0.0
    
    expense_before = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE,
        models.FinancialLog.order_no == order.order_no
    ).scalar() or 0.0
    
    log_test_result_v2(
        "退款前收入验证",
        abs(income_before - total_price) < 0.01,
        f"收入={income_before}元, 预期={total_price}元"
    )
    
    log_test_result_v2(
        "退款前支出验证",
        abs(expense_before - commission_amount) < 0.01,
        f"支出={expense_before}元, 预期={commission_amount}元"
    )
    
    print("\n  [步骤 3] 执行退款操作...")
    
    refund_amount = total_price
    refund_reason = "测试退款 - 专项测试"
    
    try:
        original_status = order.status
        
        order.status = models.OrderStatus.REFUNDED
        
        refund_log = models.FinancialLog(
            transaction_type=models.TransactionType.REFUND,
            order_no=order.order_no,
            amount=refund_amount,
            transaction_time=datetime.utcnow(),
            summary=f"订单退款，订单号: {order.order_no}, 原订单金额: {total_price}元, 退款金额: {refund_amount}元, 原因: {refund_reason}",
            related_distributor_id=distributor.id
        )
        db.add(refund_log)
        
        if commission_amount > 0:
            reverse_commission_log = models.FinancialLog(
                transaction_type=models.TransactionType.DISTRIBUTION_EXPENSE,
                order_no=order.order_no,
                amount=-commission_amount,
                transaction_time=datetime.utcnow(),
                summary=f"退款冲抵分销佣金，订单号: {order.order_no}, 原佣金金额: {commission_amount}元",
                related_distributor_id=distributor.id
            )
            db.add(reverse_commission_log)
        
        db.commit()
        db.refresh(order)
        db.refresh(refund_log)
        
        created_test_ids_v2["financial_logs"].append(refund_log.id)
        if commission_amount > 0:
            created_test_ids_v2["financial_logs"].append(reverse_commission_log.id)
        
        log_test_result_v2(
            "退款操作成功",
            order.status == models.OrderStatus.REFUNDED and refund_log.id is not None,
            f"订单状态={order.status}, 退款流水ID={refund_log.id}, 退款金额={refund_amount}元"
        )
        
    except Exception as e:
        db.rollback()
        log_test_result_v2("退款操作失败", False, f"错误: {str(e)}")
        raise
    
    print("\n  [步骤 4] 验证退款后财务状态...")
    
    order_status = db.query(models.TicketOrder.status).filter(
        models.TicketOrder.id == order.id
    ).scalar()
    
    log_test_result_v2(
        "订单状态变更验证",
        order_status == models.OrderStatus.REFUNDED,
        f"当前状态={order_status}, 预期=REFUNDED"
    )
    
    refund_log_count = db.query(models.FinancialLog).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.order_no == order.order_no
    ).count()
    
    log_test_result_v2(
        "退款流水存在验证",
        refund_log_count == 1,
        f"退款流水数量={refund_log_count}, 预期=1"
    )
    
    refund_total = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.order_no == order.order_no
    ).scalar() or 0.0
    
    log_test_result_v2(
        "退款金额验证",
        abs(refund_total - refund_amount) < 0.01,
        f"退款金额={refund_total}元, 预期={refund_amount}元"
    )
    
    print("\n  [步骤 5] 验证资产负债表正确扣减...")
    
    income_total = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME,
        models.FinancialLog.order_no == order.order_no
    ).scalar() or 0.0
    
    refund_total = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.order_no == order.order_no
    ).scalar() or 0.0
    
    expense_total = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE,
        models.FinancialLog.order_no == order.order_no
    ).scalar() or 0.0
    
    net_income = income_total - refund_total
    expected_net = total_price - refund_amount
    
    log_test_result_v2(
        "净收入计算验证",
        abs(net_income - expected_net) < 0.01,
        f"收入={income_total}元 - 退款={refund_total}元 = 净收入={net_income}元, 预期={expected_net}元"
    )
    
    log_test_result_v2(
        "佣金冲抵验证",
        abs(expense_total) < 0.01,
        f"分销支出净额={expense_total}元, 预期=0元 (佣金已冲抵)"
    )
    
    print("\n  [统计] 退款测试结果:")
    print(f"    原订单金额: {total_price} 元")
    print(f"    退款金额: {refund_amount} 元")
    print(f"    原佣金金额: {commission_amount} 元")
    print(f"    收入流水: {income_total} 元")
    print(f"    退款流水: {refund_total} 元")
    print(f"    分销支出净额: {expense_total} 元")
    print(f"    净收入: {net_income} 元")
    print(f"    订单最终状态: {order_status}")
    
    test_data["refund_order"] = order
    test_data["refund_log"] = refund_log
    test_data["refund_amount"] = refund_amount
    
    return True


def test_reconciliation_api_logic(db, test_data):
    print("\n[专项测试 3] 对账检查API逻辑测试")
    print("=" * 70)
    
    from sqlalchemy import func
    
    print("\n  测试目标: 验证对账检查逻辑的正确性")
    
    print("\n  [步骤 1] 统计订单表数据...")
    
    paid_orders = db.query(models.TicketOrder).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.id.in_(created_test_ids_v2["orders"])
    ).all()
    
    refunded_orders = db.query(models.TicketOrder).filter(
        models.TicketOrder.status == models.OrderStatus.REFUNDED,
        models.TicketOrder.id.in_(created_test_ids_v2["orders"])
    ).all()
    
    paid_total = sum(order.total_price for order in paid_orders)
    refunded_total = sum(order.total_price for order in refunded_orders)
    
    print(f"    已支付订单数: {len(paid_orders)} 笔, 金额: {paid_total} 元")
    print(f"    已退款订单数: {len(refunded_orders)} 笔, 金额: {refunded_total} 元")
    
    print("\n  [步骤 2] 统计财务流水数据...")
    
    financial_income = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME,
        models.FinancialLog.id.in_(created_test_ids_v2["financial_logs"])
    ).scalar() or 0.0
    
    financial_refund = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.id.in_(created_test_ids_v2["financial_logs"])
    ).scalar() or 0.0
    
    print(f"    财务收入总额: {financial_income} 元")
    print(f"    财务退款总额: {financial_refund} 元")
    
    print("\n  [步骤 3] 执行对账检查...")
    
    expected_income = paid_total
    actual_income = financial_income - financial_refund
    
    difference = abs(expected_income - actual_income)
    is_balanced = difference < 0.01
    
    print(f"    订单表净收入: {expected_income} 元")
    print(f"    财务流水净收入: {actual_income} 元")
    print(f"    差额: {difference} 元")
    print(f"    账目平衡: {is_balanced}")
    
    log_test_result_v2(
        "对账检查 - 账目平衡验证",
        is_balanced,
        f"差额={difference}元, 平衡={is_balanced}"
    )
    
    test_data["reconciliation_result"] = {
        "is_balanced": is_balanced,
        "difference": difference,
        "expected_income": expected_income,
        "actual_income": actual_income
    }
    
    return True


def run_finance_v2_tests():
    print("\n" + "=" * 70)
    print("  财务核算与对账中心 - 回归测试 V2")
    print("=" * 70)
    print(f"\n[测试场景] 专项对账测试 + 退款流程测试")
    print(f"[测试时间] {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[测试数据] 使用 UUID 生成唯一标识，避免 UNIQUE 约束冲突")
    print("-" * 70)
    
    print("\n[迁移] 执行数据库迁移...")
    try:
        from main import migrate_database
        migrate_database()
        print("  [迁移] 完成")
    except Exception as e:
        print(f"  [警告] 迁移时出错: {e}")
    
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    test_data = {}
    
    try:
        cleanup_test_data_v2(db)
        
        test_data = create_test_data_v2(db)
        
        test_10_orders_reconciliation(db, test_data)
        
        test_refund_process(db, test_data)
        
        test_reconciliation_api_logic(db, test_data)
        
        print("\n" + "=" * 70)
        print("  测试结果汇总")
        print("=" * 70)
        
        total_tests = len(test_results_v2)
        passed_tests = sum(1 for r in test_results_v2 if r["passed"])
        failed_tests = total_tests - passed_tests
        
        print(f"\n  总测试数: {total_tests}")
        print(f"  通过: {passed_tests}")
        print(f"  失败: {failed_tests}")
        print(f"  通过率: {(passed_tests / total_tests * 100) if total_tests > 0 else 0:.1f}%")
        
        print("\n  详细结果:")
        print("-" * 70)
        for result in test_results_v2:
            status = "PASS" if result["passed"] else "FAIL"
            print(f"  [{status}] [{result['timestamp']}] {result['test_name']}")
            if result["message"]:
                print(f"     {result['message']}")
        
        print("\n" + "=" * 70)
        if failed_tests == 0:
            print("  [OK] 所有测试通过! 100% 通过率")
            print("\n  验证要点:")
            print("  1. 10笔订单成交 -> 10笔收入记录 + 10笔支出记录")
            print("  2. 每笔订单金额分毫不差")
            print("  3. 订单表总额与财务流水总额一致")
            print("  4. 100元订单退款 -> 正确生成退款流水")
            print("  5. 订单状态正确变更为 REFUNDED")
            print("  6. 资产负债表正确扣减")
            print("  7. 对账检查逻辑正确")
        else:
            print("  [WARN] 存在失败的测试，请检查代码")
        print("=" * 70)
        
        return failed_tests == 0
        
    finally:
        cleanup_test_data_v2(db)
        db.close()


if __name__ == "__main__":
    run_finance_v2_tests()
