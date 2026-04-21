from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    TOURIST = "TOURIST"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"


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
