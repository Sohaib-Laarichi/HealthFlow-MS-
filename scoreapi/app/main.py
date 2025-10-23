import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from passlib.context import CryptContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Database Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'healthflow')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'healthflow')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'healthflow123')

# Initialize FastAPI app
app = FastAPI(
    title="HealthFlow Score API",
    description="Secure API for accessing patient risk scores and explanations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic Models
class RiskScore(BaseModel):
    patient_pseudo_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Risk probability between 0 and 1")
    prediction_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    risk_level: str = Field(..., description="Categorical risk level")
    model_version: str
    prediction_timestamp: datetime
    created_at: datetime

class RiskExplanation(BaseModel):
    patient_pseudo_id: str
    risk_score: float
    shap_values: Dict[str, float] = Field(..., description="SHAP values for feature contributions")
    top_risk_factors: List[str] = Field(..., description="Top contributing risk factors")
    explanation_text: str = Field(..., description="Human-readable explanation")
    model_version: str
    prediction_timestamp: datetime

class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    database_connected: bool
    version: str

class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime

# Database connection pool
class DatabaseManager:
    def __init__(self):
        self.connection = None
    
    def get_connection(self):
        if not self.connection or self.connection.closed:
            self.connection = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        return self.connection
    
    def close_connection(self):
        if self.connection and not self.connection.closed:
            self.connection.close()

db_manager = DatabaseManager()

# JWT Token Functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Utility Functions
def categorize_risk_level(risk_score: float) -> str:
    """Categorize risk score into levels"""
    if risk_score < 0.3:
        return 'LOW'
    elif risk_score < 0.6:
        return 'MODERATE'
    elif risk_score < 0.8:
        return 'HIGH'
    else:
        return 'CRITICAL'

def format_explanation_text(shap_values: Dict[str, float]) -> str:
    """Create human-readable explanation from SHAP values"""
    if not shap_values:
        return "No significant risk factors identified."
    
    explanations = []
    top_factors = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    
    for feature, contribution in top_factors:
        if contribution > 0:
            explanations.append(f"{feature.replace('_', ' ').title()} increases risk (impact: {contribution:.3f})")
        else:
            explanations.append(f"{feature.replace('_', ' ').title()} decreases risk (impact: {contribution:.3f})")
    
    return "Key risk factors: " + "; ".join(explanations) if explanations else "Risk assessment based on overall health profile."

# API Endpoints

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        connection = db_manager.get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_connected = cursor.fetchone() is not None
        
        return HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow(),
            database_connected=db_connected,
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            database_connected=False,
            version="1.0.0"
        )

@app.post("/auth/token")
async def get_access_token():
    """
    Get access token for API authentication
    In production, this should include proper user authentication
    """
    # For demo purposes, we'll create a token without user validation
    # In production, validate user credentials first
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": "demo_user"}, 
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.get("/api/v1/score/{patient_pseudo_id}", response_model=RiskScore)
async def get_patient_risk_score(
    patient_pseudo_id: str,
    current_user: str = Depends(verify_token)
):
    """Get the latest risk score for a patient"""
    try:
        connection = db_manager.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT patient_pseudo_id, risk_score, prediction_confidence, 
                          model_version, prediction_timestamp, created_at
                   FROM prediction_results 
                   WHERE patient_pseudo_id = %s 
                   ORDER BY prediction_timestamp DESC 
                   LIMIT 1""",
                (patient_pseudo_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No risk score found for patient {patient_pseudo_id}"
                )
            
            risk_level = categorize_risk_level(result['risk_score'])
            
            return RiskScore(
                patient_pseudo_id=result['patient_pseudo_id'],
                risk_score=result['risk_score'],
                prediction_confidence=result['prediction_confidence'],
                risk_level=risk_level,
                model_version=result['model_version'],
                prediction_timestamp=result['prediction_timestamp'],
                created_at=result['created_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting risk score for patient {patient_pseudo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving risk score"
        )

@app.get("/api/v1/explain/{patient_pseudo_id}", response_model=RiskExplanation)
async def get_patient_risk_explanation(
    patient_pseudo_id: str,
    current_user: str = Depends(verify_token)
):
    """Get risk explanation with SHAP values for a patient"""
    try:
        connection = db_manager.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT patient_pseudo_id, risk_score, shap_values_json, 
                          model_version, prediction_timestamp
                   FROM prediction_results 
                   WHERE patient_pseudo_id = %s 
                   ORDER BY prediction_timestamp DESC 
                   LIMIT 1""",
                (patient_pseudo_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No risk explanation found for patient {patient_pseudo_id}"
                )
            
            # Parse SHAP values
            shap_values = json.loads(result['shap_values_json']) if result['shap_values_json'] else {}
            
            # Get top risk factors
            top_factors = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
            top_risk_factors = [factor[0] for factor in top_factors]
            
            # Generate explanation text
            explanation_text = format_explanation_text(shap_values)
            
            return RiskExplanation(
                patient_pseudo_id=result['patient_pseudo_id'],
                risk_score=result['risk_score'],
                shap_values=shap_values,
                top_risk_factors=top_risk_factors,
                explanation_text=explanation_text,
                model_version=result['model_version'],
                prediction_timestamp=result['prediction_timestamp']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting risk explanation for patient {patient_pseudo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving risk explanation"
        )

@app.get("/api/v1/scores/recent", response_model=List[RiskScore])
async def get_recent_risk_scores(
    limit: int = 50,
    current_user: str = Depends(verify_token)
):
    """Get recent risk scores across all patients"""
    try:
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit cannot exceed 1000"
            )
        
        connection = db_manager.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT ON (patient_pseudo_id) 
                          patient_pseudo_id, risk_score, prediction_confidence, 
                          model_version, prediction_timestamp, created_at
                   FROM prediction_results 
                   ORDER BY patient_pseudo_id, prediction_timestamp DESC
                   LIMIT %s""",
                (limit,)
            )
            results = cursor.fetchall()
            
            scores = []
            for result in results:
                risk_level = categorize_risk_level(result['risk_score'])
                scores.append(RiskScore(
                    patient_pseudo_id=result['patient_pseudo_id'],
                    risk_score=result['risk_score'],
                    prediction_confidence=result['prediction_confidence'],
                    risk_level=risk_level,
                    model_version=result['model_version'],
                    prediction_timestamp=result['prediction_timestamp'],
                    created_at=result['created_at']
                ))
            
            return scores
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent risk scores: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving recent scores"
        )

@app.get("/api/v1/scores/high-risk", response_model=List[RiskScore])
async def get_high_risk_patients(
    threshold: float = 0.7,
    limit: int = 100,
    current_user: str = Depends(verify_token)
):
    """Get patients with high risk scores"""
    try:
        if not 0.0 <= threshold <= 1.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Threshold must be between 0.0 and 1.0"
            )
        
        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit cannot exceed 1000"
            )
        
        connection = db_manager.get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT DISTINCT ON (patient_pseudo_id) 
                          patient_pseudo_id, risk_score, prediction_confidence, 
                          model_version, prediction_timestamp, created_at
                   FROM prediction_results 
                   WHERE risk_score >= %s
                   ORDER BY patient_pseudo_id, prediction_timestamp DESC, risk_score DESC
                   LIMIT %s""",
                (threshold, limit)
            )
            results = cursor.fetchall()
            
            scores = []
            for result in results:
                risk_level = categorize_risk_level(result['risk_score'])
                scores.append(RiskScore(
                    patient_pseudo_id=result['patient_pseudo_id'],
                    risk_score=result['risk_score'],
                    prediction_confidence=result['prediction_confidence'],
                    risk_level=risk_level,
                    model_version=result['model_version'],
                    prediction_timestamp=result['prediction_timestamp'],
                    created_at=result['created_at']
                ))
            
            return scores
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting high-risk patients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving high-risk patients"
        )

