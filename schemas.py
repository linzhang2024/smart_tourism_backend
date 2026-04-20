from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


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
