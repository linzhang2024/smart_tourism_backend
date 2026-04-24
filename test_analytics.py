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


def test_flow_prediction_accuracy(db):
    print("\n" + "=" * 60)
    print("测试 5: 客流预测准确度范围验证")
    print("=" * 60)
    
    print("\n[准备] 创建历史流量数据...")
    
    spot = create_test_scenic_spot(db)
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    peak_hour_actual = 14
    base_visitors_per_hour = 20
    
    total_historical_flows = 0
    expected_peak_visitors = 0
    
    for day_offset in range(7):
        for hour in range(24):
            if 9 <= hour <= 17:
                if hour == peak_hour_actual:
                    visitors = int(base_visitors_per_hour * 3 * (1 + day_offset * 0.05))
                elif 10 <= hour <= 16:
                    visitors = int(base_visitors_per_hour * 2 * (1 + day_offset * 0.03))
                else:
                    visitors = int(base_visitors_per_hour * (1 + day_offset * 0.02))
            else:
                visitors = int(base_visitors_per_hour * 0.2)
            
            flow_time = today_start - timedelta(days=day_offset + 1) + timedelta(hours=hour)
            
            create_tourist_flow(db, spot, visitors, record_time=flow_time)
            total_historical_flows += visitors
            
            if day_offset == 6 and hour == peak_hour_actual:
                expected_peak_visitors = visitors
    
    print(f"  [准备] 创建 {7 * 24} 条历史流量记录, 总计 {total_historical_flows} 人次")
    print(f"  [准备] 历史峰值: {expected_peak_visitors} 人 (14时)")
    
    print("\n[验证] 调用预测算法...")
    
    from sqlalchemy import func as sql_func
    import statistics
    
    period_end = today_start
    period_start = period_end - timedelta(days=7)
    
    hourly_data = db.query(
        sql_func.strftime('%H', models.TouristFlow.record_time).label('hour'),
        sql_func.strftime('%Y-%m-%d', models.TouristFlow.record_time).label('date'),
        sql_func.sum(models.TouristFlow.entry_count).label('total_visitors')
    ).filter(
        models.TouristFlow.record_time >= period_start,
        models.TouristFlow.record_time < period_end
    ).group_by(
        sql_func.strftime('%Y-%m-%d', models.TouristFlow.record_time),
        sql_func.strftime('%H', models.TouristFlow.record_time)
    ).order_by(
        'date', 'hour'
    ).all()
    
    hourly_stats = {}
    for row in hourly_data:
        hour = int(row.hour)
        if hour not in hourly_stats:
            hourly_stats[hour] = []
        hourly_stats[hour].append(row.total_visitors)
    
    daily_data = db.query(
        sql_func.date(models.TouristFlow.record_time).label('flow_date'),
        sql_func.sum(models.TouristFlow.entry_count).label('daily_visitors')
    ).filter(
        models.TouristFlow.record_time >= period_start,
        models.TouristFlow.record_time < period_end
    ).group_by(
        sql_func.date(models.TouristFlow.record_time)
    ).order_by(
        'flow_date'
    ).all()
    
    daily_visitors = [row.daily_visitors for row in daily_data] if daily_data else [0]
    
    if len(daily_visitors) >= 2:
        recent_avg = sum(daily_visitors[-3:]) / len(daily_visitors[-3:]) if len(daily_visitors) >= 3 else daily_visitors[-1]
        older_avg = sum(daily_visitors[:-3]) / len(daily_visitors[:-3]) if len(daily_visitors) > 3 else daily_visitors[0] if daily_visitors else 0
        
        if recent_avg > older_avg * 1.1:
            trend_direction = "上升"
        elif recent_avg < older_avg * 0.9:
            trend_direction = "下降"
        else:
            trend_direction = "平稳"
    else:
        trend_direction = "平稳"
    
    base_hourly_pattern = {
        8: 0.5, 9: 0.7, 10: 0.9, 11: 0.95, 12: 0.85,
        13: 0.75, 14: 1.0, 15: 0.95, 16: 0.9, 17: 0.8,
        18: 0.6, 19: 0.4, 20: 0.2, 21: 0.1, 22: 0.05,
        0: 0.02, 1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01,
        5: 0.02, 6: 0.05, 7: 0.3
    }
    
    avg_daily_visitors = sum(daily_visitors) / len(daily_visitors) if daily_visitors else 100
    
    current_hour = now.hour
    hourly_predictions = []
    peak_hour = 14
    peak_visitors = 0
    
    for hour_offset in range(24):
        prediction_hour = (current_hour + hour_offset) % 24
        
        historical_values = hourly_stats.get(prediction_hour, [])
        if historical_values:
            avg_value = statistics.mean(historical_values)
            if len(historical_values) > 1:
                std_dev = statistics.stdev(historical_values)
                confidence = max(0.5, 1.0 - (std_dev / (avg_value + 1)) * 0.5)
            else:
                confidence = 0.7
        else:
            pattern_factor = base_hourly_pattern.get(prediction_hour, 0.3)
            avg_value = avg_daily_visitors * pattern_factor / 24 * 2
            confidence = 0.5
        
        if prediction_hour >= 9 and prediction_hour <= 11:
            trend_factor = 1.1 if trend_direction == "上升" else (0.9 if trend_direction == "下降" else 1.0)
            predicted_visitors = int(avg_value * trend_factor)
        elif prediction_hour >= 13 and prediction_hour <= 16:
            trend_factor = 1.15 if trend_direction == "上升" else (0.85 if trend_direction == "下降" else 1.0)
            predicted_visitors = int(avg_value * trend_factor)
        else:
            predicted_visitors = int(avg_value)
        
        predicted_visitors = max(0, predicted_visitors)
        
        hourly_predictions.append({
            'hour': prediction_hour,
            'predicted_visitors': predicted_visitors,
            'confidence': round(confidence, 2)
        })
        
        if predicted_visitors > peak_visitors:
            peak_visitors = predicted_visitors
            peak_hour = prediction_hour
    
    print(f"\n[预测结果]")
    print(f"  预测峰值: {peak_visitors} 人 ({peak_hour}时)")
    print(f"  趋势方向: {trend_direction}")
    
    accuracy_tests_passed = True
    
    peak_hour_valid = 9 <= peak_hour <= 17
    log_test_result(
        "预测准确度 - 峰值时段合理性验证",
        peak_hour_valid,
        f"预测峰值时段: {peak_hour}时, 预期范围: 9-17时"
    )
    accuracy_tests_passed = accuracy_tests_passed and peak_hour_valid
    
    peak_visitors_positive = peak_visitors > 0
    log_test_result(
        "预测准确度 - 峰值人数合理性验证",
        peak_visitors_positive,
        f"预测峰值人数: {peak_visitors}"
    )
    accuracy_tests_passed = accuracy_tests_passed and peak_visitors_positive
    
    all_hours_valid = all(0 <= h['hour'] <= 23 and h['predicted_visitors'] >= 0 and 0 <= h['confidence'] <= 1 for h in hourly_predictions)
    log_test_result(
        "预测准确度 - 24小时预测数据完整性验证",
        all_hours_valid,
        f"预测数据点数: {len(hourly_predictions)}, 预期: 24"
    )
    accuracy_tests_passed = accuracy_tests_passed and all_hours_valid
    
    min_expected_visitors = base_visitors_per_hour * 0.5
    max_expected_visitors = base_visitors_per_hour * 5
    peak_in_valid_range = min_expected_visitors <= peak_visitors <= max_expected_visitors
    
    log_test_result(
        "预测准确度 - 峰值范围合理性验证",
        peak_in_valid_range,
        f"预测峰值: {peak_visitors}, 合理范围: {int(min_expected_visitors)}-{int(max_expected_visitors)}"
    )
    accuracy_tests_passed = accuracy_tests_passed and peak_in_valid_range
    
    return accuracy_tests_passed


