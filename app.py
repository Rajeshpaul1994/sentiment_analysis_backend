from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import jwt
import datetime
import os
import json
import redis
import requests as http_requests

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from sentiment import analyze_sentiment
from dotenv import load_dotenv
from database import engine, SessionLocal
import models
from sqlalchemy import text

# Ensure tables are created
models.Base.metadata.create_all(bind=engine)
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN queries_today INT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN last_query_date DATETIME;"))
except Exception:
    pass

app = Flask(__name__)
load_dotenv()

# --- Replace with real API ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = "super-secret-key-change-me-in-production"

REDIS_HOST = os.getenv("REDIS_HOST_URL")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

CORS(app, resources={r"/*": {"origins": [FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"]}}, supports_credentials=True)

# Database Session Context Helper
def get_db_session():
    return SessionLocal()

# Flask Decorator for Token Authentication
def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            
        if not token:
            return jsonify({'detail': 'Missing authentication token'}), 401
            
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            email = payload.get("email")
            if not email:
                return jsonify({'detail': 'Invalid auth credentials'}), 401
                
            db = get_db_session()
            user = db.query(models.User).filter(models.User.email == email).first()
            if not user:
                db.close()
                return jsonify({'detail': 'User not found'}), 401
                
            # Attach injectables
            kwargs['current_user'] = user
            kwargs['db'] = db
                
        except Exception:
            return jsonify({'detail': 'Invalid token'}), 401
            
        return f(*args, **kwargs)
    return decorator


@app.route("/auth/google", methods=["POST"])
def google_auth():
    try:
        data = request.get_json()
        token = data.get('token')
        
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=10
        )
        
        user_email = idinfo.get('email')
        user_name = idinfo.get('name')
        user_avatar = idinfo.get('picture')
        
        db = get_db_session()
        
        user = db.query(models.User).filter(models.User.email == user_email).first()
        if not user:
            user = models.User(
                email=user_email,
                name=user_name,
                avatar=user_avatar,
                last_login=datetime.datetime.utcnow()
            )
            db.add(user)
        else:
            user.name = user_name
            user.avatar = user_avatar
            user.last_login = datetime.datetime.utcnow()
            
        db.commit()
        db.refresh(user)
        
        payload = {
            "email": user_email,
            "name": user_name,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }
        
        app_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        
        return jsonify({
            "token": app_token,
            "user": {"email": user_email, "name": user_name, "avatar": user_avatar}
        }), 200
        
    except ValueError as e:
        return jsonify({'detail': f'Invalid Token: {str(e)}'}), 401
    finally:
        if 'db' in locals():
            db.close()


RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

def fetch_tweets(topic: str):
    url = "https://twitter-search-only.p.rapidapi.com/search.php"
    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    }
    params = {
        "query": topic,
        "search_type": "Top"
    }

    response = http_requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.text}")

    data = response.json()
    tweets = []

    for item in data.get("timeline", []):
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

    return tweets[:10]


@app.route("/tweets/sentiment", methods=["GET"])
@token_required
def tweet_sentiment(current_user, db):
    try:
        topic = request.args.get("topic")
        if not topic:
            return jsonify({'detail': 'Topic is required'}), 400
            
        today_date = datetime.datetime.utcnow().date()
        
        if current_user.last_query_date is None or current_user.last_query_date.date() != today_date:
            current_user.queries_today = 0
            current_user.last_query_date = datetime.datetime.utcnow()
            
        if current_user.queries_today >= 20:
            return jsonify({'detail': 'daily limit over'}), 429
            
        current_user.queries_today += 1
        db.commit()

        cache_key = f"sentiment:{topic.lower()}"
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            return jsonify(json.loads(cached_data))

        tweets = fetch_tweets(topic)
        
        for tweet in tweets:
            sentiment, score = analyze_sentiment(tweet["text"])
            tweet["sentiment"] = sentiment
            tweet["score"] = score

        response_data = {
            "topic": topic,
            "count": len(tweets),
            "data": tweets
        }
        
        redis_client.setex(cache_key, 180, json.dumps(response_data))

        return jsonify(response_data)
    finally:
        db.close()


if __name__ == "__main__":
    app.run(port=8000, debug=True)
