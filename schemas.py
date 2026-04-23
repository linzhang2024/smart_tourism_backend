from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


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


class ComplaintStatus(str, Enum):
    PENDING = "待处理"
    PROCESSING = "处理中"
    RESOLVED = "已解决"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    role: UserRole = Field(default=UserRole.TOURIST, description="用户角色")


class UserLogin(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    phone: Optional[str]
    is_active: bool
    total_points: int = 0
    member_level: MemberLevel = MemberLevel.NORMAL
    department_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="部门名称")
    description: Optional[str] = Field(None, max_length=500, description="部门描述")


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class Department(DepartmentBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None


# Tourist schemas
class TouristBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="游客姓名")
    email: str = Field(..., description="游客邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="游客电话")


class TouristCreate(TouristBase):
    pass


class TouristUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)


class Tourist(TouristBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ScenicSpot schemas
class ScenicSpotBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="景点名称")
    description: Optional[str] = Field(None, description="景点描述")
    location: Optional[str] = Field(None, max_length=200, description="景点位置")
    rating: Optional[float] = Field(0.0, ge=0, le=5, description="景点评分")
    price: Optional[float] = Field(0.0, ge=0, description="景点门票价格")
    total_inventory: Optional[int] = Field(100, ge=0, description="总库存")
    remained_inventory: Optional[int] = Field(100, ge=0, description="剩余库存")


class ScenicSpotCreate(ScenicSpotBase):
    pass


class ScenicSpotUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    rating: Optional[float] = Field(None, ge=0, le=5)
    price: Optional[float] = Field(None, ge=0)
    total_inventory: Optional[int] = Field(None, ge=0)
    remained_inventory: Optional[int] = Field(None, ge=0)


class ScenicSpot(ScenicSpotBase):
    id: int
    created_at: datetime
    status_note: Optional[str] = None

    class Config:
        from_attributes = True


# Ticket schemas
class TicketBase(BaseModel):
    tourist_id: int = Field(..., description="游客ID")
    scenic_spot_id: int = Field(..., description="景点ID")
    quantity: int = Field(1, ge=1, description="门票数量")


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=20)


class Ticket(TicketBase):
    id: int
    total_price: float
    purchase_date: datetime
    status: str

    class Config:
        from_attributes = True


# Response schemas with relationships
class TouristWithTickets(Tourist):
    tickets: List[Ticket] = []


class ScenicSpotWithTickets(ScenicSpot):
    tickets: List[Ticket] = []
    status_note: Optional[str] = None


class TicketWithDetails(Ticket):
    tourist: Tourist
    scenic_spot: ScenicSpot


class ScenicSpotInventoryAlert(BaseModel):
    id: int
    name: str
    total_inventory: int
    remained_inventory: int
    inventory_ratio: float
    is_low_inventory: bool

    class Config:
        from_attributes = True


# TouristFlow schemas
class TouristFlowBase(BaseModel):
    scenic_spot_id: int = Field(..., description="景点ID")
    entry_count: int = Field(..., ge=0, description="入园人数")


class TouristFlowCreate(TouristFlowBase):
    pass


class TouristFlow(TouristFlowBase):
    id: int
    record_time: datetime

    class Config:
        from_attributes = True


class TouristFlowAnalytics(BaseModel):
    scenic_spot_id: int
    scenic_spot_name: str
    recent_records: List[TouristFlow]
    average_entry_count: float
    congestion_level: str
    trend: str

    class Config:
        from_attributes = True


class TicketOrderCreate(BaseModel):
    user_id: int = Field(..., description="用户ID")
    scenic_spot_id: int = Field(..., description="景点ID")
    quantity: int = Field(1, ge=1, description="门票数量")


class TicketOrder(BaseModel):
    id: int
    order_no: str
    user_id: int
    scenic_spot_id: int
    quantity: int
    total_price: float
    status: OrderStatus
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TicketOrderWithDetails(TicketOrder):
    user: UserResponse
    scenic_spot: ScenicSpot


class TicketSuccessBrief(BaseModel):
    order_no: str
    tourist_name: str
    scenic_spot_name: str
    quantity: int
    paid_at: Optional[datetime] = None
    time_ago: str = ""

    class Config:
        from_attributes = True


class ComplaintCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="投诉标题")
    content: str = Field(..., min_length=1, description="投诉内容")


class ComplaintUpdate(BaseModel):
    reply: Optional[str] = Field(None, description="回复内容")
    status: Optional[ComplaintStatus] = Field(None, description="状态")