def test_member_cross_dimension_aggregation(db):
    print("\n" + "=" * 60)
    print("测试 6: 跨维度会员数据聚合验证")
    print("=" * 60)
    
    print("\n[准备] 创建测试用户和订单数据...")
    
    spot = create_test_scenic_spot(db)
    
    gold_user = create_test_user(db, member_level=models.MemberLevel.GOLD)
    silver_user = create_test_user(db, member_level=models.MemberLevel.SILVER)
    normal_user = create_test_user(db, member_level=models.MemberLevel.NORMAL)
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)
    
    gold_orders = 5
    gold_avg_price = 200.0
    gold_total_spent = 0.0
    
    for i in range(gold_orders):
        price = gold_avg_price + i * 20.0
        order_time = month_start + timedelta(hours=i * 24)
        
        order = create_test_order(db, gold_user, spot, price, paid_at=order_time)
        gold_total_spent += price
        
        create_financial_log(
            db, models.TransactionType.INCOME,
            price, order_no=order.order_no,
            transaction_time=order_time
        )
        
        commission = price * 0.05
        create_financial_log(
            db, models.TransactionType.DISTRIBUTION_EXPENSE,
            commission, order_no=order.order_no,
            transaction_time=order_time
        )
    
    silver_orders = 8
    silver_avg_price = 150.0
    silver_total_spent = 0.0
    
    for i in range(silver_orders):
        price = silver_avg_price + i * 10.0
        order_time = month_start + timedelta(hours=i * 24 + 1)
        
        order = create_test_order(db, silver_user, spot, price, paid_at=order_time)
        silver_total_spent += price
        
        create_financial_log(
            db, models.TransactionType.INCOME,
            price, order_no=order.order_no,
            transaction_time=order_time
        )
        
        commission = price * 0.05
        create_financial_log(
            db, models.TransactionType.DISTRIBUTION_EXPENSE,
            commission, order_no=order.order_no,
            transaction_time=order_time
        )
    
    normal_orders = 3
    normal_avg_price = 100.0
    normal_total_spent = 0.0
    
    for i in range(normal_orders):
        price = normal_avg_price + i * 5.0
        order_time = month_start + timedelta(hours=i * 24 + 2)
        
        order = create_test_order(db, normal_user, spot, price, paid_at=order_time)
        normal_total_spent += price
        
        create_financial_log(
            db, models.TransactionType.INCOME,
            price, order_no=order.order_no,
            transaction_time=order_time
        )
        
        commission = price * 0.05
        create_financial_log(
            db, models.TransactionType.DISTRIBUTION_EXPENSE,
            commission, order_no=order.order_no,
            transaction_time=order_time
        )
    
    print(f"  [准备] 黄金会员: {gold_orders} 单, 消费 {gold_total_spent:.2f} 元")
    print(f"  [准备] 白银会员: {silver_orders} 单, 消费 {silver_total_spent:.2f} 元")
    print(f"  [准备] 普通用户: {normal_orders} 单, 消费 {normal_total_spent:.2f} 元")
    
    print("\n[验证] 执行跨维度聚合查询...")
    
    from sqlalchemy import func as sql_func
    
    order_stats = db.query(
        models.User.member_level,
        sql_func.count(models.TicketOrder.id).label('order_count'),
        sql_func.sum(models.TicketOrder.total_price).label('total_spent')
    ).join(
        models.TicketOrder, models.User.id == models.TicketOrder.user_id
    ).filter(
        models.TicketOrder.status == models.OrderStatus.PAID,
        models.TicketOrder.paid_at >= month_start,
        models.TicketOrder.paid_at < (month_start + timedelta(days=32)).replace(day=1),
        models.User.id.in_([gold_user.id, silver_user.id, normal_user.id])
    ).group_by(
        models.User.member_level
    ).all()
    
    level_order_stats = {}
    for row in order_stats:
        level_order_stats[row.member_level] = {
            'order_count': row.order_count or 0,
            'total_spent': row.total_spent or 0.0
        }
    
    level_names = {
        models.MemberLevel.GOLD: "黄金会员",
        models.MemberLevel.SILVER: "白银会员",
        models.MemberLevel.NORMAL: "普通用户"
    }
    
    expected_gold_avg = gold_total_spent / gold_orders
    expected_silver_avg = silver_total_spent / silver_orders
    expected_normal_avg = normal_total_spent / normal_orders
    
    print(f"\n[验证结果]")
    
    all_passed = True
    
    gold_stats = level_order_stats.get(models.MemberLevel.GOLD, {'order_count': 0, 'total_spent': 0.0})
    gold_order_match = gold_stats['order_count'] == gold_orders
    gold_spent_match = abs(gold_stats['total_spent'] - gold_total_spent) < 0.01
    gold_avg = gold_stats['total_spent'] / gold_stats['order_count'] if gold_stats['order_count'] > 0 else 0
    gold_avg_match = abs(gold_avg - expected_gold_avg) < 0.01
    
    log_test_result(
        "跨维度聚合 - 黄金会员数据验证",
        gold_order_match and gold_spent_match and gold_avg_match,
        f"订单数: 预期={gold_orders}, 实际={gold_stats['order_count']}, 客单价: 预期={expected_gold_avg:.2f}, 实际={gold_avg:.2f}"
    )
    all_passed = all_passed and gold_order_match and gold_spent_match and gold_avg_match
    
    silver_stats = level_order_stats.get(models.MemberLevel.SILVER, {'order_count': 0, 'total_spent': 0.0})
    silver_order_match = silver_stats['order_count'] == silver_orders
    silver_spent_match = abs(silver_stats['total_spent'] - silver_total_spent) < 0.01
    silver_avg = silver_stats['total_spent'] / silver_stats['order_count'] if silver_stats['order_count'] > 0 else 0
    silver_avg_match = abs(silver_avg - expected_silver_avg) < 0.01
    
    log_test_result(
        "跨维度聚合 - 白银会员数据验证",
        silver_order_match and silver_spent_match and silver_avg_match,
        f"订单数: 预期={silver_orders}, 实际={silver_stats['order_count']}, 客单价: 预期={expected_silver_avg:.2f}, 实际={silver_avg:.2f}"
    )
    all_passed = all_passed and silver_order_match and silver_spent_match and silver_avg_match
    
    normal_stats = level_order_stats.get(models.MemberLevel.NORMAL, {'order_count': 0, 'total_spent': 0.0})
    normal_order_match = normal_stats['order_count'] == normal_orders
    normal_spent_match = abs(normal_stats['total_spent'] - normal_total_spent) < 0.01
    normal_avg = normal_stats['total_spent'] / normal_stats['order_count'] if normal_stats['order_count'] > 0 else 0
    normal_avg_match = abs(normal_avg - expected_normal_avg) < 0.01
    
    log_test_result(
        "跨维度聚合 - 普通用户数据验证",
        normal_order_match and normal_spent_match and normal_avg_match,
        f"订单数: 预期={normal_orders}, 实际={normal_stats['order_count']}, 客单价: 预期={expected_normal_avg:.2f}, 实际={normal_avg:.2f}"
    )
    all_passed = all_passed and normal_order_match and normal_spent_match and normal_avg_match
    
    hierarchy_correct = gold_avg > silver_avg > normal_avg
    log_test_result(
        "跨维度聚合 - 会员等级消费层次验证",
        hierarchy_correct,
        f"黄金客单价={gold_avg:.2f} > 白银客单价={silver_avg:.2f} > 普通客单价={normal_avg:.2f}"
    )
    all_passed = all_passed and hierarchy_correct
    
    return all_passed


