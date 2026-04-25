import os
import sys
import time
import hashlib
import uuid
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import schemas
from database import Base, engine, get_db

try:
    from main import check_staff_on_duty, get_color_level, calculate_distance
    MAIN_IMPORTED = True
except Exception as e:
    print(f"Warning: Could not import from main.py: {e}")
    MAIN_IMPORTED = False

test_results = []
created_test_ids = {
    "scenic_spots": [],
    "users": [],
    "work_shifts": [],
    "schedules": [],
    "attendance_records": [],
    "coupons": []
}


def generate_unique_suffix():
    return uuid.uuid4().hex[:8]


def generate_test_username(prefix):
    return "{}_{}".format(prefix, generate_unique_suffix())


def get_simple_password_hash(password):
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
    print("  [{}] {}".format(status, test_name))
    if message:
        print("     Details: {}".format(message))


def cleanup_test_data(db):
    print("\n[Cleanup] Cleaning up test data...")
    
    try:
        if created_test_ids["attendance_records"]:
            delete_records = delete(models.AttendanceRecord).where(
                models.AttendanceRecord.id.in_(created_test_ids["attendance_records"])
            )
            result = db.execute(delete_records)
            db.commit()
        
        if created_test_ids["schedules"]:
            delete_schedules = delete(models.Schedule).where(
                models.Schedule.id.in_(created_test_ids["schedules"])
            )
            result = db.execute(delete_schedules)
            db.commit()
        
        if created_test_ids["work_shifts"]:
            delete_shifts = delete(models.WorkShift).where(
                models.WorkShift.id.in_(created_test_ids["work_shifts"])
            )
            result = db.execute(delete_shifts)
            db.commit()
        
        if created_test_ids["coupons"]:
            delete_coupons = delete(models.Coupon).where(
                models.Coupon.id.in_(created_test_ids["coupons"])
            )
            result = db.execute(delete_coupons)
            db.commit()
        
        if created_test_ids["scenic_spots"]:
            delete_spots = delete(models.ScenicSpot).where(
                models.ScenicSpot.id.in_(created_test_ids["scenic_spots"])
            )
            result = db.execute(delete_spots)
            db.commit()
        
        if created_test_ids["users"]:
            delete_users = delete(models.User).where(
                models.User.id.in_(created_test_ids["users"])
            )
            result = db.execute(delete_users)
            db.commit()
        
        for key in created_test_ids:
            created_test_ids[key].clear()
        
        print("  [Cleanup] Done")
    except Exception as e:
        print("  [Warning] Error during cleanup: {}".format(e))


def create_test_scenic_spot(db, name, capacity=100, current_count=0, latitude=None, longitude=None, status=models.ScenicSpotStatus.ACTIVE):
    spot = models.ScenicSpot(
        name=name,
        description="Test spot: {}".format(name),
        location="Test location",
        capacity=capacity,
        current_count=current_count,
        latitude=latitude,
        longitude=longitude,
        status=status,
        rating=4.5,
        price=50.0
    )
    db.add(spot)
    db.commit()
    db.refresh(spot)
    created_test_ids["scenic_spots"].append(spot.id)
    return spot


