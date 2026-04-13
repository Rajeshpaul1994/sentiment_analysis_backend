from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
import datetime
import httpx, os, json
import redis.asyncio as redis_async
from sentiment import analyze_sentiment
from dotenv import load_dotenv
from database import engine, get_db
import models

# Ensure tables are created
models.Base.metadata.create_all(bind=engine)
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN queries_today INT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN last_query_date DATETIME;"))
except Exception:
    pass

app = FastAPI()

load_dotenv()

# --- Replace with real API ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = "super-secret-key-change-me-in-production"

REDIS_HOST = os.getenv("REDIS_HOST_URL")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

redis_client = redis_async.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],# "http://localhost:5173", "http://127.0.0.1:5173"], # Allows prod and local origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        email = payload.get("email")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid auth credentials")
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

class AuthRequest(BaseModel):
    token: str

@app.post("/auth/google")
async def google_auth(request: AuthRequest, db: Session = Depends(get_db)):
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            request.token, requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=10
        )
        
        # User details from Google
        user_email = idinfo.get('email')
        user_name = idinfo.get('name')
        user_avatar = idinfo.get('picture')
        
        # Check if user exists in the database
        user = db.query(models.User).filter(models.User.email == user_email).first()
        if not user:
            # Create new user
            user = models.User(
                email=user_email,
                name=user_name,
                avatar=user_avatar,
                last_login=datetime.datetime.utcnow()
            )
            db.add(user)
        else:
            # Update user info and last login
            user.name = user_name
            user.avatar = user_avatar
            user.last_login = datetime.datetime.utcnow()
            
        db.commit()
        db.refresh(user)
        
        # Create an app session token (JWT)
        payload = {
            "email": user_email,
            "name": user_name,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }
        
        app_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        
        return {
            "token": app_token,
            "user": {"email": user_email, "name": user_name, "avatar": user_avatar}
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Token: {str(e)}")

# --- Replace with real API ---
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")


async def fetch_tweets(topic: str):
    url = "https://twitter-search-only.p.rapidapi.com/search.php"

    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    params = {
        "query": topic,
        "search_type": "Top"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.text}")

    data = response.json()

    # ⚠️ IMPORTANT: inspect actual response structure
    # adjust parsing accordingly

    tweets = []

    for item in data.get("timeline", []):  # may vary!
        text = item.get("text")
        tweet_id = item.get("tweet_id")
        author = item.get("user_info", {}).get("name")
        avatar = item.get("user_info", {}).get("avatar")
        if text:
            tweets.append({
                "tweet_id": tweet_id,
                "author": author,
                "avatar": avatar,
                "text": text
            })

    return tweets[:10]  # limit to 10



@app.get("/tweets/sentiment")
async def tweet_sentiment(topic: str = Query(...), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    today_date = datetime.datetime.utcnow().date()
    
    # Rate limit check logic
    if user.last_query_date is None or user.last_query_date.date() != today_date:
        user.queries_today = 0
        user.last_query_date = datetime.datetime.utcnow()
        
    if user.queries_today >= 20:
        raise HTTPException(status_code=429, detail="daily limit over")
        
    # Commit usage before heavy operations
    user.queries_today += 1
    db.commit()

    # Cache Check
    cache_key = f"sentiment:{topic.lower()}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    # Process
    tweets = await fetch_tweets(topic)
    
    for tweet in tweets:
        sentiment, score = analyze_sentiment(tweet["text"])
        tweet["sentiment"] = sentiment
        tweet["score"] = score

    response_data = {
        "topic": topic,
        "count": len(tweets),
        "data": tweets
    }
    
    # Save to Cache for 3 minutes (180 seconds)
    await redis_client.setex(cache_key, 180, json.dumps(response_data))

    return response_data