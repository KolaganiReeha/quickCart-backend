from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Optional
from datetime import date

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserInDB(BaseModel):
    id: str
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class User(BaseModel):
    id: Optional[str]
    email: EmailStr
    password: str
    is_verified: bool = False
    otp_code: Optional[str] = None

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class ProductCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(0.0, ge=0)
    quantity: Optional[int] = Field(1, ge=0)
    image_url: Optional[HttpUrl] = None

class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None
    image_url: Optional[HttpUrl] = None

class ProductInDB(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = 0.0
    quantity: Optional[int] = 1
    image_url: Optional[HttpUrl] = None