from fastapi import FastAPI, status, HTTPException, APIRouter, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from bson import ObjectId
from typing import List
from auth import get_password_hash, verify_password, create_access_token, get_current_user
from datetime import timedelta, datetime
import random 

from database import users_collection, products_collection
from models import UserCreate, Token, UserInDB, OTPVerify, ProductCreate, ProductUpdate, ProductInDB
from email_utils import send_otp_email

app = FastAPI(title="Task Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://kolaganireeha.github.io/quickCart/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def product_helper(product) -> dict:
    return {
        "id": str(product["_id"]),
        "title": product["title"],
        "description": product.get("description"),
        "price": float(product.get("price", 0.0)),
        "quantity": int(product.get("quantity", 1)),
        "image_url": product.get("image_url"),
    }

@app.post("/products", response_model=ProductInDB, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, current_user=Depends(get_current_user)):
    prod = jsonable_encoder(product)
    prod["price"] = float(prod.get("price", 0.0))
    prod["quantity"] = int(prod.get("quantity", 1))
    prod["owner_id"] = ObjectId(current_user["id"])
    result = await products_collection.insert_one(prod)
    created = await products_collection.find_one({"_id": result.inserted_id})
    return product_helper(created)

@app.get("/products", response_model=List[ProductInDB], status_code=status.HTTP_200_OK)
async def get_products(current_user=Depends(get_current_user)):
    products = []
    owner_oid = ObjectId(current_user["id"])
    cursor = products_collection.find({"owner_id": owner_oid})
    async for doc in cursor:
        products.append(product_helper(doc))
    return products

@app.get("/products/{product_id}", response_model=ProductInDB, status_code=status.HTTP_200_OK)
async def get_product(product_id: str, current_user=Depends(get_current_user)):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Id")
    owner_oid = ObjectId(current_user["id"])
    doc = await products_collection.find_one({"_id": ObjectId(product_id), "owner_id": owner_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Product Not Found")
    return product_helper(doc)

@app.put("/products/{product_id}", response_model=ProductInDB)
async def update_product(product_id: str, product: ProductUpdate, current_user=Depends(get_current_user)):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    update_data = {k: v for k, v in product.dict().items() if v is not None}
    if "price" in update_data:
        update_data["price"] = float(update_data["price"])
    if "quantity" in update_data:
        update_data["quantity"] = int(update_data["quantity"])
    owner_oid = ObjectId(current_user["id"])
    if update_data:
        result = await products_collection.update_one(
            {"_id": ObjectId(product_id), "owner_id": owner_oid},
            {"$set": update_data},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product Not Found")
    doc = await products_collection.find_one({"_id": ObjectId(product_id), "owner_id": owner_oid})
    return product_helper(doc)

@app.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user=Depends(get_current_user)):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    owner_oid = ObjectId(current_user["id"])
    result = await products_collection.delete_one({"_id": ObjectId(product_id), "owner_id": owner_oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product Not Found")
    return {"status": "Deleted"}

#----------------------------------------------------------------------------------------

auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.post("/register")
async def register(user: UserCreate):
    try:
        email = user.email.strip().lower()
        existing = await users_collection.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        if user.password is None or len(user.password.encode("utf-8")) > 4096:
            raise HTTPException(status_code=400, detail="Password too long")

        hashed = get_password_hash(user.password)

        otp = f"{random.randint(100000, 999999)}"
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        doc = {
            "email": email,
            "hashed_password": hashed,
            "is_verified": False,
            "otp_code": otp,
            "otp_expires_at": expires_at,
        }

        await users_collection.insert_one(doc)
        await send_otp_email(email, otp)
        return {"message": "OTP sent to your email. Please verify to activate your account."}

    except HTTPException:
        raise
    except Exception as exc:
        import traceback, sys
        print("Register failed:", exc, file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error during registration")
    
@auth_router.post("/verify-otp")
async def verify_otp(payload: OTPVerify):
    email = payload.email.strip().lower()
    otp = payload.otp.strip()

    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if user.get("is_verified"):
        return {"message": "Email already verified"}

    stored_otp = user.get("otp_code")
    expires_at = user.get("otp_expires_at")

    if not stored_otp or not expires_at:
        raise HTTPException(status_code=400, detail="No OTP pending, please register again")

    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=400, detail="OTP expired, please register again")

    if stored_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    await users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"is_verified": True},
            "$unset": {"otp_code": "", "otp_expires_at": ""},
        },
    )

    return {"message": "Email verified successfully! You can now log in."}


@auth_router.post("/token", response_model=Token)
async def login_for_token(form_data: dict = Body(...)):
    email = form_data.get("email")
    password = form_data.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    user = await users_collection.find_one({"email": email.lower()})
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect credentials")

    if not user.get("is_verified", False):
        raise HTTPException(status_code=403, detail="Email not verified")

    if not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect credentials")

    access_token = create_access_token({"sub": str(user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}


app.include_router(auth_router)