import uuid
import random
import string
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timedelta, timezone
from enum import Enum


def get_utc8_now():
    utc_now = datetime.now(timezone.utc)
    utc8_offset = timedelta(hours=8)
    utc8_time = utc_now.astimezone(timezone(utc8_offset))
    return utc8_time.replace(tzinfo=None)


def get_default_expires_at():
    return datetime.utcnow() + timedelta(days=365)


def generate_redemption_code(length: int = 12) -> str:
    prefix = "CP"
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=length - 2))
    return prefix + random_part


class UserRole(str, Enum):
    TOURIST = "TOURIST"
    STAFF = "STAFF"
    DEPT_ADMIN = "DEPT_ADMIN"
    ADMIN = "ADMIN"


class MemberLevel(str, Enum):
    NORMAL = "普通"
    SILVER = "白银"
    GOLD = "黄金"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class ComplaintStatus(str, Enum):
    PENDING = "待处理"
    PROCESSING = "处理中"
    RESOLVED = "已解决"


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="department")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.TOURIST, nullable=False)
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    total_points = Column(Integer, default=0)
    member_level = Column(SQLEnum(MemberLevel), default=MemberLevel.NORMAL)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("TicketOrder", back_populates="user")
    point_logs = relationship("PointLog", back_populates="user")
    department = relationship("Department", back_populates="users")


class TicketOrder(Base):
    __tablename__ = "ticket_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"), nullable=False)
    quantity = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    commission_amount = Column(Float, default=0.0, nullable=True)
    is_settled = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="orders")
    scenic_spot = relationship("ScenicSpot")
    distributor = relationship("Distributor")


class Tourist(Base):
    __tablename__ = "tourists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tickets = relationship("Ticket", back_populates="tourist")


class ScenicSpotStatus(str, Enum):
    ACTIVE = "正常开放"
    SUSPENDED = "暂停服务"
    MAINTENANCE = "维护中"


class ScenicSpot(Base):
    __tablename__ = "scenic_spots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    location = Column(String(200))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geofence_radius = Column(Float, nullable=True)
    rating = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    total_inventory = Column(Integer, default=100)
    remained_inventory = Column(Integer, default=100)
    capacity = Column(Integer, default=100)
    current_count = Column(Integer, default=0)
    status = Column(SQLEnum(ScenicSpotStatus), default=ScenicSpotStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tickets = relationship("Ticket", back_populates="scenic_spot")
    attendance_records = relationship("AttendanceRecord", back_populates="scenic_spot")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    tourist_id = Column(Integer, ForeignKey("tourists.id"), nullable=False)
    scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"), nullable=False)
    quantity = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    purchase_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="active")
    
    tourist = relationship("Tourist", back_populates="tickets")
    scenic_spot = relationship("ScenicSpot", back_populates="tickets")


class TouristFlow(Base):
    __tablename__ = "tourist_flows"

    id = Column(Integer, primary_key=True, index=True)
    scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"), nullable=False)
    entry_count = Column(Integer, nullable=False)
    record_time = Column(DateTime, default=get_utc8_now)

    scenic_spot = relationship("ScenicSpot")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(SQLEnum(ComplaintStatus), default=ComplaintStatus.PENDING, nullable=False)
    reply = Column(Text, nullable=True)
    is_points_rewarded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class PointLog(Base):
    __tablename__ = "point_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    points_change = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=get_default_expires_at)
    is_expired = Column(Boolean, default=False)

    user = relationship("User", back_populates="point_logs")


class CouponType(str, Enum):
    FIXED_AMOUNT = "满减券"
    DISCOUNT = "折扣券"


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    coupon_type = Column(SQLEnum(CouponType), default=CouponType.FIXED_AMOUNT, nullable=False)
    discount_value = Column(Float, nullable=False)
    discount_percentage = Column(Float, nullable=True)
    min_spend = Column(Float, default=0.0, nullable=False)
    max_discount = Column(Float, nullable=True)
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=False, default=get_default_expires_at)
    total_stock = Column(Integer, default=100, nullable=False)
    remained_stock = Column(Integer, default=100, nullable=False)
    points_required = Column(Integer, default=0, nullable=False)
    target_member_level = Column(SQLEnum(MemberLevel), nullable=True)
    target_scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    scenic_spot = relationship("ScenicSpot")


