from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


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
