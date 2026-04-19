from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TicketStatus(str, Enum):
    valid = "valid"
    used = "used"
    expired = "expired"
    cancelled = "cancelled"


class ScenicSpotBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="景点名称")
    description: Optional[str] = Field(None, max_length=500, description="景点描述")
    location: Optional[str] = Field(None, max_length=200, description="景点位置")
    rating: Optional[float] = Field(None, ge=0, le=5, description="评分")
    image_url: Optional[str] = Field(None, max_length=200, description="图片URL")
    total_inventory: Optional[int] = Field(100, ge=0, description="总库存")
    remained_inventory: Optional[int] = Field(100, ge=0, description="剩余库存")


class ScenicSpotCreate(ScenicSpotBase):
    pass


class ScenicSpotUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    rating: Optional[float] = Field(None, ge=0, le=5)
    image_url: Optional[str] = Field(None, max_length=200)
    total_inventory: Optional[int] = Field(None, ge=0)
    remained_inventory: Optional[int] = Field(None, ge=0)


class ScenicSpotResponse(ScenicSpotBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ScenicSpotInventoryAlert(BaseModel):
    id: int
    name: str
    total_inventory: int
    remained_inventory: int
    inventory_percentage: float
    is_low_inventory: bool = False

    class Config:
        orm_mode = True


class TouristBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="游客姓名")
    id_card: str = Field(..., min_length=18, max_length=18, description="身份证号")
    phone: Optional[str] = Field(None, max_length=15, description="手机号码")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")


class TouristCreate(TouristBase):
    pass


class TouristUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    id_card: Optional[str] = Field(None, min_length=18, max_length=18)
    phone: Optional[str] = Field(None, max_length=15)
    email: Optional[str] = Field(None, max_length=100)


class TouristResponse(TouristBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TicketBase(BaseModel):
    scenic_spot_id: int = Field(..., description="景点ID")
    tourist_id: int = Field(..., description="游客ID")
    ticket_type: str = Field(..., max_length=50, description="门票类型")
    price: float = Field(..., gt=0, description="价格")
    valid_date: Optional[datetime] = Field(None, description="有效日期")
    status: TicketStatus = Field(default=TicketStatus.valid, description="状态")


class TicketCreate(TicketBase):
    pass


class TicketUpdate(BaseModel):
    scenic_spot_id: Optional[int] = Field(None)
    tourist_id: Optional[int] = Field(None)
    ticket_type: Optional[str] = Field(None, max_length=50)
    price: Optional[float] = Field(None, gt=0)
    valid_date: Optional[datetime] = Field(None)
    status: Optional[TicketStatus] = Field(None)


class TicketResponse(TicketBase):
    id: int
    purchase_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ScenicSpotWithTickets(ScenicSpotResponse):
    tickets: List[TicketResponse] = []


class TouristWithTickets(TouristResponse):
    tickets: List[TicketResponse] = []