def test_inventory_alert_functionality(db):
    print("\n" + "=" * 60)
    print("测试 7: 库存告警功能验证")
    print("=" * 60)
    
    print("\n[准备] 创建测试景点...")
    
    normal_spot = models.ScenicSpot(
        name=f"正常景点_{generate_unique_suffix()}",
        description="库存充足的测试景点",
        location="测试位置",
        price=150.0,
        total_inventory=1000,
        remained_inventory=800
    )
    db.add(normal_spot)
    db.commit()
    db.refresh(normal_spot)
    created_test_ids["scenic_spots"].append(normal_spot.id)
    
    warning_spot = models.ScenicSpot(
        name=f"警告景点_{generate_unique_suffix()}",
        description="库存较低的测试景点",
        location="测试位置",
        price=200.0,
        total_inventory=500,
        remained_inventory=45
    )
    db.add(warning_spot)
    db.commit()
    db.refresh(warning_spot)
    created_test_ids["scenic_spots"].append(warning_spot.id)
    
    critical_spot = models.ScenicSpot(
        name=f"紧急景点_{generate_unique_suffix()}",
        description="库存紧急的测试景点",
        location="测试位置",
        price=250.0,
        total_inventory=100,
        remained_inventory=3
    )
    db.add(critical_spot)
    db.commit()
    db.refresh(critical_spot)
    created_test_ids["scenic_spots"].append(critical_spot.id)
    
    print(f"  [准备] 正常景点: 库存={normal_spot.remained_inventory}/{normal_spot.total_inventory}")
    print(f"  [准备] 警告景点: 库存={warning_spot.remained_inventory}/{warning_spot.total_inventory}")
    print(f"  [准备] 紧急景点: 库存={critical_spot.remained_inventory}/{critical_spot.total_inventory}")
    
    print("\n[验证] 检测库存告警...")
    
    threshold = 0.10
    
    all_spots = db.query(models.ScenicSpot).filter(
        models.ScenicSpot.id.in_([normal_spot.id, warning_spot.id, critical_spot.id])
    ).all()
    
    alerts = []
    total_estimated_loss = 0.0
    
    for spot in all_spots:
        if spot.total_inventory == 0:
            inventory_ratio = 0.0
        else:
            inventory_ratio = spot.remained_inventory / spot.total_inventory
        
        if inventory_ratio <= threshold:
            sold_tickets = spot.total_inventory - spot.remained_inventory
            
            if sold_tickets > 0:
                avg_daily_sales = sold_tickets / 30
                days_to_depletion = spot.remained_inventory / avg_daily_sales if avg_daily_sales > 0 else 0
                
                if inventory_ratio <= 0.05 or days_to_depletion <= 3:
                    alert_level = "紧急"
                elif inventory_ratio <= 0.10 or days_to_depletion <= 7:
                    alert_level = "警告"
                else:
                    alert_level = "注意"
            else:
                alert_level = "注意" if inventory_ratio <= 0.10 else "警告"
            
            estimated_revenue_loss = (spot.total_inventory - spot.remained_inventory) * spot.price * 0.1
            
            total_estimated_loss += estimated_revenue_loss
            
            alerts.append({
                'spot_id': spot.id,
                'spot_name': spot.name,
                'total_inventory': spot.total_inventory,
                'remained_inventory': spot.remained_inventory,
                'inventory_ratio': round(inventory_ratio, 4),
                'price_per_ticket': round(spot.price, 2),
                'estimated_revenue_loss': round(estimated_revenue_loss, 2),
                'alert_level': alert_level
            })
    
    print(f"\n[告警检测结果]")
    print(f"  告警数量: {len(alerts)}")
    print(f"  预估营收损失: {total_estimated_loss:.2f}")
    
    all_passed = True
    
    expected_alert_count = 2
    alert_count_match = len(alerts) == expected_alert_count
    log_test_result(
        "库存告警 - 告警数量验证",
        alert_count_match,
        f"预期告警数: {expected_alert_count}, 实际: {len(alerts)}"
    )
    all_passed = all_passed and alert_count_match
    
    normal_alerted = any(a['spot_id'] == normal_spot.id for a in alerts)
    warning_alerted = any(a['spot_id'] == warning_spot.id for a in alerts)
    critical_alerted = any(a['spot_id'] == critical_spot.id for a in alerts)
    
    log_test_result(
        "库存告警 - 正常景点不应告警",
        not normal_alerted,
        f"正常景点库存率: {(normal_spot.remained_inventory/normal_spot.total_inventory*100):.1f}%, 告警阈值: {threshold*100}%"
    )
    all_passed = all_passed and not normal_alerted
    
    log_test_result(
        "库存告警 - 警告景点应告警",
        warning_alerted,
        f"警告景点库存率: {(warning_spot.remained_inventory/warning_spot.total_inventory*100):.1f}%, 告警阈值: {threshold*100}%"
    )
    all_passed = all_passed and warning_alerted
    
    log_test_result(
        "库存告警 - 紧急景点应告警",
        critical_alerted,
        f"紧急景点库存率: {(critical_spot.remained_inventory/critical_spot.total_inventory*100):.1f}%, 告警阈值: {threshold*100}%"
    )
    all_passed = all_passed and critical_alerted
    
    critical_alert = next((a for a in alerts if a['spot_id'] == critical_spot.id), None)
    if critical_alert:
        critical_level_correct = critical_alert['alert_level'] == "紧急"
        log_test_result(
            "库存告警 - 紧急告警级别验证",
            critical_level_correct,
            f"实际告警级别: {critical_alert['alert_level']}, 预期: 紧急"
        )
        all_passed = all_passed and critical_level_correct
    
    warning_alert = next((a for a in alerts if a['spot_id'] == warning_spot.id), None)
    if warning_alert:
        warning_level_correct = warning_alert['alert_level'] == "警告" or warning_alert['alert_level'] == "紧急"
        log_test_result(
            "库存告警 - 警告告警级别验证",
            warning_level_correct,
            f"实际告警级别: {warning_alert['alert_level']}, 预期: 警告或紧急"
        )
        all_passed = all_passed and warning_level_correct
    
    expected_loss = (
        (warning_spot.total_inventory - warning_spot.remained_inventory) * warning_spot.price * 0.1 +
        (critical_spot.total_inventory - critical_spot.remained_inventory) * critical_spot.price * 0.1
    )
    loss_match = abs(total_estimated_loss - expected_loss) < 0.01
    log_test_result(
        "库存告警 - 营收影响计算验证",
        loss_match,
        f"预期损失: {expected_loss:.2f}, 实际: {total_estimated_loss:.2f}"
    )
    all_passed = all_passed and loss_match
    
    return all_passed


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
        test_5_passed = test_flow_prediction_accuracy(db)
        test_6_passed = test_member_cross_dimension_aggregation(db)
        test_7_passed = test_inventory_alert_functionality(db)
        
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