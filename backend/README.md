# RUDRX1 Backend API

Production FastAPI backend for the RUDRX1 AI Platform.

## Architecture

```
User → Frontend (rudrxai.cloud) → Backend API (api.rudrxai.cloud) → Groq API
                                         ↓
                                    Supabase (Auth + DB)
                                         ↓
                                    Razorpay (Payments)
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all values
```

### 3. Run the database schema

Go to your Supabase SQL Editor and run `../supabase-schema.sql`

### 4. Start the server

```bash
# Development
uvicorn main:app --reload --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. Deploy with Docker

```bash
docker build -t rudrx1-api .
docker run -p 8000:8000 --env-file .env rudrx1-api
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/models` | List available models |
| POST | `/v1/chat/completions` | Chat completion (routes to Groq) |
| GET | `/v1/keys` | List API keys |
| POST | `/v1/keys` | Create API key |
| DELETE | `/v1/keys/{id}` | Delete API key |
| POST | `/v1/keys/{id}/regenerate` | Regenerate API key |
| GET | `/v1/usage` | Get usage statistics |
| GET | `/v1/usage/requests` | Get recent requests |
| GET | `/v1/billing` | Get billing overview |
| POST | `/v1/billing/create-order` | Create Razorpay order |
| POST | `/v1/billing/verify-payment` | Verify payment |
| GET | `/v1/subscription` | Get subscription |
| GET | `/v1/downloads` | Get download history |
| POST | `/v1/downloads` | Log a download |
| GET | `/v1/activity` | Get activity feed |
| POST | `/v1/playground` | Test API (playground) |
| GET | `/v1/auth/profile` | Get user profile |
| PATCH | `/v1/auth/profile` | Update profile |

## Model Routing

The backend maps RUDRX1 model names to provider models internally:

| RUDRX1 Model | Description |
|-------------|-------------|
| `rudrx1-core` | General purpose, advanced reasoning |
| `rudrx1-code` | Code generation and debugging |
| `rudrx1-voice` | Speech-to-text |
| `rudrx1-vision` | Image understanding |
| `rudrx1-fast` | Fast responses for simple tasks |

**Provider model names are NEVER exposed to users.**

## Security

- JWT validation via Supabase
- API key authentication with SHA-256 hashing
- Rate limiting per plan
- CORS protection
- All Groq requests proxied through backend
- Environment variables for all secrets