class UserCoupon(Base):
    __tablename__ = "user_coupons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False)
    redemption_code = Column(String(20), unique=True, nullable=False, default=generate_redemption_code)
    is_used = Column(Boolean, default=False)
    obtained_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=get_default_expires_at)
    used_at = Column(DateTime, nullable=True)
    used_order_id = Column(Integer, ForeignKey("ticket_orders.id"), nullable=True)

    coupon = relationship("Coupon")


class TimeLimitedCommission(Base):
    __tablename__ = "time_limited_commissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"), nullable=True)
    commission_rate = Column(Float, nullable=False)
    valid_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    distributor = relationship("Distributor")
    scenic_spot = relationship("ScenicSpot")


def generate_distributor_code() -> str:
    prefix = "DIST"
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=6))
    return prefix + random_part


class Distributor(Base):
    __tablename__ = "distributors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    distributor_code = Column(String(20), unique=True, nullable=False, default=generate_distributor_code)
    commission_rate = Column(Float, default=0.05, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    payment_account_encrypted = Column(Text, nullable=True)
    payment_account_type = Column(String(20), nullable=True)

    user = relationship("User")


class WorkShift(Base):
    __tablename__ = "work_shifts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    max_staff = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    schedules = relationship("Schedule", back_populates="work_shift")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    work_shift_id = Column(Integer, ForeignKey("work_shifts.id"), nullable=False)
    schedule_date = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    work_shift = relationship("WorkShift", back_populates="schedules")


class AttendanceLocationStatus(str, Enum):
    NORMAL = "NORMAL"
    OUT_OF_RANGE = "OUT_OF_RANGE"


class AttendanceStatus(str, Enum):
    NORMAL = "NORMAL"
    LATE = "LATE"
    EARLY_LEAVE = "EARLY_LEAVE"
    ABSENT = "ABSENT"
    MANUAL_APPROVED = "MANUAL_APPROVED"


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=True)
    scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"), nullable=True)
    
    attendance_date = Column(String(10), nullable=False)
    
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    
    check_in_latitude = Column(Float, nullable=True)
    check_in_longitude = Column(Float, nullable=True)
    check_out_latitude = Column(Float, nullable=True)
    check_out_longitude = Column(Float, nullable=True)
    
    check_in_location_status = Column(SQLEnum(AttendanceLocationStatus), default=AttendanceLocationStatus.NORMAL)
    check_out_location_status = Column(SQLEnum(AttendanceLocationStatus), default=AttendanceLocationStatus.NORMAL)
    
    attendance_status = Column(SQLEnum(AttendanceStatus), default=AttendanceStatus.ABSENT)
    
    is_approved = Column(Boolean, default=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    remark = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    schedule = relationship("Schedule")
    scenic_spot = relationship("ScenicSpot")
    approver = relationship("User", foreign_keys=[approved_by])


class TransactionType(str, Enum):
    INCOME = "收入"
    DISTRIBUTION_EXPENSE = "分销支出"
    REFUND = "退款"


class FinancialLog(Base):
    __tablename__ = "financial_logs"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    order_no = Column(String(36), index=True, nullable=True)
    amount = Column(Float, nullable=False)
    transaction_time = Column(DateTime, default=datetime.utcnow, index=True)
    summary = Column(String(500), nullable=True)
    related_distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    distributor = relationship("Distributor")


class AuditLogAction(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    OTHER = "OTHER"


class AuditLogModule(str, Enum):
    AUTH = "认证管理"
    USER = "用户管理"
    SCENIC_SPOT = "景点管理"
    TICKET = "门票管理"
    ORDER = "订单管理"
    FINANCE = "财务管理"
    DISTRIBUTION = "分销管理"
    ATTENDANCE = "考勤管理"
    SCHEDULE = "排班管理"
    INVENTORY = "库存管理"
    COMPLAINT = "投诉管理"
    ANALYTICS = "数据分析"
    SYSTEM = "系统管理"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=True)
    
    module = Column(SQLEnum(AuditLogModule), nullable=False, index=True)
    action = Column(SQLEnum(AuditLogAction), nullable=False, index=True)
    
    target_id = Column(Integer, nullable=True)
    target_type = Column(String(100), nullable=True)
    
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship("User", foreign_keys=[user_id])
