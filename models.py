import uuid
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


class UserRole(str, Enum):
    TOURIST = "TOURIST"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class MemberLevel(str, Enum):
    NORMAL = "普通"
    SILVER = "白银"
    GOLD = "黄金"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"


class ComplaintStatus(str, Enum):
    PENDING = "待处理"
    PROCESSING = "处理中"
    RESOLVED = "已解决"


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
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("TicketOrder", back_populates="user")
    point_logs = relationship("PointLog", back_populates="user")


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

    user = relationship("User", back_populates="orders")
    scenic_spot = relationship("ScenicSpot")


class Tourist(Base):
    __tablename__ = "tourists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tickets = relationship("Ticket", back_populates="tourist")


class ScenicSpot(Base):
    __tablename__ = "scenic_spots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    location = Column(String(200))
    rating = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    total_inventory = Column(Integer, default=100)
    remained_inventory = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tickets = relationship("Ticket", back_populates="scenic_spot")


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
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class PointLog(Base):
    __tablename__ = "point_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    points_change = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="point_logs")


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    face_value = Column(Integer, nullable=False)
    points_required = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserCoupon(Base):
    __tablename__ = "user_coupons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False)
    is_used = Column(Boolean, default=False)
    obtained_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)

    coupon = relationship("Coupon")
