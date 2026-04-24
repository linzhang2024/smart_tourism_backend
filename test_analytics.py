import os
import sys
import time
import hashlib
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete, and_, func

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
from database import Base, engine, get_db

test_results = []
created_test_ids = {
    "orders": [],
    "users": [],
    "financial_logs": [],
    "tourist_flows": [],
    "scenic_spots": []
}


def generate_unique_suffix():
    return uuid.uuid4().hex[:8]


def generate_test_username(prefix):
    return f"{prefix}_{generate_unique_suffix()}"


def get_simple_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def log_test_result(test_name, passed, message=""):
    result = {
        "test_name": test_name,
        "passed": passed,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    test_results.append(result)
    
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"     详情: {message}")


def cleanup_test_data(db):
    print("\n[清理] 强制清理残留测试数据...")
    
    try:
        if created_test_ids["tourist_flows"]:
            delete_flows = delete(models.TouristFlow).where(
                models.TouristFlow.id.in_(created_test_ids["tourist_flows"])
            )
            result = db.execute(delete_flows)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试流量记录")
        
        if created_test_ids["financial_logs"]:
            delete_logs = delete(models.FinancialLog).where(
                models.FinancialLog.id.in_(created_test_ids["financial_logs"])
            )
            result = db.execute(delete_logs)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试财务流水")
        
        if created_test_ids["orders"]:
            delete_orders = delete(models.TicketOrder).where(
                models.TicketOrder.id.in_(created_test_ids["orders"])
            )
            result = db.execute(delete_orders)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 条测试订单")
        
        if created_test_ids["scenic_spots"]:
            delete_spots = delete(models.ScenicSpot).where(
                models.ScenicSpot.id.in_(created_test_ids["scenic_spots"])
            )
            result = db.execute(delete_spots)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试景点")
        
        if created_test_ids["users"]:
            delete_users = delete(models.User).where(
                models.User.id.in_(created_test_ids["users"])
            )
            result = db.execute(delete_users)
            db.commit()
            if result.rowcount > 0:
                print(f"  已清理 {result.rowcount} 个测试用户")
        
    except Exception as e:
        print(f"  清理测试数据时出错: {e}")
        db.rollback()


