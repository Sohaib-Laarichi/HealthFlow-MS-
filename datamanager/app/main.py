import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from fastapi.responses import RedirectResponse

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("datamanager")

# Env
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'healthflow')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'healthflow')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'healthflow123')
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
ALGORITHM = 'HS256'
PROXYFHIR_BASE = os.getenv('PROXYFHIR_BASE', 'http://proxyfhir:8080')

# App
app = FastAPI(
    title="HealthFlow Data Manager API",
    description="Admin API to manage new data entries and trigger ingestion",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# DB
class DB:
    conn = None

    @classmethod
    def get(cls):
        if cls.conn is None or cls.conn.closed:
            cls.conn = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        return cls.conn

# Models
class PredictionIn(BaseModel):
    patient_pseudo_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    prediction_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    shap_values_json: Optional[Dict[str, float]] = None
    feature_vector_json: Optional[Dict[str, Any]] = None
    model_version: Optional[str] = Field(default="v1.0")
    prediction_timestamp: Optional[datetime] = None

class PredictionOut(BaseModel):
    id: str
    patient_pseudo_id: str
    risk_score: float
    prediction_confidence: Optional[float] = None
    shap_values_json: Optional[Dict[str, float]] = None
    feature_vector_json: Optional[Dict[str, Any]] = None
    model_version: str
    prediction_timestamp: datetime
    created_at: datetime

# Health
@app.get("/health")
def health():
    ok = True
    try:
        conn = DB.get()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as e:
        ok = False
    return {"status": "healthy" if ok else "unhealthy", "timestamp": datetime.utcnow().isoformat()}

# Convenience: redirect root to /docs for easier discovery
@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/docs")

# CRUD Endpoints
@app.post("/api/v1/predictions", response_model=PredictionOut)
def create_prediction(item: PredictionIn, _: dict = Depends(verify_token)):
    conn = DB.get()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prediction_results (
                patient_pseudo_id, risk_score, prediction_confidence,
                shap_values_json, feature_vector_json, model_version,
                prediction_timestamp
            ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, COALESCE(%s, NOW()))
            RETURNING id, patient_pseudo_id, risk_score, prediction_confidence,
                shap_values_json, feature_vector_json, model_version,
                prediction_timestamp, created_at
            """,
            (
                item.patient_pseudo_id,
                item.risk_score,
                item.prediction_confidence,
                json.dumps(item.shap_values_json) if item.shap_values_json is not None else None,
                json.dumps(item.feature_vector_json) if item.feature_vector_json is not None else None,
                item.model_version,
                item.prediction_timestamp,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row

@app.get("/api/v1/predictions", response_model=List[PredictionOut])
def list_predictions(limit: int = 50, offset: int = 0, _: dict = Depends(verify_token)):
    limit = max(1, min(limit, 500))
    conn = DB.get()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, patient_pseudo_id, risk_score, prediction_confidence,
                   shap_values_json, feature_vector_json, model_version,
                   prediction_timestamp, created_at
            FROM prediction_results
            ORDER BY prediction_timestamp DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = cur.fetchall()
        return rows

@app.get("/api/v1/predictions/{prediction_id}", response_model=PredictionOut)
def get_prediction(prediction_id: str, _: dict = Depends(verify_token)):
    conn = DB.get()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, patient_pseudo_id, risk_score, prediction_confidence,
                   shap_values_json, feature_vector_json, model_version,
                   prediction_timestamp, created_at
            FROM prediction_results
            WHERE id = %s
            """,
            (prediction_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return row

@app.put("/api/v1/predictions/{prediction_id}", response_model=PredictionOut)
def update_prediction(prediction_id: str, item: PredictionIn, _: dict = Depends(verify_token)):
    conn = DB.get()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE prediction_results SET
                patient_pseudo_id = %s,
                risk_score = %s,
                prediction_confidence = %s,
                shap_values_json = %s::jsonb,
                feature_vector_json = %s::jsonb,
                model_version = %s,
                prediction_timestamp = COALESCE(%s, prediction_timestamp)
            WHERE id = %s
            RETURNING id, patient_pseudo_id, risk_score, prediction_confidence,
                      shap_values_json, feature_vector_json, model_version,
                      prediction_timestamp, created_at
            """,
            (
                item.patient_pseudo_id,
                item.risk_score,
                item.prediction_confidence,
                json.dumps(item.shap_values_json) if item.shap_values_json is not None else None,
                json.dumps(item.feature_vector_json) if item.feature_vector_json is not None else None,
                item.model_version,
                item.prediction_timestamp,
                prediction_id,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
        return row

@app.delete("/api/v1/predictions/{prediction_id}")
def delete_prediction(prediction_id: str, _: dict = Depends(verify_token)):
    conn = DB.get()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM prediction_results WHERE id = %s RETURNING id", (prediction_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        conn.commit()
        return {"status": "deleted", "id": prediction_id}

# Trigger ProxyFHIR ingestion for a patient id
@app.post("/api/v1/ingest/patient/{patient_id}")
def trigger_ingest(patient_id: str, _: dict = Depends(verify_token)):
    try:
        url = f"{PROXYFHIR_BASE}/api/v1/fhir/sync/patient/{patient_id}"
        resp = requests.post(url, timeout=60)
        return {"status": "forwarded", "proxyfhir_status": resp.status_code, "body": resp.json() if resp.headers.get('content-type','').startswith('application/json') else resp.text}
    except Exception as e:
        logger.error(f"Trigger ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Simple token endpoint for development convenience (NOT for production)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@app.post("/auth/token", response_model=TokenResponse)
def dev_token():
    # issue a short-lived token with role=admin
    payload = {"sub": "dev-admin", "role": "admin", "exp": int((datetime.utcnow() + timedelta(minutes=60)).timestamp())}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return TokenResponse(access_token=token)