class Complaint(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    status: ComplaintStatus
    reply: Optional[str] = None
    is_points_rewarded: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ComplaintWithUser(Complaint):
    user: Optional[UserResponse] = None


class PointLog(BaseModel):
    id: int
    user_id: int
    points_change: int
    reason: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_expired: bool = False

    class Config:
        from_attributes = True


class MemberProfileResponse(BaseModel):
    user_id: int
    username: str
    member_level: MemberLevel
    total_points: int
    expiring_points_30d: int = 0
    expiring_points_7d: int = 0
    recent_logs: List[PointLog]

    class Config:
        from_attributes = True


class CouponBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="优惠券名称")
    face_value: int = Field(..., ge=1, description="面值（元）")
    points_required: int = Field(..., ge=1, description="所需积分")


class CouponCreate(CouponBase):
    pass


class Coupon(CouponBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCoupon(BaseModel):
    id: int
    user_id: int
    coupon_id: int
    redemption_code: str
    is_used: bool
    obtained_at: datetime
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    used_order_id: Optional[int] = None
    coupon: Optional[Coupon] = None

    class Config:
        from_attributes = True


class ExchangeRequest(BaseModel):
    coupon_id: int = Field(..., description="优惠券ID")


class ExchangeResponse(BaseModel):
    success: bool
    message: str
    user_coupon: Optional[UserCoupon] = None
    remaining_points: int = 0


class TicketOrderCreate(BaseModel):
    user_id: int = Field(..., description="用户ID")
    scenic_spot_id: int = Field(..., description="景点ID")
    quantity: int = Field(1, ge=1, description="门票数量")
    user_coupon_id: Optional[int] = Field(None, description="用户优惠券ID（使用优惠券时提供）")


class DistributorCreate(BaseModel):
    user_id: int = Field(..., description="用户ID")
    commission_rate: Optional[float] = Field(0.05, ge=0, le=1, description="佣金比例（默认5%）")


class DistributorUpdate(BaseModel):
    commission_rate: Optional[float] = Field(None, ge=0, le=1, description="佣金比例")
    is_active: Optional[bool] = Field(None, description="是否激活")


class Distributor(BaseModel):
    id: int
    user_id: int
    distributor_code: str
    commission_rate: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DistributorWithDetails(Distributor):
    user: Optional[UserResponse] = None


class TicketOrderWithDistributor(TicketOrder):
    distributor_id: Optional[int] = None
    distributor_code: Optional[str] = None
    commission_amount: Optional[float] = None


class DistributorEarnings(BaseModel):
    distributor_id: int
    distributor_code: str
    total_orders: int
    total_revenue: float
    total_commission: float
    commission_rate: float

    class Config:
        from_attributes = True


class DistributorOrderListItem(TicketOrder):
    distributor_id: Optional[int] = None
    commission_amount: Optional[float] = None
    scenic_spot_name: Optional[str] = None
    is_settled: bool = False


class DistributorFinanceReport(BaseModel):
    distributor_id: int
    distributor_code: str
    commission_rate: float
    
    total_orders: int
    total_revenue: float
    total_commission: float
    
    settled_orders: int
    settled_commission: float
    
    pending_orders: int
    pending_commission: float
    
    today_orders: int
    today_revenue: float
    today_commission: float

    class Config:
        from_attributes = True


class FinanceOrderItem(BaseModel):
    order_no: str
    scenic_spot_name: str
    order_date: Optional[str] = None
    quantity: int
    total_price: float
    commission_amount: float
    is_settled: bool

    class Config:
        from_attributes = True


class WorkShiftBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="班次名称")
    start_time: str = Field(..., description="开始时间，格式: HH:MM")
    end_time: str = Field(..., description="结束时间，格式: HH:MM")
    max_staff: Optional[int] = Field(None, ge=1, description="班次最大容量，None 表示无限制")


class WorkShiftCreate(WorkShiftBase):
    pass


class WorkShiftUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    max_staff: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class WorkShift(WorkShiftBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleBase(BaseModel):
    user_id: int = Field(..., description="员工ID")
    work_shift_id: int = Field(..., description="班次ID")
    schedule_date: str = Field(..., description="排班日期，格式: YYYY-MM-DD")


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    work_shift_id: Optional[int] = None


class Schedule(ScheduleBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleWithDetails(Schedule):
    user: Optional[UserResponse] = None
    work_shift: Optional[WorkShift] = None


class BatchScheduleItem(BaseModel):
    user_id: int = Field(..., description="员工ID")


class BatchScheduleCreate(BaseModel):
    user_ids: List[int] = Field(..., description="员工ID列表")
    work_shift_id: int = Field(..., description="班次ID")
    start_date: str = Field(..., description="开始日期，格式: YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期，格式: YYYY-MM-DD")
    exclude_weekends: Optional[bool] = Field(False, description="是否排除周末")


class BatchScheduleResponse(BaseModel):
    success: bool
    message: str
    created_count: int = 0
    conflict_dates: List[str] = []


class ScheduleConflictCheck(BaseModel):
    user_id: int
    schedule_date: str
    has_conflict: bool
    existing_schedule: Optional[ScheduleWithDetails] = None