def create_test_user(db, role=models.UserRole.TOURIST, member_level=models.MemberLevel.NORMAL):
    user = models.User(
        username=generate_test_username("analytics_test"),
        hashed_password=get_simple_password_hash("test123456"),
        role=role,
        member_level=member_level,
        phone=f"138{int(time.time() * 1000) % 10000000:07d}"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    created_test_ids["users"].append(user.id)
    return user


def create_test_scenic_spot(db):
    spot = models.ScenicSpot(
        name=f"测试景点_{generate_unique_suffix()}",
        description="性能测试专用景点",
        location="测试位置",
        price=100.0,
        total_inventory=10000,
        remained_inventory=10000
    )
    db.add(spot)
    db.commit()
    db.refresh(spot)
    created_test_ids["scenic_spots"].append(spot.id)
    return spot


def create_test_order(db, user, spot, total_price, status=models.OrderStatus.PAID, paid_at=None):
    order = models.TicketOrder(
        user_id=user.id,
        scenic_spot_id=spot.id,
        quantity=1,
        total_price=total_price,
        status=status,
        paid_at=paid_at or datetime.utcnow(),
        commission_amount=total_price * 0.05
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    created_test_ids["orders"].append(order.id)
    return order


def create_financial_log(db, transaction_type, amount, order_no=None, transaction_time=None):
    log = models.FinancialLog(
        transaction_type=transaction_type,
        order_no=order_no,
        amount=amount,
        transaction_time=transaction_time or datetime.utcnow(),
        summary=f"测试流水 - {transaction_type}"
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    created_test_ids["financial_logs"].append(log.id)
    return log


def create_tourist_flow(db, spot, entry_count, record_time=None):
    flow = models.TouristFlow(
        scenic_spot_id=spot.id,
        entry_count=entry_count,
        record_time=record_time or datetime.utcnow()
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)
    created_test_ids["tourist_flows"].append(flow.id)
    return flow


def calculate_overview_stats(db):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    month_start = today_start.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1)
    
    today_sales_total = db.query(func.sum(models.TicketOrder.total_price)).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.paid_at >= today_start,
        models.TicketOrder.paid_at < today_end
    ).scalar() or 0.0
    
    today_visitor_count = db.query(func.sum(models.TouristFlow.entry_count)).filter(
        models.TouristFlow.record_time >= today_start,
        models.TouristFlow.record_time < today_end
    ).scalar() or 0
    
    all_recent_flows = db.query(models.TouristFlow).filter(
        models.TouristFlow.record_time >= today_start - timedelta(hours=24)
    ).all()
    current_in_scenic_count = sum(flow.entry_count for flow in all_recent_flows)
    
    month_income = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.INCOME,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    month_distribution = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.DISTRIBUTION_EXPENSE,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    month_refund = db.query(func.sum(models.FinancialLog.amount)).filter(
        models.FinancialLog.transaction_type == models.TransactionType.REFUND,
        models.FinancialLog.transaction_time >= month_start,
        models.FinancialLog.transaction_time < month_end
    ).scalar() or 0.0
    
    month_total_profit = month_income - month_distribution - month_refund
    
    total_users = db.query(models.User).count()
    member_users = db.query(models.User).filter(
        models.User.member_level != models.MemberLevel.NORMAL
    ).count()
    member_conversion_rate = (member_users / total_users * 100) if total_users > 0 else 0.0
    
    return {
        "today_sales_total": round(today_sales_total, 2),
        "today_visitor_count": today_visitor_count,
        "current_in_scenic_count": current_in_scenic_count,
        "month_total_profit": round(month_total_profit, 2),
        "member_conversion_rate": round(member_conversion_rate, 2)
    }


def test_aggregate_performance(db):
    print("\n" + "=" * 60)
    print("测试 1: 高性能聚合查询性能测试")
    print("=" * 60)
    
    print("\n[准备] 创建测试数据...")
    
    admin_user = create_test_user(db, role=models.UserRole.ADMIN)
    spot = create_test_scenic_spot(db)
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)
    
    print("[准备] 创建批量测试订单和财务流水...")
    
    total_sales = 0.0
    total_visitors = 0
    total_income = 0.0
    total_distribution = 0.0
    order_count = 100
    
    for i in range(order_count):
        price = 100.0 + (i % 5) * 50.0
        order_time = today_start + timedelta(hours=i % 12)
        
        order = create_test_order(
            db, admin_user, spot, price, 
            paid_at=order_time
        )
        total_sales += price
        
        create_financial_log(
            db, 
            models.TransactionType.INCOME, 
            price, 
            order_no=order.order_no,
            transaction_time=order_time
        )
        total_income += price
        
        commission = price * 0.05
        create_financial_log(
            db, 
            models.TransactionType.DISTRIBUTION_EXPENSE, 
            commission, 
            order_no=order.order_no,
            transaction_time=order_time
        )
        total_distribution += commission
    
    print(f"[准备] 创建 {order_count} 条订单和 {order_count * 2} 条财务流水")
    
    print("\n[准备] 创建批量流量记录...")
    for i in range(50):
        entry_count = 10 + (i % 20)
        flow_time = today_start + timedelta(hours=i)
        create_tourist_flow(db, spot, entry_count, record_time=flow_time)
        total_visitors += entry_count
    
    print(f"[准备] 创建 50 条流量记录")
    
    print("\n[准备] 创建测试会员用户...")
    for i in range(20):
        if i % 3 == 0:
            create_test_user(db, member_level=models.MemberLevel.GOLD)
        elif i % 3 == 1:
            create_test_user(db, member_level=models.MemberLevel.SILVER)
        else:
            create_test_user(db, member_level=models.MemberLevel.NORMAL)
    
    print("\n[性能测试] 执行聚合查询...")
    
    db.expire_all()
    
    iterations = 10
    query_times = []
    
    print(f"[性能测试] 执行 {iterations} 次查询以测量性能...")
    
    for i in range(iterations):
        start_time = time.perf_counter()
        
        stats = calculate_overview_stats(db)
        
        end_time = time.perf_counter()
        elapsed = (end_time - start_time) * 1000
        query_times.append(elapsed)
        
        db.expire_all()
    
    avg_time = sum(query_times) / len(query_times)
    min_time = min(query_times)
    max_time = max(query_times)
    
    print(f"\n[性能测试结果]")
    print(f"  平均查询时间: {avg_time:.2f} ms")
    print(f"  最小查询时间: {min_time:.2f} ms")
    print(f"  最大查询时间: {max_time:.2f} ms")
    
    performance_passed = avg_time < 100
    log_test_result(
        "高性能聚合查询性能测试",
        performance_passed,
        f"平均查询时间 {avg_time:.2f}ms, 目标 < 100ms"
    )
    
    print("\n[数据一致性验证] 验证聚合数据准确性...")
    
    expected_profit = total_income - total_distribution
    actual_profit = stats["month_total_profit"]
    
    profit_consistent = abs(expected_profit - actual_profit) < 0.01
    
    log_test_result(
        "数据一致性 - 利润计算验证",
        profit_consistent,
        f"预期: {expected_profit:.2f}, 实际: {actual_profit:.2f}"
    )
    
    sales_consistent = abs(total_sales - stats["today_sales_total"]) < 0.01
    log_test_result(
        "数据一致性 - 销售额验证",
        sales_consistent,
        f"预期: {total_sales:.2f}, 实际: {stats['today_sales_total']:.2f}"
    )
    
    return performance_passed and profit_consistent and sales_consistent


