# Twitter Sentiment Analysis Backend (EchoScan)

The backbone architecture for real-time social media pulse detection. This backend connects natively via Google OAuth 2.0, proxies authenticated clients dynamically through an aggressive Redis Cache layer, leverages strict JWT rate-limit boundaries linked to a live MySQL database, and processes semantic meaning instantaneously using NLTK compound mapping algorithms.

Highly flexible, this architecture supports two distinct running states: blazing-fast asynchronous capability via **FastAPI** (`main.py`) or purely synchronous classical routing via **Flask** (`app.py`).

## 🛠 Technology Stack

### Core Routing Engines
- **FastAPI**: Asynchronous edge-speed dependency controller (`main.py`)
- **Flask**: Secure synchronous WSGI application routing (`app.py`)

### Processing & Logic
- **NLTK (Vader Lexicon)**: Natural Language Processing engine mapping complex sentiment compound scores mathematically.
- **Redis (Redis-py / asyncio_redis)**: In-memory dynamic caching payload mapping holding API responses exactly 3 minutes.
- **SQLAlchemy & PyMySQL**: Object-Relational Mapping tracking user daily quotas directly onto AWS RDS formats.

### Security
- **Google Auth (`google-auth`)**: Validating structural payload hashes returning from client postMessage structures.
- **PyJWT**: Wrapping stateless session logic tightly enforcing the 20 limits/day API quotas globally.
- **Flask-CORS / FastAPI CORSMiddleware**: Dynamic origin tracking restricting DOM elements automatically via `.env` arrays.

---

## 🚀 Environment Setup (`.env`)
Before running either environment, make sure your `.env` is perfectly structured in the root folder alongside the files:
```env
# Database Credentials
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_url
DB_NAME=your_schema
DB_PORT=3306

# Target App Connection
FRONTEND_URL=https://tweetsanalysis.techgreat.in

# Provider APIs
GOOGLE_CLIENT_ID=your_google_cloud_client_id
RAPIDAPI_HOST=twitter-search-only.p.rapidapi.com
RAPIDAPI_KEY=your_rapidapi_token

# Redis Edge Connections
REDIS_HOST_URL=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=optional_redis_password
```

---

## ⚡ Option A: How to Run using Fastest Async (FastAPI)

FastAPI utilizes the hyper-fast `uvicorn` engine dynamically streaming NLTK returns and pulling `asyncio` from Redis seamlessly. It is the core original configuration built for scaling immediately.

**1. Install FastAPI Requirements**
```bash
pip install -r requirements.txt
```

**2. Start the Uvicorn Server**
```bash
uvicorn main:app --reload
```
*The endpoint will boot immediately traversing port `:8000`. It will dynamically render its own structural docs via `http://localhost:8000/docs`.*

---

## 🐍 Option B: How to Run using Classic Sync (Flask)

The Flask implementation handles logic completely sequentially avoiding loop handlers structurally executing everything synchronously down the procedural track inside `app.py`.

**1. Install Flask Requirements**
```bash
pip install -r requirements_flask.txt
```

**2. Start the WSGI Development Server**
```bash
python app.py
```
*The Flask wrapper automatically launches an active debug-ready server sitting natively on `http://localhost:8000` executing the identical logical pipelines securely mapped by the custom `@token_required` router proxy.*