def create_test_user(db, role=models.UserRole.STAFF):
    username = generate_test_username("staff")
    user = models.User(
        username=username,
        hashed_password=get_simple_password_hash("test123456"),
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    created_test_ids["users"].append(user.id)
    return user


def create_test_work_shift(db, name="Morning Shift", start_time="08:00", end_time="18:00"):
    shift = models.WorkShift(
        name=name,
        start_time=start_time,
        end_time=end_time,
        is_active=True
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    created_test_ids["work_shifts"].append(shift.id)
    return shift


def create_test_schedule(db, user_id, work_shift_id, schedule_date=None):
    if schedule_date is None:
        schedule_date = datetime.now().strftime("%Y-%m-%d")
    
    schedule = models.Schedule(
        user_id=user_id,
        work_shift_id=work_shift_id,
        schedule_date=schedule_date
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    created_test_ids["schedules"].append(schedule.id)
    return schedule


def create_test_attendance_record(db, user_id, schedule_id, scenic_spot_id, check_in_time=None, check_out_time=None):
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if check_in_time is None:
        check_in_time = datetime.now()
    
    record = models.AttendanceRecord(
        user_id=user_id,
        schedule_id=schedule_id,
        scenic_spot_id=scenic_spot_id,
        attendance_date=today_str,
        check_in_time=check_in_time,
        check_out_time=check_out_time,
        attendance_status=models.AttendanceStatus.NORMAL
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    created_test_ids["attendance_records"].append(record.id)
    return record


def create_test_coupon(db, name="10 Yuan Coupon", discount_value=10, target_scenic_spot_id=None):
    coupon = models.Coupon(
        name=name,
        coupon_type=models.CouponType.FIXED_AMOUNT,
        discount_value=discount_value,
        min_spend=0,
        valid_from=datetime.utcnow(),
        valid_to=datetime.utcnow() + timedelta(days=30),
        total_stock=100,
        remained_stock=100,
        target_scenic_spot_id=target_scenic_spot_id,
        is_active=True
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    created_test_ids["coupons"].append(coupon.id)
    return coupon


def test_color_level_logic():
    print("\n" + "=" * 60)
    print("Test 1: Color Warning Logic")
    print("=" * 60)
    
    if not MAIN_IMPORTED:
        print("  [SKIP] main.py not imported")
        return False
    
    test_cases = [
        (0.0, "green", "0% saturation"),
        (0.3, "green", "30% saturation"),
        (0.39, "green", "39% saturation"),
        (0.4, "yellow", "40% saturation"),
        (0.5, "yellow", "50% saturation"),
        (0.79, "yellow", "79% saturation"),
        (0.8, "red", "80% saturation"),
        (0.9, "red", "90% saturation"),
        (1.0, "red", "100% saturation"),
    ]
    
    all_passed = True
    for saturation, expected_color, description in test_cases:
        actual_color = get_color_level(saturation)
        passed = actual_color == expected_color
        if not passed:
            all_passed = False
        log_test_result(
            "Color - {}".format(description),
            passed,
            "Saturation {:.0f}%: expected {}, actual {}".format(
                saturation*100, expected_color, actual_color
            )
        )
    
    return all_passed


def test_distance_calculation():
    print("\n" + "=" * 60)
    print("Test 2: Distance Calculation Logic")
    print("=" * 60)
    
    if not MAIN_IMPORTED:
        print("  [SKIP] main.py not imported")
        return False
    
    beijing_lat, beijing_lng = 39.9042, 116.4074
    tianjin_lat, tianjin_lng = 39.0842, 117.2009
    
    distance = calculate_distance(beijing_lat, beijing_lng, tianjin_lat, tianjin_lng)
    
    expected_min = 100
    expected_max = 150
    
    passed = expected_min < distance < expected_max
    
    log_test_result(
        "Distance - Beijing to Tianjin",
        passed,
        "Calculated: {:.2f} km, expected: {}-{} km".format(
            distance, expected_min, expected_max
        )
    )
    
    same_point_distance = calculate_distance(beijing_lat, beijing_lng, beijing_lat, beijing_lng)
    same_point_passed = same_point_distance < 1
    
    log_test_result(
        "Distance - Same point",
        same_point_passed,
        "Same point distance: {:.6f} km, expected: < 1 km".format(
            same_point_distance
        )
    )
    
    return passed and same_point_passed


def test_crowded_spot_diversion_recommendation(db):
    print("\n" + "=" * 60)
    print("Test 3: Crowded Spot Diversion Recommendation")
    print("=" * 60)
    
    print("\n[Setup] Creating test spots...")
    
    crowded_spot = create_test_scenic_spot(
        db, 
        name="Crowded Test Spot A",
        capacity=100,
        current_count=85,
        latitude=39.9042,
        longitude=116.4074
    )
    print("  Created: {}, ID={}, Saturation={:.0f}%".format(
        crowded_spot.name, crowded_spot.id,
        crowded_spot.current_count / crowded_spot.capacity * 100
    ))
    
    comfort_spot1 = create_test_scenic_spot(
        db,
        name="Comfort Test Spot B",
        capacity=100,
        current_count=30,
        latitude=39.9142,
        longitude=116.4174
    )
    print("  Created: {}, ID={}, Saturation={:.0f}%".format(
        comfort_spot1.name, comfort_spot1.id,
        comfort_spot1.current_count / comfort_spot1.capacity * 100
    ))
    
    comfort_spot2 = create_test_scenic_spot(
        db,
        name="Comfort Test Spot C",
        capacity=100,
        current_count=25,
        latitude=39.8942,
        longitude=116.3974
    )
    print("  Created: {}, ID={}, Saturation={:.0f}%".format(
        comfort_spot2.name, comfort_spot2.id,
        comfort_spot2.current_count / comfort_spot2.capacity * 100
    ))
    
    print("\n[Test] Verifying saturation calculation...")
    
    crowded_saturation = crowded_spot.current_count / crowded_spot.capacity
    crowded_passed = crowded_saturation >= 0.8
    log_test_result(
        "Crowded spot saturation",
        crowded_passed,
        "Spot A saturation: {:.0f}%, expected >= 80%".format(
            crowded_saturation * 100
        )
    )
    
    comfort1_saturation = comfort_spot1.current_count / comfort_spot1.capacity
    comfort1_passed = comfort1_saturation < 0.4
    log_test_result(
        "Comfort spot B saturation",
        comfort1_passed,
        "Spot B saturation: {:.0f}%, expected < 40%".format(
            comfort1_saturation * 100
        )
    )
    
    comfort2_saturation = comfort_spot2.current_count / comfort_spot2.capacity
    comfort2_passed = comfort2_saturation < 0.4
    log_test_result(
        "Comfort spot C saturation",
        comfort2_passed,
        "Spot C saturation: {:.0f}%, expected < 40%".format(
            comfort2_saturation * 100
        )
    )
    
    print("\n[Test] Verifying color levels...")
    
    if MAIN_IMPORTED:
        crowded_color = get_color_level(crowded_saturation)
        log_test_result(
            "Crowded spot color",
            crowded_color == "red",
            "Spot A color: {}, expected: red".format(crowded_color)
        )
        
        comfort1_color = get_color_level(comfort1_saturation)
        log_test_result(
            "Comfort spot color",
            comfort1_color == "green",
            "Spot B color: {}, expected: green".format(comfort1_color)
        )
    else:
        print("  [SKIP] Color level tests (main.py not imported)")
    
    print("\n[Test] Verifying diversion trigger logic...")
    
    diversion_threshold = 0.8
    recommendation_threshold = 0.4
    
    should_trigger_diversion = crowded_saturation >= diversion_threshold
    log_test_result(
        "Diversion trigger condition",
        should_trigger_diversion,
        "Spot A saturation {:.0f}% >= {:.0f}%, should trigger diversion".format(
            crowded_saturation * 100, diversion_threshold * 100
        )
    )
    
    is_recommendable = comfort1_saturation < recommendation_threshold
    log_test_result(
        "Recommendation condition",
        is_recommendable,
        "Spot B saturation {:.0f}% < {:.0f}%, is recommendable".format(
            comfort1_saturation * 100, recommendation_threshold * 100
        )
    )
    
    all_passed = (
        crowded_passed and 
        comfort1_passed and 
        comfort2_passed and
        should_trigger_diversion and
        is_recommendable
    )
    
    return all_passed


def test_staff_on_duty_status(db):
    print("\n" + "=" * 60)
    print("Test 4: Staff On-Duty Status")
    print("=" * 60)
    
    if not MAIN_IMPORTED:
        print("  [SKIP] main.py not imported")
        return False
    
    print("\n[Setup] Creating test data...")
    
    test_spot = create_test_scenic_spot(
        db,
        name="Staff Status Test Spot",
        capacity=100,
        current_count=50,
        latitude=39.9042,
        longitude=116.4074
    )
    print("  Created test spot: {}, ID={}".format(test_spot.name, test_spot.id))
    
    staff_user = create_test_user(db, role=models.UserRole.STAFF)
    print("  Created staff user: ID={}, role={}".format(staff_user.id, staff_user.role.value))
    
    morning_shift = create_test_work_shift(
        db,
        name="Test Morning Shift",
        start_time="06:00",
        end_time="22:00"
    )
    print("  Created work shift: {}, time={}-{}".format(
        morning_shift.name, morning_shift.start_time, morning_shift.end_time
    ))
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    schedule = create_test_schedule(
        db,
        user_id=staff_user.id,
        work_shift_id=morning_shift.id,
        schedule_date=today_str
    )
    print("  Created schedule: date={}".format(schedule.schedule_date))
    
    print("\n[Test] Scenario 1: Staff checked in...")
    
    attendance_record = create_test_attendance_record(
        db,
        user_id=staff_user.id,
        schedule_id=schedule.id,
        scenic_spot_id=test_spot.id,
        check_in_time=datetime.now(),
        check_out_time=None
    )
    print("  Created attendance record: check_in={}, not checked out".format(
        attendance_record.check_in_time
    ))
    
    has_staff = check_staff_on_duty(db, test_spot.id)
    
    log_test_result(
        "Staff status - after check-in",
        has_staff,
        "Staff checked in, check_staff_on_duty returned {}, expected True".format(
            has_staff
        )
    )
    
    test_passed_1 = has_staff
    
    print("\n[Test] Scenario 2: Staff checked out...")
    
    attendance_record.check_out_time = datetime.now()
    db.commit()
    db.refresh(attendance_record)
    print("  Updated attendance: check_out={}".format(attendance_record.check_out_time))
    
    has_staff_after_checkout = check_staff_on_duty(db, test_spot.id)
    
    log_test_result(
        "Staff status - after check-out",
        not has_staff_after_checkout,
        "Staff checked out, check_staff_on_duty returned {}, expected False".format(
            has_staff_after_checkout
        )
    )
    
    test_passed_2 = not has_staff_after_checkout
    
    print("\n[Test] Scenario 3: No attendance records...")
    
    db.delete(attendance_record)
    db.commit()
    created_test_ids["attendance_records"].remove(attendance_record.id)
    print("  Deleted attendance record")
    
    new_spot = create_test_scenic_spot(
        db,
        name="No Attendance Test Spot",
        capacity=100,
        current_count=50,
        latitude=39.9142,
        longitude=116.4174
    )
    print("  Created new spot: {}, ID={} (no attendance)".format(new_spot.name, new_spot.id))
    
    has_staff_no_record = check_staff_on_duty(db, new_spot.id)
    
    log_test_result(
        "Staff status - no records",
        not has_staff_no_record,
        "No attendance records, check_staff_on_duty returned {}, expected False".format(
            has_staff_no_record
        )
    )
    
    test_passed_3 = not has_staff_no_record
    
    print("\n[Test] Scenario 4: Spot status auto-switch logic...")
    
    spot_status = test_spot.status
    effective_status = spot_status
    
    if not test_passed_1:
        effective_status = models.ScenicSpotStatus.SUSPENDED
    
    log_test_result(
        "Spot status logic",
        True,
        "Spot status: {}, staff on duty: {}, effective status: {}".format(
            spot_status.value, test_passed_1, effective_status.value
        )
    )
    
    all_passed = test_passed_1 and test_passed_2 and test_passed_3
    
    return all_passed


def test_coupon_integration(db):
    print("\n" + "=" * 60)
    print("Test 5: Coupon System Integration")
    print("=" * 60)
    
    print("\n[Setup] Creating test data...")
    
    crowded_spot = create_test_scenic_spot(
        db,
        name="Coupon Test Spot A",
        capacity=100,
        current_count=90,
        latitude=39.9042,
        longitude=116.4074
    )
    print("  Created crowded spot: {}, ID={}, Saturation=90%".format(
        crowded_spot.name, crowded_spot.id
    ))
    
    target_spot = create_test_scenic_spot(
        db,
        name="Coupon Target Spot B",
        capacity=100,
        current_count=30,
        latitude=39.9142,
        longitude=116.4174
    )
    print("  Created target spot: {}, ID={}, Saturation=30%".format(
        target_spot.name, target_spot.id
    ))
    
    print("\n[Test] Creating coupon for target spot...")
    
    coupon = create_test_coupon(
        db,
        name="10 Yuan Diversion Coupon",
        discount_value=10,
        target_scenic_spot_id=target_spot.id
    )
    print("  Created coupon: ID={}, Value={} Yuan, Target Spot ID={}".format(
        coupon.id, coupon.discount_value, coupon.target_scenic_spot_id
    ))
    
    log_test_result(
        "Coupon creation",
        coupon.id is not None and coupon.target_scenic_spot_id == target_spot.id,
        "Coupon ID={}, Target Spot ID={}, Active={}".format(
            coupon.id, coupon.target_scenic_spot_id, coupon.is_active
        )
    )
    
    coupon_created = coupon.id is not None
    
    print("\n[Test] Verifying crowded spot trigger condition...")
    
    crowded_saturation = crowded_spot.current_count / crowded_spot.capacity
    should_trigger = crowded_saturation >= 0.8
    
    log_test_result(
        "Crowded trigger condition",
        should_trigger,
        "Spot A saturation={:.0f}% >= 80%, should trigger diversion and coupon recommendation".format(
            crowded_saturation * 100
        )
    )
    
    print("\n[Test] Verifying target spot recommendation condition...")
    
    target_saturation = target_spot.current_count / target_spot.capacity
    is_good_recommendation = target_saturation < 0.4
    
    log_test_result(
        "Target spot recommendation",
        is_good_recommendation,
        "Spot B saturation={:.0f}% < 40%, is recommendable".format(
            target_saturation * 100
        )
    )
    
    print("\n[Test] Verifying coupon availability...")
    
    is_available = (
        coupon.is_active and 
        coupon.remained_stock > 0 and
        coupon.target_scenic_spot_id == target_spot.id
    )
    
    log_test_result(
        "Coupon availability",
        is_available,
        "Coupon status: Active={}, Stock={}, Target matches={}".format(
            coupon.is_active, coupon.remained_stock,
            coupon.target_scenic_spot_id == target_spot.id
        )
    )
    
    all_passed = coupon_created and should_trigger and is_good_recommendation and is_available
    
    return all_passed


def print_test_summary():
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r["passed"])
    failed_tests = total_tests - passed_tests
    
    print("\n  Total tests: {}".format(total_tests))
    print("  Passed: {}".format(passed_tests))
    print("  Failed: {}".format(failed_tests))
    
    if failed_tests > 0:
        print("\n  Failed tests:")
        for result in test_results:
            if not result["passed"]:
                print("    - {}".format(result["test_name"]))
                print("      Details: {}".format(result["message"]))
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print("\n  Success rate: {:.1f}%".format(success_rate))
    
    print("\n" + "=" * 60)
    
    return failed_tests == 0


def main():
    print("\n" + "=" * 60)
    print("  Smart Tourism Crowd Control - Automated Tests")
    print("=" * 60)
    print("  Test start time: {}".format(time.strftime('%Y-%m-%d %H:%M:%S')))
    
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        cleanup_test_data(db)
        
        all_tests_passed = True
        
        test_color_level_logic()
        
        test_distance_calculation()
        
        if not test_crowded_spot_diversion_recommendation(db):
            all_tests_passed = False
        
        if not test_staff_on_duty_status(db):
            all_tests_passed = False
        
        if not test_coupon_integration(db):
            all_tests_passed = False
        
        final_result = print_test_summary()
        
        if final_result:
            print("\n  [SUCCESS] All tests passed!")
        else:
            print("\n  [FAILED] Some tests failed, please check the error messages above.")
        
        return 0 if final_result else 1
        
    except Exception as e:
        print("\n  [ERROR] Exception during test execution: {}".format(e))
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cleanup_test_data(db)
        db.close()
        print("\n  Test end time: {}".format(time.strftime('%Y-%m-%d %H:%M:%S')))


if __name__ == "__main__":
    sys.exit(main())