def test_sales_trend_accuracy(db):
    print("\n" + "=" * 60)
    print("测试 2: 销售趋势接口数据准确性测试")
    print("=" * 60)
    
    print("\n[准备] 创建历史订单数据...")
    
    user = create_test_user(db, role=models.UserRole.ADMIN)
    spot = create_test_scenic_spot(db)
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    test_order_ids = []
    expected_daily_data = {}
    
    for i in range(7):
        day_offset = 6 - i
        order_date = today_start - timedelta(days=day_offset)
        
        daily_orders = 5 + i * 2
        daily_income = 0.0
        
        for j in range(daily_orders):
            price = 100.0 + j * 10.0
            order_time = order_date + timedelta(hours=10 + j % 8)
            
            order = create_test_order(
                db, user, spot, price,
                paid_at=order_time
            )
            test_order_ids.append(order.id)
            daily_income += price
            
            create_financial_log(
                db, models.TransactionType.INCOME,
                price, order_no=order.order_no,
                transaction_time=order_time
            )
        
        date_str = order_date.strftime('%Y-%m-%d')
        expected_daily_data[date_str] = {
            'order_count': daily_orders,
            'income': daily_income
        }
        
        print(f"  [准备] {date_str}: {daily_orders} 单, 收入 {daily_income:.2f} 元")
    
    print("\n[验证] 查询销售趋势数据...")
    
    days = 7
    period_end = today_start + timedelta(days=1)
    period_start = period_end - timedelta(days=days)
    
    from sqlalchemy import func as sql_func
    
    results = db.query(
        sql_func.date(models.TicketOrder.paid_at).label('order_date'),
        sql_func.count(models.TicketOrder.id).label('order_count'),
        sql_func.sum(models.TicketOrder.total_price).label('total_income')
    ).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.paid_at >= period_start,
        models.TicketOrder.paid_at < period_end,
        models.TicketOrder.id.in_(test_order_ids)
    ).group_by(
        sql_func.date(models.TicketOrder.paid_at)
    ).order_by(
        'order_date'
    ).all()
    
    actual_daily_data = {}
    for row in results:
        date_str = str(row.order_date)
        actual_daily_data[date_str] = {
            'order_count': row.order_count or 0,
            'income': row.total_income or 0.0
        }
    
    print("\n[验证结果]")
    
    all_passed = True
    for date_str, expected in expected_daily_data.items():
        actual = actual_daily_data.get(date_str, {'order_count': 0, 'income': 0.0})
        
        order_match = expected['order_count'] == actual['order_count']
        income_match = abs(expected['income'] - actual['income']) < 0.01
        
        passed = order_match and income_match
        all_passed = all_passed and passed
        
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {date_str}:")
        print(f"    订单数: 预期={expected['order_count']}, 实际={actual['order_count']}")
        print(f"    收入: 预期={expected['income']:.2f}, 实际={actual['income']:.2f}")
    
    log_test_result(
        "销售趋势接口数据准确性测试",
        all_passed,
        "验证了7天的销售数据与财务流水一致性"
    )
    
    return all_passed


def test_member_conversion_calculation(db):
    print("\n" + "=" * 60)
    print("测试 3: 会员转化率计算准确性测试")
    print("=" * 60)
    
    print("\n[准备] 创建测试用户...")
    
    initial_total = db.query(models.User).count()
    
    test_users = []
    
    for i in range(10):
        if i < 3:
            user = create_test_user(db, member_level=models.MemberLevel.GOLD)
        elif i < 6:
            user = create_test_user(db, member_level=models.MemberLevel.SILVER)
        else:
            user = create_test_user(db, member_level=models.MemberLevel.NORMAL)
        test_users.append(user)
    
    print(f"  [准备] 创建 10 个测试用户: 3黄金会员, 3白银会员, 4普通用户")
    
    print("\n[验证] 计算会员转化率...")
    
    total_users = db.query(models.User).count()
    member_users = db.query(models.User).filter(
        models.User.member_level != models.MemberLevel.NORMAL
    ).count()
    
    expected_conversion = (member_users / total_users * 100) if total_users > 0 else 0.0
    
    print(f"  总用户数: {total_users}")
    print(f"  会员用户数: {member_users}")
    print(f"  转化率: {expected_conversion:.2f}%")
    
    test_member_users = sum(1 for u in test_users if u.member_level != models.MemberLevel.NORMAL)
    test_total_users = len(test_users)
    test_conversion = (test_member_users / test_total_users * 100)
    
    expected_test_conversion = 60.0
    
    conversion_passed = abs(test_conversion - expected_test_conversion) < 0.01
    
    log_test_result(
        "会员转化率计算准确性测试",
        conversion_passed,
        f"测试用户组: 60% 会员, 计算值: {test_conversion:.2f}%"
    )
    
    return conversion_passed


