import json
import logging
import os
import time
import pickle
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

import pandas as pd
import numpy as np
import xgboost as xgb
import shap
import joblib
from kafka import KafkaConsumer, KafkaProducer
import psycopg2
import psycopg2.extras
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelRiskService:
    """
    Risk prediction service using XGBoost with SHAP explanations
    """
    
    def __init__(self):
        # Environment variables
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.postgres_host = os.getenv('POSTGRES_HOST', 'postgres')
        self.postgres_db = os.getenv('POSTGRES_DB', 'healthflow')
        self.postgres_user = os.getenv('POSTGRES_USER', 'healthflow')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD', 'healthflow123')
        
        # Kafka topics
        self.input_topic = 'features.patient.ready'
        self.output_topic = 'risk.score.calculated'
        
        # Model paths
        self.model_path = '/app/model/model.xgb'
        self.explainer_path = '/app/model/explainer.pkl'
        self.scaler_path = '/app/model/scaler.pkl'
        self.feature_names_path = '/app/model/feature_names.pkl'
        
        # Initialize components
        self.db_connection = None
        self.kafka_consumer = None
        self.kafka_producer = None
        self.model = None
        self.explainer = None
        self.scaler = None
        self.feature_names = []
        
        # Model version
        self.model_version = "v1.0"
        
    def connect_to_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_connection = psycopg2.connect(
                host=self.postgres_host,
                database=self.postgres_db,
                user=self.postgres_user,
                password=self.postgres_password,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def setup_kafka(self):
        """Setup Kafka consumer and producer"""
        try:
            self.kafka_consumer = KafkaConsumer(
                self.input_topic,
                bootstrap_servers=self.kafka_servers,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                key_deserializer=lambda x: x.decode('utf-8') if x else None,
                group_id='model-risk-service',
                auto_offset_reset='earliest',
                enable_auto_commit=True
            )
            
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda x: json.dumps(x, default=str).encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None
            )
            
            logger.info("Kafka consumer and producer initialized")
        except Exception as e:
            logger.error(f"Failed to setup Kafka: {e}")
            raise
    
    def create_dummy_model(self):
        """
        Create a dummy XGBoost model for demonstration purposes
        """
        logger.info("Creating dummy model and explainer...")
        
        # Generate dummy training data
        np.random.seed(42)
        n_samples = 1000
        n_features = 50
        
        # Create feature names
        self.feature_names = [
            'age', 'gender_male', 'gender_female',
            'total_conditions', 'active_conditions', 'chronic_conditions',
            'total_medications', 'active_medications',
            'heart_rate_mean', 'blood_pressure_mean', 'temperature_mean',
            'condition_cardiovascular', 'condition_diabetes', 'condition_respiratory',
            'medication_cardiovascular', 'medication_diabetes',
            'entity_disease', 'entity_symptom', 'concept_cardiovascular',
            'biobert_emb_0', 'biobert_emb_1', 'biobert_emb_2'
        ]
        
        # Extend feature names to reach n_features
        while len(self.feature_names) < n_features:
            self.feature_names.append(f'feature_{len(self.feature_names)}')
        
        # Generate synthetic data with realistic medical patterns
        X = np.random.randn(n_samples, n_features)
        
        # Create risk factors
        # Age effect
        X[:, 0] = np.random.normal(50, 20, n_samples)  # Age
        X[:, 0] = np.clip(X[:, 0], 0, 100)
        
        # Gender (binary)
        X[:, 1] = np.random.binomial(1, 0.5, n_samples)  # Male
        X[:, 2] = 1 - X[:, 1]  # Female
        
        # Medical conditions and medications
        X[:, 3:8] = np.random.poisson(2, (n_samples, 5))  # Condition/medication counts
        
        # Vital signs (normalized)
        X[:, 8:11] = np.random.normal(0, 1, (n_samples, 3))
        
        # Create target variable with realistic medical risk factors
        # Risk increases with age, number of conditions, and certain patterns
        risk_score = (
            0.02 * X[:, 0] +  # Age effect
            0.3 * X[:, 3] +   # Total conditions effect
            0.2 * X[:, 4] +   # Active conditions effect
            0.15 * X[:, 8] +  # Heart rate effect
            np.random.normal(0, 0.1, n_samples)  # Noise
        )
        
        # Convert to probability using sigmoid
        y_prob = 1 / (1 + np.exp(-risk_score))
        y = np.random.binomial(1, y_prob)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train XGBoost model
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            eval_metric='logloss'
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Create SHAP explainer
        self.explainer = shap.TreeExplainer(self.model)
        
        # Save model components
        os.makedirs('/app/model', exist_ok=True)
        
        # Save XGBoost model
        self.model.save_model(self.model_path)
        
        # Save other components
        with open(self.explainer_path, 'wb') as f:
            pickle.dump(self.explainer, f)
        
        with open(self.scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        with open(self.feature_names_path, 'wb') as f:
            pickle.dump(self.feature_names, f)
        
        logger.info(f"Dummy model created with {n_features} features")
        logger.info(f"Model accuracy on test set: {self.model.score(X_test_scaled, y_test):.3f}")
    
    def load_model_components(self):
        """
        Load model, explainer, and preprocessing components
        """
        try:
            # Check if model files exist, create dummy if not
            if not os.path.exists(self.model_path):
                logger.info("Model files not found, creating dummy model...")
                self.create_dummy_model()
                return
            
            # Load XGBoost model
            self.model = xgb.XGBClassifier()
            self.model.load_model(self.model_path)
            
            # Load explainer
            with open(self.explainer_path, 'rb') as f:
                self.explainer = pickle.load(f)
            
            # Load scaler
            with open(self.scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            
            # Load feature names
            with open(self.feature_names_path, 'rb') as f:
                self.feature_names = pickle.load(f)
            
            logger.info("Model components loaded successfully")
            logger.info(f"Model expects {len(self.feature_names)} features")
            
        except Exception as e:
            logger.error(f"Error loading model components: {e}")
            # Fallback to creating dummy model
            self.create_dummy_model()
    
    def prepare_feature_vector(self, features: Dict[str, Any]) -> np.ndarray:
        """
        Prepare feature vector from extracted features
        """
        try:
            # Create feature vector with expected features
            feature_vector = []
            
            for feature_name in self.feature_names:
                if feature_name in features:
                    value = features[feature_name]
                    # Handle different data types
                    if isinstance(value, (int, float)):
                        feature_vector.append(float(value))
                    elif isinstance(value, bool):
                        feature_vector.append(float(value))
                    elif value is None:
                        feature_vector.append(0.0)
                    else:
                        # Try to convert to float, default to 0
                        try:
                            feature_vector.append(float(value))
                        except:
                            feature_vector.append(0.0)
                else:
                    # Feature not present, use default value
                    feature_vector.append(0.0)
            
            # Ensure we have the right number of features
            while len(feature_vector) < len(self.feature_names):
                feature_vector.append(0.0)
            
            # Convert to numpy array and reshape
            feature_array = np.array(feature_vector).reshape(1, -1)
            
            # Scale features
            if self.scaler:
                feature_array = self.scaler.transform(feature_array)
            
            return feature_array
            
        except Exception as e:
            logger.error(f"Error preparing feature vector: {e}")
            # Return zero vector as fallback
            return np.zeros((1, len(self.feature_names)))
    
    def predict_risk(self, features: Dict[str, Any]) -> Tuple[float, float, Dict[str, float]]:
        """
        Predict risk score and generate SHAP explanations
        """
        try:
            # Prepare feature vector
            feature_vector = self.prepare_feature_vector(features)
            
            # Make prediction
            risk_probability = self.model.predict_proba(feature_vector)[0, 1]
            confidence = max(self.model.predict_proba(feature_vector)[0]) - 0.5
            
            # Generate SHAP values
            shap_values = self.explainer.shap_values(feature_vector)[0]
            
            # Create SHAP explanation dictionary
            shap_explanation = {}
            for i, (feature_name, shap_value) in enumerate(zip(self.feature_names, shap_values)):
                if abs(shap_value) > 0.001:  # Only include significant contributions
                    shap_explanation[feature_name] = float(shap_value)
            
            # Sort by absolute importance
            shap_explanation = dict(sorted(
                shap_explanation.items(), 
                key=lambda x: abs(x[1]), 
                reverse=True
            ))
            
            return float(risk_probability), float(confidence), shap_explanation
            
        except Exception as e:
            logger.error(f"Error predicting risk: {e}")
            # Return default values
            return 0.5, 0.0, {}
    
    def save_prediction_to_database(self, patient_pseudo_id: str, risk_score: float, 
                                  confidence: float, shap_values: Dict[str, float], 
                                  features: Dict[str, Any]):
        """
        Save prediction results to PostgreSQL
        """
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO prediction_results 
                       (patient_pseudo_id, risk_score, prediction_confidence, 
                        shap_values_json, feature_vector_json, model_version) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        patient_pseudo_id,
                        risk_score,
                        confidence,
                        json.dumps(shap_values),
                        json.dumps(features),
                        self.model_version
                    )
                )
                self.db_connection.commit()
                logger.info(f"Saved prediction for patient {patient_pseudo_id} to database")
                
        except Exception as e:
            logger.error(f"Error saving prediction to database: {e}")
    
    def create_explanation_text(self, shap_values: Dict[str, float]) -> str:
        """
        Create human-readable explanation from SHAP values
        """
        if not shap_values:
            return "No significant risk factors identified."
        
        explanations = []
        
        # Get top contributing factors
        top_factors = list(shap_values.items())[:5]
        
        for feature, contribution in top_factors:
            if contribution > 0:
                explanations.append(f"{feature.replace('_', ' ').title()} increases risk (impact: {contribution:.3f})")
            else:
                explanations.append(f"{feature.replace('_', ' ').title()} decreases risk (impact: {contribution:.3f})")
        
        if explanations:
            return "Key risk factors: " + "; ".join(explanations)
        else:
            return "Risk assessment based on overall health profile."
    
    def process_message(self, message):
        """
        Process a single Kafka message
        """
        try:
            logger.info(f"Processing features for patient: {message.get('patientPseudoId')}")
            
            patient_pseudo_id = message.get('patientPseudoId')
            features = message.get('features', {})
            
            if not patient_pseudo_id:
                logger.error("No patient pseudo ID in message")
                return
            
            if not features:
                logger.error("No features in message")
                return
            
            # Predict risk
            risk_score, confidence, shap_values = self.predict_risk(features)
            
            # Create explanation text
            explanation_text = self.create_explanation_text(shap_values)
            
            # Save to database
            self.save_prediction_to_database(
                patient_pseudo_id, risk_score, confidence, shap_values, features
            )
            
            # Create output message for real-time alerts
            output_message = {
                'patientPseudoId': patient_pseudo_id,
                'riskScore': risk_score,
                'confidence': confidence,
                'riskLevel': self._categorize_risk(risk_score),
                'explanation': explanation_text,
                'topRiskFactors': list(shap_values.keys())[:3],
                'modelVersion': self.model_version,
                'timestamp': int(time.time() * 1000),
                'source': 'model-risk-service',
                'eventType': 'risk_score_calculated'
            }
            
            # Publish to output topic
            self.kafka_producer.send(
                self.output_topic,
                key=patient_pseudo_id,
                value=output_message
            )
            
            logger.info(f"Risk prediction completed for patient {patient_pseudo_id}: "
                       f"Score={risk_score:.3f}, Risk Level={self._categorize_risk(risk_score)}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _categorize_risk(self, risk_score: float) -> str:
        """
        Categorize risk score into levels
        """
        if risk_score < 0.3:
            return 'LOW'
        elif risk_score < 0.6:
            return 'MODERATE'
        elif risk_score < 0.8:
            return 'HIGH'
        else:
            return 'CRITICAL'
    
    def run(self):
        """
        Main service loop
        """
        logger.info("Starting Model Risk Service")
        
        # Load model components
        self.load_model_components()
        
        # Setup connections
        self.connect_to_database()
        self.setup_kafka()
        
        logger.info(f"Consuming from topic: {self.input_topic}")
        logger.info(f"Publishing to topic: {self.output_topic}")
        
        try:
            for message in self.kafka_consumer:
                self.process_message(message.value)
                
        except KeyboardInterrupt:
            logger.info("Shutting down service...")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """
        Cleanup resources
        """
        if self.kafka_consumer:
            self.kafka_consumer.close()
        if self.kafka_producer:
            self.kafka_producer.close()
        if self.db_connection:
            self.db_connection.close()
        logger.info("Cleanup completed")

if __name__ == "__main__":
    service = ModelRiskService()
    service.run()