from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class ScenicSpot(Base):
    __tablename__ = "scenic_spots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    description = Column(String(500))
    location = Column(String(200))
    rating = Column(Float)
    image_url = Column(String(200))
    total_inventory = Column(Integer, default=100)
    remained_inventory = Column(Integer, default=100)
    alert_threshold = Column(Float, default=10.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tickets = relationship("Ticket", back_populates="scenic_spot")


class Tourist(Base):
    __tablename__ = "tourists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    id_card = Column(String(18), unique=True, index=True)
    phone = Column(String(15))
    email = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tickets = relationship("Ticket", back_populates="tourist")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    scenic_spot_id = Column(Integer, ForeignKey("scenic_spots.id"))
    tourist_id = Column(Integer, ForeignKey("tourists.id"))
    ticket_type = Column(String(50))
    price = Column(Float)
    purchase_date = Column(DateTime, default=datetime.utcnow)
    valid_date = Column(DateTime)
    status = Column(String(20), default="valid")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenic_spot = relationship("ScenicSpot", back_populates="tickets")
    tourist = relationship("Tourist", back_populates="tickets")