def test_concurrent_performance(db):
    print("\n" + "=" * 60)
    print("测试 4: 并发查询性能测试")
    print("=" * 60)
    
    print("\n[准备] 创建大规模测试数据...")
    
    user = create_test_user(db, role=models.UserRole.ADMIN)
    spot = create_test_scenic_spot(db)
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(500):
        price = 50.0 + (i % 10) * 25.0
        order_time = today_start - timedelta(days=i % 7) + timedelta(hours=i % 12)
        
        order = create_test_order(db, user, spot, price, paid_at=order_time)
        
        create_financial_log(
            db, models.TransactionType.INCOME,
            price, order_no=order.order_no,
            transaction_time=order_time
        )
    
    print(f"  [准备] 创建 500 条订单和财务流水记录")
    
    print("\n[性能测试] 执行多次连续查询...")
    
    import threading
    import queue
    
    result_queue = queue.Queue()
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def run_query(iteration):
        thread_db = None
        try:
            thread_db = SessionLocal()
            start = time.perf_counter()
            
            stats = calculate_overview_stats(thread_db)
            
            end = time.perf_counter()
            elapsed = (end - start) * 1000
            
            result_queue.put({
                'iteration': iteration,
                'time': elapsed,
                'success': True
            })
        except Exception as e:
            result_queue.put({
                'iteration': iteration,
                'time': 0,
                'success': False,
                'error': str(e)
            })
        finally:
            if thread_db:
                thread_db.close()
    
    concurrent_count = 5
    threads = []
    
    print(f"  [测试] 启动 {concurrent_count} 个并发查询...")
    
    start_time = time.perf_counter()
    
    for i in range(concurrent_count):
        t = threading.Thread(target=run_query, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    end_time = time.perf_counter()
    total_elapsed = (end_time - start_time) * 1000
    
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    
    success_count = sum(1 for r in results if r['success'])
    times = [r['time'] for r in results if r['success']]
    
    avg_time = sum(times) / len(times) if times else 0
    
    print(f"\n[结果] 并发查询测试结果:")
    print(f"  总耗时: {total_elapsed:.2f} ms")
    print(f"  成功数: {success_count}/{concurrent_count}")
    print(f"  平均查询时间: {avg_time:.2f} ms")
    
    all_success = success_count == concurrent_count
    performance_ok = avg_time < 200
    
    log_test_result(
        "并发查询性能测试",
        all_success and performance_ok,
        f"成功数: {success_count}/{concurrent_count}, 平均时间: {avg_time:.2f}ms"
    )
    
    return all_success and performance_ok


def run_all_tests():
    print("=" * 60)
    print("智能大数据分析大屏 - 性能验证测试套件")
    print("=" * 60)
    print(f"测试开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        test_1_passed = test_aggregate_performance(db)
        test_2_passed = test_sales_trend_accuracy(db)
        test_3_passed = test_member_conversion_calculation(db)
        test_4_passed = test_concurrent_performance(db)
        
        print("\n" + "=" * 60)
        print("测试汇总报告")
        print("=" * 60)
        
        total_tests = len(test_results)
        passed_tests = sum(1 for r in test_results if r['passed'])
        
        print(f"\n总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {total_tests - passed_tests}")
        
        print("\n详细结果:")
        for result in test_results:
            status = "PASS" if result['passed'] else "FAIL"
            print(f"  [{status}] {result['test_name']}")
            if result['message']:
                print(f"         {result['message']}")
        
        if passed_tests == total_tests:
            print("\n" + "=" * 60)
            print("所有测试通过!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print(f"警告: {total_tests - passed_tests} 个测试失败!")
            print("=" * 60)
        
        return passed_tests == total_tests
        
    finally:
        print("\n" + "-" * 60)
        cleanup_test_data(db)
        db.close()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)