import json
import logging
import os
import time
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter

import pandas as pd
import numpy as np
from kafka import KafkaConsumer, KafkaProducer
import spacy
from transformers import AutoTokenizer, AutoModel
import torch
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from fhir.resources.bundle import Bundle
from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.condition import Condition
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.diagnosticreport import DiagnosticReport

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FeatureExtractor:
    """
    Advanced feature extraction service for FHIR data using NLP and statistical methods
    """
    
    def __init__(self):
        # Environment variables
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        
        # Kafka topics
        self.input_topic = 'fhir.data.anonymized'
        self.output_topic = 'features.patient.ready'
        
        # Initialize NLP models
        self.nlp_model = None
        self.biobert_tokenizer = None
        self.biobert_model = None
        
        # Feature extractors
        self.tfidf_vectorizer = None
        self.scaler = StandardScaler()
        
        # Kafka connections
        self.kafka_consumer = None
        self.kafka_producer = None
        
        # Medical concept mappings
        self.medical_concepts = self._initialize_medical_concepts()
        
    def _initialize_medical_concepts(self) -> Dict[str, List[str]]:
        """
        Initialize medical concept mappings for feature extraction
        """
        return {
            'cardiovascular': [
                'hypertension', 'heart disease', 'myocardial infarction', 'cardiac arrest',
                'coronary artery disease', 'atrial fibrillation', 'heart failure', 'stroke'
            ],
            'diabetes': [
                'diabetes', 'diabetic', 'hyperglycemia', 'hypoglycemia', 'insulin',
                'glucose', 'hemoglobin a1c', 'diabetic neuropathy'
            ],
            'respiratory': [
                'asthma', 'copd', 'pneumonia', 'respiratory failure', 'dyspnea',
                'chronic obstructive pulmonary disease', 'bronchitis', 'lung disease'
            ],
            'renal': [
                'kidney disease', 'renal failure', 'dialysis', 'nephropathy',
                'chronic kidney disease', 'acute kidney injury', 'creatinine'
            ],
            'mental_health': [
                'depression', 'anxiety', 'bipolar', 'schizophrenia', 'ptsd',
                'mental health', 'psychiatric', 'mood disorder'
            ],
            'cancer': [
                'cancer', 'tumor', 'malignancy', 'oncology', 'chemotherapy',
                'radiation therapy', 'metastasis', 'carcinoma'
            ]
        }
    
    def setup_nlp_models(self):
        """
        Initialize NLP models (spaCy and BioBERT)
        """
        try:
            logger.info("Loading spaCy model...")
            self.nlp_model = spacy.load("en_core_sci_sm")
            logger.info("spaCy model loaded successfully")
            
            logger.info("Loading BioBERT model...")
            model_name = "dmis-lab/biobert-base-cased-v1.1"
            self.biobert_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.biobert_model = AutoModel.from_pretrained(model_name)
            self.biobert_model.eval()
            logger.info("BioBERT model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading NLP models: {e}")
            # Fallback to basic processing without advanced NLP
            self.nlp_model = None
            self.biobert_tokenizer = None
            self.biobert_model = None
    
    def setup_kafka(self):
        """
        Setup Kafka consumer and producer
        """
        try:
            self.kafka_consumer = KafkaConsumer(
                self.input_topic,
                bootstrap_servers=self.kafka_servers,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                key_deserializer=lambda x: x.decode('utf-8') if x else None,
                group_id='featurizer-service',
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
    
    def extract_biobert_embeddings(self, text: str) -> np.ndarray:
        """
        Extract BioBERT embeddings from text
        """
        if not self.biobert_model or not self.biobert_tokenizer:
            return np.zeros(768)  # Default embedding size
        
        try:
            # Tokenize and encode
            inputs = self.biobert_tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=512
            )
            
            # Get embeddings
            with torch.no_grad():
                outputs = self.biobert_model(**inputs)
                # Use CLS token embedding (first token)
                embeddings = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error extracting BioBERT embeddings: {e}")
            return np.zeros(768)
    
    def extract_medical_entities(self, text: str) -> Dict[str, int]:
        """
        Extract medical entities using spaCy
        """
        entities = defaultdict(int)
        
        if not self.nlp_model:
            # Fallback to simple keyword matching
            text_lower = text.lower()
            for category, keywords in self.medical_concepts.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        entities[f"entity_{category}"] += text_lower.count(keyword)
            return dict(entities)
        
        try:
            # Process text with spaCy
            doc = self.nlp_model(text)
            
            # Extract entities
            for ent in doc.ents:
                entity_label = ent.label_.lower()
                entities[f"entity_{entity_label}"] += 1
            
            # Extract medical concepts
            text_lower = text.lower()
            for category, keywords in self.medical_concepts.items():
                count = 0
                for keyword in keywords:
                    count += text_lower.count(keyword)
                entities[f"concept_{category}"] = count
            
        except Exception as e:
            logger.error(f"Error extracting medical entities: {e}")
        
        return dict(entities)
    
    def extract_patient_demographics(self, patient_data: dict) -> Dict[str, Any]:
        """
        Extract demographic features from Patient resource
        """
        features = {}
        
        try:
            patient = Patient(**patient_data)
            
            # Age calculation (if birthDate is available)
            if patient.birthDate:
                birth_date = datetime.strptime(str(patient.birthDate), '%Y-%m-%d')
                age = (datetime.now() - birth_date).days // 365
                features['age'] = age
                features['age_group'] = self._categorize_age(age)
            else:
                features['age'] = None
                features['age_group'] = 'unknown'
            
            # Gender
            if patient.gender:
                features['gender'] = patient.gender
                features[f'gender_{patient.gender}'] = 1
            else:
                features['gender'] = 'unknown'
            
            # Marital status
            if patient.maritalStatus and patient.maritalStatus.coding:
                status = patient.maritalStatus.coding[0].code
                features['marital_status'] = status
                features[f'marital_{status}'] = 1
            
        except Exception as e:
            logger.error(f"Error extracting patient demographics: {e}")
        
        return features
    
    def _categorize_age(self, age: int) -> str:
        """
        Categorize age into groups
        """
        if age < 18:
            return 'pediatric'
        elif age < 35:
            return 'young_adult'
        elif age < 50:
            return 'middle_aged'
        elif age < 65:
            return 'older_adult'
        else:
            return 'elderly'
    
    def extract_vital_signs_features(self, observations: List[dict]) -> Dict[str, Any]:
        """
        Extract vital signs and lab values features
        """
        features = {}
        vital_signs = defaultdict(list)
        
        for obs_data in observations:
            try:
                observation = Observation(**obs_data)
                
                # Extract vital signs based on LOINC codes or display names
                if observation.code and observation.code.coding:
                    code_info = observation.code.coding[0]
                    display = code_info.display or code_info.code
                    
                    # Map common vital signs
                    vital_type = self._map_vital_sign_type(display)
                    
                    if vital_type and observation.valueQuantity:
                        value = float(observation.valueQuantity.value)
                        vital_signs[vital_type].append(value)
                
            except Exception as e:
                logger.error(f"Error processing observation: {e}")
                continue
        
        # Calculate statistics for each vital sign
        for vital_type, values in vital_signs.items():
            if values:
                features[f'{vital_type}_count'] = len(values)
                features[f'{vital_type}_mean'] = np.mean(values)
                features[f'{vital_type}_std'] = np.std(values)
                features[f'{vital_type}_min'] = np.min(values)
                features[f'{vital_type}_max'] = np.max(values)
                features[f'{vital_type}_latest'] = values[-1]  # Most recent value
                
                # Calculate trend (slope of linear regression)
                if len(values) > 1:
                    x = np.arange(len(values))
                    slope = np.polyfit(x, values, 1)[0]
                    features[f'{vital_type}_trend'] = slope
        
        return features
    
    def _map_vital_sign_type(self, display: str) -> Optional[str]:
        """
        Map observation display name to vital sign type
        """
        display_lower = display.lower()
        
        mapping = {
            'blood pressure': 'blood_pressure',
            'heart rate': 'heart_rate',
            'temperature': 'temperature',
            'respiratory rate': 'respiratory_rate',
            'oxygen saturation': 'oxygen_saturation',
            'weight': 'weight',
            'height': 'height',
            'bmi': 'bmi',
            'glucose': 'glucose',
            'cholesterol': 'cholesterol',
            'hemoglobin': 'hemoglobin',
            'creatinine': 'creatinine'
        }
        
        for key, value in mapping.items():
            if key in display_lower:
                return value
        
        return None
    
    def extract_condition_features(self, conditions: List[dict]) -> Dict[str, Any]:
        """
        Extract features from Condition resources
        """
        features = {}
        condition_categories = defaultdict(int)
        active_conditions = 0
        chronic_conditions = 0
        
        for cond_data in conditions:
            try:
                condition = Condition(**cond_data)
                
                # Count active conditions
                if (condition.clinicalStatus and 
                    any('active' in coding.code.lower() for coding in condition.clinicalStatus.coding)):
                    active_conditions += 1
                
                # Categorize conditions
                if condition.code and condition.code.coding:
                    display = condition.code.coding[0].display or condition.code.coding[0].code
                    category = self._categorize_condition(display)
                    condition_categories[category] += 1
                
                # Check for chronic conditions
                if condition.category:
                    for category in condition.category:
                        if category.coding:
                            for coding in category.coding:
                                if 'chronic' in coding.display.lower():
                                    chronic_conditions += 1
                                    break
                
            except Exception as e:
                logger.error(f"Error processing condition: {e}")
                continue
        
        features['total_conditions'] = len(conditions)
        features['active_conditions'] = active_conditions
        features['chronic_conditions'] = chronic_conditions
        
        # Add condition category counts
        for category, count in condition_categories.items():
            features[f'condition_{category}'] = count
        
        return features
    
    def _categorize_condition(self, display: str) -> str:
        """
        Categorize condition based on display name
        """
        display_lower = display.lower()
        
        for category, keywords in self.medical_concepts.items():
            for keyword in keywords:
                if keyword in display_lower:
                    return category
        
        return 'other'
    
    def extract_medication_features(self, medications: List[dict]) -> Dict[str, Any]:
        """
        Extract features from MedicationRequest resources
        """
        features = {}
        medication_categories = defaultdict(int)
        active_medications = 0
        
        for med_data in medications:
            try:
                medication = MedicationRequest(**med_data)
                
                # Count active medications
                if (medication.status and medication.status == 'active'):
                    active_medications += 1
                
                # Categorize medications
                if medication.medicationCodeableConcept and medication.medicationCodeableConcept.coding:
                    display = medication.medicationCodeableConcept.coding[0].display
                    if display:
                        category = self._categorize_medication(display)
                        medication_categories[category] += 1
                
            except Exception as e:
                logger.error(f"Error processing medication: {e}")
                continue
        
        features['total_medications'] = len(medications)
        features['active_medications'] = active_medications
        
        # Add medication category counts
        for category, count in medication_categories.items():
            features[f'medication_{category}'] = count
        
        return features
    
    def _categorize_medication(self, display: str) -> str:
        """
        Categorize medication based on display name
        """
        display_lower = display.lower()
        
        # Simple medication categorization
        if any(word in display_lower for word in ['insulin', 'metformin', 'glipizide']):
            return 'diabetes'
        elif any(word in display_lower for word in ['lisinopril', 'amlodipine', 'metoprolol']):
            return 'cardiovascular'
        elif any(word in display_lower for word in ['albuterol', 'prednisone', 'montelukast']):
            return 'respiratory'
        elif any(word in display_lower for word in ['sertraline', 'fluoxetine', 'lorazepam']):
            return 'mental_health'
        else:
            return 'other'
    
    def extract_clinical_notes_features(self, diagnostic_reports: List[dict]) -> Dict[str, Any]:
        """
        Extract NLP features from clinical notes in DiagnosticReports
        """
        features = {}
        all_text = ""
        
        # Collect all clinical text
        for report_data in diagnostic_reports:
            try:
                report = DiagnosticReport(**report_data)
                
                if report.conclusion:
                    all_text += " " + report.conclusion
                
                # Extract text from components
                if hasattr(report, 'result') and report.result:
                    for result_ref in report.result:
                        # In a real implementation, you would resolve these references
                        # For now, we'll skip this part
                        pass
                        
            except Exception as e:
                logger.error(f"Error processing diagnostic report: {e}")
                continue
        
        if all_text.strip():
            # Extract medical entities
            entity_features = self.extract_medical_entities(all_text)
            features.update(entity_features)
            
            # Extract BioBERT embeddings (take first 10 dimensions for feature vector)
            embeddings = self.extract_biobert_embeddings(all_text)
            for i, emb_val in enumerate(embeddings[:10]):
                features[f'biobert_emb_{i}'] = float(emb_val)
            
            # Text statistics
            features['text_length'] = len(all_text)
            features['word_count'] = len(all_text.split())
            features['sentence_count'] = len(re.split(r'[.!?]+', all_text))
        
        return features
    
    def process_fhir_bundle(self, bundle_json: str) -> Dict[str, Any]:
        """
        Process a complete FHIR bundle and extract features
        """
        try:
            bundle_data = json.loads(bundle_json)
            bundle = Bundle(**bundle_data)
            
            # Separate resources by type
            patients = []
            observations = []
            conditions = []
            medications = []
            diagnostic_reports = []
            
            if bundle.entry:
                for entry in bundle.entry:
                    if entry.resource:
                        resource_type = entry.resource.get('resourceType')
                        
                        if resource_type == 'Patient':
                            patients.append(entry.resource)
                        elif resource_type == 'Observation':
                            observations.append(entry.resource)
                        elif resource_type == 'Condition':
                            conditions.append(entry.resource)
                        elif resource_type == 'MedicationRequest':
                            medications.append(entry.resource)
                        elif resource_type == 'DiagnosticReport':
                            diagnostic_reports.append(entry.resource)
            
            # Extract features from each resource type
            features = {}
            
            # Patient demographics
            if patients:
                demo_features = self.extract_patient_demographics(patients[0])
                features.update(demo_features)
            
            # Vital signs and lab values
            vital_features = self.extract_vital_signs_features(observations)
            features.update(vital_features)
            
            # Conditions
            condition_features = self.extract_condition_features(conditions)
            features.update(condition_features)
            
            # Medications
            medication_features = self.extract_medication_features(medications)
            features.update(medication_features)
            
            # Clinical notes
            notes_features = self.extract_clinical_notes_features(diagnostic_reports)
            features.update(notes_features)
            
            # Overall statistics
            features['total_resources'] = len(bundle.entry) if bundle.entry else 0
            features['resource_diversity'] = len(set(entry.resource.get('resourceType') 
                                                   for entry in bundle.entry 
                                                   if entry.resource))
            
            return features
            
        except Exception as e:
            logger.error(f"Error processing FHIR bundle: {e}")
            return {}
    
    def normalize_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and clean features
        """
        normalized = {}
        
        for key, value in features.items():
            if value is None:
                normalized[key] = 0
            elif isinstance(value, (int, float)):
                # Handle infinite and NaN values
                if np.isnan(value) or np.isinf(value):
                    normalized[key] = 0
                else:
                    normalized[key] = float(value)
            elif isinstance(value, str):
                # Convert categorical variables to numeric if needed
                if value in ['male', 'female']:
                    normalized[f'{key}_{value}'] = 1
                else:
                    normalized[key] = value
            else:
                normalized[key] = value
        
        return normalized
    
    def process_message(self, message):
        """
        Process a single Kafka message
        """
        try:
            logger.info(f"Processing anonymized data for patient: {message.get('patientPseudoId')}")
            
            patient_pseudo_id = message.get('patientPseudoId')
            anonymized_bundle = message.get('anonymizedBundle')
            
            if not patient_pseudo_id or not anonymized_bundle:
                logger.error("Missing required fields in message")
                return
            
            # Extract features from the bundle
            features = self.process_fhir_bundle(anonymized_bundle)
            
            # Add patient identifier
            features['patient_pseudo_id'] = patient_pseudo_id
            
            # Normalize features
            normalized_features = self.normalize_features(features)
            
            # Create output message
            output_message = {
                'patientPseudoId': patient_pseudo_id,
                'features': normalized_features,
                'featureCount': len(normalized_features),
                'timestamp': int(time.time() * 1000),
                'source': 'featurizer-service',
                'eventType': 'features_extracted'
            }
            
            # Publish to output topic
            self.kafka_producer.send(
                self.output_topic,
                key=patient_pseudo_id,
                value=output_message
            )
            
            logger.info(f"Successfully extracted {len(normalized_features)} features for patient {patient_pseudo_id}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """
        Main service loop
        """
        logger.info("Starting Feature Extraction Service")
        
        # Setup NLP models
        self.setup_nlp_models()
        
        # Setup Kafka
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
        logger.info("Cleanup completed")

if __name__ == "__main__":
    extractor = FeatureExtractor()
    extractor.run()