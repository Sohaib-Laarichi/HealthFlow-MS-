import json
import logging
import os
import time
import hashlib
import uuid
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

import psycopg2
import psycopg2.extras
from kafka import KafkaConsumer, KafkaProducer
from faker import Faker
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

class DeIdentificationService:
    """
    Service for de-identifying FHIR data using pseudonymization
    """
    
    def __init__(self):
        # Initialize Faker for generating pseudonyms
        self.faker = Faker()
        Faker.seed(42)  # For reproducibility
        
        # Environment variables
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.postgres_host = os.getenv('POSTGRES_HOST', 'postgres')
        self.postgres_db = os.getenv('POSTGRES_DB', 'healthflow')
        self.postgres_user = os.getenv('POSTGRES_USER', 'healthflow')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD', 'healthflow123')
        self.salt = os.getenv('DEID_SALT', 'healthflow-deid-salt-2024')
        
        # Kafka topics
        self.input_topic = 'fhir.data.raw'
        self.output_topic = 'fhir.data.anonymized'
        
        # Initialize connections
        self.db_connection = None
        self.kafka_consumer = None
        self.kafka_producer = None
        
        # Cache for pseudonym mappings
        self.pseudonym_cache = {}
        
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
                group_id='deid-service',
                auto_offset_reset='earliest',
                enable_auto_commit=True
            )
            
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                key_serializer=lambda x: x.encode('utf-8') if x else None
            )
            
            logger.info("Kafka consumer and producer initialized")
        except Exception as e:
            logger.error(f"Failed to setup Kafka: {e}")
            raise
    
    def get_or_create_pseudonym(self, original_id: str, identifier_type: str) -> str:
        """
        Get existing pseudonym or create a new one for an identifier
        """
        cache_key = f"{identifier_type}:{original_id}"
        
        # Check cache first
        if cache_key in self.pseudonym_cache:
            return self.pseudonym_cache[cache_key]
        
        try:
            # Check database for existing mapping
            with self.db_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pseudonym_identifier FROM pseudonym_mapping WHERE original_identifier = %s AND identifier_type = %s",
                    (original_id, identifier_type)
                )
                result = cursor.fetchone()
                
                if result:
                    pseudonym = result['pseudonym_identifier']
                    self.pseudonym_cache[cache_key] = pseudonym
                    return pseudonym
                
                # Create new pseudonym
                pseudonym = self.generate_pseudonym(original_id, identifier_type)
                
                # Store in database
                cursor.execute(
                    """INSERT INTO pseudonym_mapping 
                       (original_identifier, pseudonym_identifier, identifier_type, salt_used) 
                       VALUES (%s, %s, %s, %s)""",
                    (original_id, pseudonym, identifier_type, self.salt)
                )
                self.db_connection.commit()
                
                # Cache the result
                self.pseudonym_cache[cache_key] = pseudonym
                return pseudonym
                
        except Exception as e:
            logger.error(f"Error managing pseudonym for {original_id}: {e}")
            # Fallback to generating pseudonym without database storage
            return self.generate_pseudonym(original_id, identifier_type)
    
    def generate_pseudonym(self, original_id: str, identifier_type: str) -> str:
        """
        Generate a consistent pseudonym using hash-based approach
        """
        # Create hash from original ID, type and salt
        hash_input = f"{original_id}:{identifier_type}:{self.salt}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Generate pseudonym based on type
        if identifier_type == 'patient_id':
            # Use hash to seed Faker for consistent generation
            temp_faker = Faker()
            temp_faker.seed_instance(int(hash_digest[:8], 16))
            return f"PATIENT_{temp_faker.random_number(digits=6)}"
        
        elif identifier_type == 'practitioner_id':
            temp_faker = Faker()
            temp_faker.seed_instance(int(hash_digest[:8], 16))
            return f"PRACT_{temp_faker.random_number(digits=5)}"
        
        elif identifier_type == 'organization_id':
            temp_faker = Faker()
            temp_faker.seed_instance(int(hash_digest[:8], 16))
            return f"ORG_{temp_faker.random_number(digits=4)}"
        
        elif identifier_type == 'name':
            temp_faker = Faker()
            temp_faker.seed_instance(int(hash_digest[:8], 16))
            return temp_faker.name()
        
        elif identifier_type == 'phone':
            temp_faker = Faker()
            temp_faker.seed_instance(int(hash_digest[:8], 16))
            return temp_faker.phone_number()
        
        elif identifier_type == 'email':
            temp_faker = Faker()
            temp_faker.seed_instance(int(hash_digest[:8], 16))
            return temp_faker.email()
        
        else:
            # Generic pseudonym for other types
            return f"PSEUDO_{hash_digest[:12].upper()}"
    
    def anonymize_patient_resource(self, patient_data: dict) -> dict:
        """
        Anonymize Patient resource
        """
        try:
            patient = Patient(**patient_data)
            
            # Anonymize patient ID
            if patient.id:
                patient.id = self.get_or_create_pseudonym(patient.id, 'patient_id')
            
            # Anonymize identifiers
            if patient.identifier:
                for identifier in patient.identifier:
                    if identifier.value:
                        identifier.value = self.get_or_create_pseudonym(identifier.value, 'patient_identifier')
            
            # Anonymize names
            if patient.name:
                for name in patient.name:
                    if name.family:
                        name.family = self.get_or_create_pseudonym(name.family, 'name')
                    if name.given:
                        name.given = [self.get_or_create_pseudonym(given, 'name') for given in name.given]
            
            # Anonymize contact information
            if patient.telecom:
                for telecom in patient.telecom:
                    if telecom.value:
                        if telecom.system == 'phone':
                            telecom.value = self.get_or_create_pseudonym(telecom.value, 'phone')
                        elif telecom.system == 'email':
                            telecom.value = self.get_or_create_pseudonym(telecom.value, 'email')
            
            # Remove addresses completely for privacy
            if hasattr(patient, 'address'):
                patient.address = None
            
            return patient.dict()
            
        except Exception as e:
            logger.error(f"Error anonymizing patient resource: {e}")
            return patient_data
    
    def anonymize_observation_resource(self, observation_data: dict) -> dict:
        """
        Anonymize Observation resource
        """
        try:
            observation = Observation(**observation_data)
            
            # Anonymize patient reference
            if observation.subject and observation.subject.reference:
                original_ref = observation.subject.reference
                if original_ref.startswith('Patient/'):
                    patient_id = original_ref.replace('Patient/', '')
                    pseudo_id = self.get_or_create_pseudonym(patient_id, 'patient_id')
                    observation.subject.reference = f"Patient/{pseudo_id}"
            
            # Anonymize performer references
            if observation.performer:
                for performer in observation.performer:
                    if performer.reference:
                        if performer.reference.startswith('Practitioner/'):
                            pract_id = performer.reference.replace('Practitioner/', '')
                            pseudo_id = self.get_or_create_pseudonym(pract_id, 'practitioner_id')
                            performer.reference = f"Practitioner/{pseudo_id}"
            
            return observation.dict()
            
        except Exception as e:
            logger.error(f"Error anonymizing observation resource: {e}")
            return observation_data
    
    def anonymize_condition_resource(self, condition_data: dict) -> dict:
        """
        Anonymize Condition resource
        """
        try:
            condition = Condition(**condition_data)
            
            # Anonymize patient reference
            if condition.subject and condition.subject.reference:
                original_ref = condition.subject.reference
                if original_ref.startswith('Patient/'):
                    patient_id = original_ref.replace('Patient/', '')
                    pseudo_id = self.get_or_create_pseudonym(patient_id, 'patient_id')
                    condition.subject.reference = f"Patient/{pseudo_id}"
            
            return condition.dict()
            
        except Exception as e:
            logger.error(f"Error anonymizing condition resource: {e}")
            return condition_data
    
    def anonymize_medication_request_resource(self, medication_data: dict) -> dict:
        """
        Anonymize MedicationRequest resource
        """
        try:
            med_request = MedicationRequest(**medication_data)
            
            # Anonymize patient reference
            if med_request.subject and med_request.subject.reference:
                original_ref = med_request.subject.reference
                if original_ref.startswith('Patient/'):
                    patient_id = original_ref.replace('Patient/', '')
                    pseudo_id = self.get_or_create_pseudonym(patient_id, 'patient_id')
                    med_request.subject.reference = f"Patient/{pseudo_id}"
            
            # Anonymize requester reference
            if med_request.requester and med_request.requester.reference:
                if med_request.requester.reference.startswith('Practitioner/'):
                    pract_id = med_request.requester.reference.replace('Practitioner/', '')
                    pseudo_id = self.get_or_create_pseudonym(pract_id, 'practitioner_id')
                    med_request.requester.reference = f"Practitioner/{pseudo_id}"
            
            return med_request.dict()
            
        except Exception as e:
            logger.error(f"Error anonymizing medication request resource: {e}")
            return medication_data
    
    def anonymize_bundle(self, bundle_json: str) -> str:
        """
        Anonymize a complete FHIR Bundle
        """
        try:
            bundle_data = json.loads(bundle_json)
            bundle = Bundle(**bundle_data)
            
            if bundle.entry:
                for entry in bundle.entry:
                    if entry.resource:
                        resource_type = entry.resource.get('resourceType')
                        
                        if resource_type == 'Patient':
                            entry.resource = self.anonymize_patient_resource(entry.resource)
                        elif resource_type == 'Observation':
                            entry.resource = self.anonymize_observation_resource(entry.resource)
                        elif resource_type == 'Condition':
                            entry.resource = self.anonymize_condition_resource(entry.resource)
                        elif resource_type == 'MedicationRequest':
                            entry.resource = self.anonymize_medication_request_resource(entry.resource)
                        # Add more resource types as needed
            
            return json.dumps(bundle.dict(), default=str)
            
        except Exception as e:
            logger.error(f"Error anonymizing bundle: {e}")
            return bundle_json
    
    def get_bundle_from_database(self, bundle_id: str) -> Optional[str]:
        """
        Retrieve FHIR bundle from database by ID
        """
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT bundle_data FROM fhir_bundles WHERE id = %s",
                    (bundle_id,)
                )
                result = cursor.fetchone()
                
                if result:
                    return result['bundle_data']
                else:
                    logger.warning(f"Bundle not found: {bundle_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error retrieving bundle {bundle_id} from database: {e}")
            return None
    
    def process_message(self, message):
        """
        Process a single Kafka message
        """
        try:
            logger.info(f"Processing message for patient: {message.get('patientId')}")
            
            bundle_id = message.get('bundleId')
            patient_id = message.get('patientId')
            
            if not bundle_id:
                logger.error("No bundleId in message")
                return
            
            # Retrieve bundle from database
            bundle_json = self.get_bundle_from_database(bundle_id)
            if not bundle_json:
                logger.error(f"Could not retrieve bundle {bundle_id}")
                return
            
            # Anonymize the bundle
            anonymized_bundle = self.anonymize_bundle(bundle_json)
            
            # Get pseudonymized patient ID
            pseudo_patient_id = self.get_or_create_pseudonym(patient_id, 'patient_id')
            
            # Create output message
            output_message = {
                'originalBundleId': bundle_id,
                'patientPseudoId': pseudo_patient_id,
                'anonymizedBundle': anonymized_bundle,
                'timestamp': int(time.time() * 1000),
                'source': 'deid-service',
                'eventType': 'fhir_data_anonymized'
            }
            
            # Publish to output topic
            self.kafka_producer.send(
                self.output_topic,
                key=pseudo_patient_id,
                value=output_message
            )
            
            logger.info(f"Successfully anonymized and published data for patient {patient_id} -> {pseudo_patient_id}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """
        Main service loop
        """
        logger.info("Starting DeIdentification Service")
        
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
    service = DeIdentificationService()
    service.run()