@app.get("/api/v1/statistics/summary")
async def get_summary_statistics(
    current_user: str = Depends(verify_token)
):
    """Get summary statistics about risk predictions"""
    try:
        connection = db_manager.get_connection()
        with connection.cursor() as cursor:
            # Get overall statistics
            cursor.execute(
                """SELECT 
                       COUNT(DISTINCT patient_pseudo_id) as total_patients,
                       COUNT(*) as total_predictions,
                       AVG(risk_score) as mean_risk_score,
                       MIN(risk_score) as min_risk_score,
                       MAX(risk_score) as max_risk_score,
                       COUNT(CASE WHEN risk_score >= 0.7 THEN 1 END) as high_risk_count,
                       COUNT(CASE WHEN risk_score < 0.3 THEN 1 END) as low_risk_count
                   FROM prediction_results
                   WHERE prediction_timestamp >= NOW() - INTERVAL '7 days'"""
            )
            stats = cursor.fetchone()
            
            # Get risk distribution
            cursor.execute(
                """SELECT 
                       CASE 
                           WHEN risk_score < 0.3 THEN 'LOW'
                           WHEN risk_score < 0.6 THEN 'MODERATE'
                           WHEN risk_score < 0.8 THEN 'HIGH'
                           ELSE 'CRITICAL'
                       END as risk_level,
                       COUNT(*) as count
                   FROM prediction_results
                   WHERE prediction_timestamp >= NOW() - INTERVAL '7 days'
                   GROUP BY 1
                   ORDER BY 1"""
            )
            risk_distribution = cursor.fetchall()
            
            return {
                "summary": {
                    "total_patients": stats['total_patients'] or 0,
                    "total_predictions": stats['total_predictions'] or 0,
                    "mean_risk_score": float(stats['mean_risk_score']) if stats['mean_risk_score'] else 0.0,
                    "min_risk_score": float(stats['min_risk_score']) if stats['min_risk_score'] else 0.0,
                    "max_risk_score": float(stats['max_risk_score']) if stats['max_risk_score'] else 0.0,
                    "high_risk_patients": stats['high_risk_count'] or 0,
                    "low_risk_patients": stats['low_risk_count'] or 0
                },
                "risk_distribution": [
                    {"risk_level": row['risk_level'], "count": row['count']}
                    for row in risk_distribution
                ],
                "period": "last_7_days",
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        logger.error(f"Error getting summary statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving statistics"
        )

# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return ErrorResponse(
        error="Internal Server Error",
        message="An unexpected error occurred",
        timestamp=datetime.utcnow()
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("HealthFlow Score API starting up...")
    try:
        # Test database connection
        connection = db_manager.get_connection()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("HealthFlow Score API shutting down...")
    db_manager.close_connection()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)