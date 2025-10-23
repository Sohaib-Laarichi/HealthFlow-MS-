package com.healthflow.proxyfhir.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

@Service
public class KafkaProducerService {

    private static final Logger logger = LoggerFactory.getLogger(KafkaProducerService.class);
    
    private static final String FHIR_RAW_DATA_TOPIC = "fhir.data.raw";
    
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    @Autowired
    public KafkaProducerService(KafkaTemplate<String, String> kafkaTemplate, ObjectMapper objectMapper) {
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
    }

    /**
     * Publish FHIR raw data notification to Kafka
     */
    public void publishFhirRawData(String bundleId, String patientId) {
        try {
            // Create message payload
            Map<String, Object> message = new HashMap<>();
            message.put("bundleId", bundleId);
            message.put("patientId", patientId);
            message.put("timestamp", System.currentTimeMillis());
            message.put("source", "proxyfhir");
            message.put("eventType", "fhir_data_ingested");

            String messageJson = objectMapper.writeValueAsString(message);
            
            // Send message to Kafka
            CompletableFuture<SendResult<String, String>> future = kafkaTemplate.send(
                FHIR_RAW_DATA_TOPIC, 
                patientId,  // Use patientId as key for partitioning
                messageJson
            );

            future.whenComplete((result, exception) -> {
                if (exception == null) {
                    logger.info("Published FHIR raw data message for patient {} to topic {} at offset {}",
                        patientId, FHIR_RAW_DATA_TOPIC, result.getRecordMetadata().offset());
                } else {
                    logger.error("Failed to publish FHIR raw data message for patient {}: {}", 
                        patientId, exception.getMessage(), exception);
                }
            });

        } catch (Exception e) {
            logger.error("Error publishing FHIR raw data message for patient {}: {}", 
                patientId, e.getMessage(), e);
            throw new RuntimeException("Failed to publish message to Kafka", e);
        }
    }

    /**
     * Publish audit log to Kafka (optional for audit trail)
     */
    public void publishAuditLog(String operation, String patientId, Map<String, Object> metadata) {
        try {
            Map<String, Object> auditMessage = new HashMap<>();
            auditMessage.put("serviceName", "proxyfhir");
            auditMessage.put("operation", operation);
            auditMessage.put("patientId", patientId);
            auditMessage.put("metadata", metadata);
            auditMessage.put("timestamp", System.currentTimeMillis());

            String messageJson = objectMapper.writeValueAsString(auditMessage);
            
            kafkaTemplate.send("audit.logs", patientId, messageJson);
            
            logger.debug("Published audit log for operation {} on patient {}", operation, patientId);

        } catch (Exception e) {
            logger.warn("Failed to publish audit log: {}", e.getMessage());
            // Don't throw exception for audit logs to avoid disrupting main flow
        }
    }
}