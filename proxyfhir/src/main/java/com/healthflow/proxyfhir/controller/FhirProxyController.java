package com.healthflow.proxyfhir.controller;

import com.healthflow.proxyfhir.entity.FhirBundle;
import com.healthflow.proxyfhir.service.FhirClientService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/fhir")
@CrossOrigin(origins = "*")
public class FhirProxyController {

    private static final Logger logger = LoggerFactory.getLogger(FhirProxyController.class);

    private final FhirClientService fhirClientService;

    @Autowired
    public FhirProxyController(FhirClientService fhirClientService) {
        this.fhirClientService = fhirClientService;
    }

    /**
     * Sync patient data from FHIR server
     */
    @PostMapping("/sync/patient/{patientId}")
    public ResponseEntity<Map<String, Object>> syncPatientData(@PathVariable String patientId) {
        logger.info("Received request to sync patient data for ID: {}", patientId);
        
        Map<String, Object> response = new HashMap<>();
        
        try {
            FhirBundle bundle = fhirClientService.fetchAndProcessPatientData(patientId);
            
            if (bundle != null) {
                response.put("status", "success");
                response.put("message", "Patient data synchronized successfully");
                response.put("bundleId", bundle.getId());
                response.put("patientId", patientId);
                response.put("timestamp", bundle.getCreatedAt());
                
                logger.info("Successfully processed patient data for ID: {}", patientId);
                return ResponseEntity.ok(response);
            } else {
                response.put("status", "skipped");
                response.put("message", "Patient data already exists (duplicate)");
                response.put("patientId", patientId);
                
                logger.info("Patient data already exists for ID: {}", patientId);
                return ResponseEntity.ok(response);
            }
            
        } catch (Exception e) {
            logger.error("Error processing patient data for ID {}: {}", patientId, e.getMessage(), e);
            
            response.put("status", "error");
            response.put("message", "Failed to sync patient data: " + e.getMessage());
            response.put("patientId", patientId);
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Batch sync multiple patients
     */
    @PostMapping("/sync/patients")
    public ResponseEntity<Map<String, Object>> syncMultiplePatients(@RequestBody Map<String, Object> request) {
        logger.info("Received request to sync multiple patients");
        
        Map<String, Object> response = new HashMap<>();
        
        try {
            @SuppressWarnings("unchecked")
            java.util.List<String> patientIds = (java.util.List<String>) request.get("patientIds");
            
            if (patientIds == null || patientIds.isEmpty()) {
                response.put("status", "error");
                response.put("message", "Patient IDs list is required");
                return ResponseEntity.badRequest().body(response);
            }

            java.util.List<Map<String, Object>> results = new java.util.ArrayList<>();
            int successCount = 0;
            int errorCount = 0;
            int skippedCount = 0;

            for (String patientId : patientIds) {
                try {
                    FhirBundle bundle = fhirClientService.fetchAndProcessPatientData(patientId);
                    
                    Map<String, Object> result = new HashMap<>();
                    result.put("patientId", patientId);
                    
                    if (bundle != null) {
                        result.put("status", "success");
                        result.put("bundleId", bundle.getId());
                        successCount++;
                    } else {
                        result.put("status", "skipped");
                        result.put("reason", "duplicate");
                        skippedCount++;
                    }
                    
                    results.add(result);
                    
                } catch (Exception e) {
                    Map<String, Object> result = new HashMap<>();
                    result.put("patientId", patientId);
                    result.put("status", "error");
                    result.put("error", e.getMessage());
                    results.add(result);
                    errorCount++;
                    
                    logger.error("Error processing patient {}: {}", patientId, e.getMessage());
                }
            }

            response.put("status", "completed");
            response.put("summary", Map.of(
                "total", patientIds.size(),
                "successful", successCount,
                "skipped", skippedCount,
                "errors", errorCount
            ));
            response.put("results", results);
            
            logger.info("Batch sync completed. Total: {}, Success: {}, Skipped: {}, Errors: {}", 
                patientIds.size(), successCount, skippedCount, errorCount);
            
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("Error in batch sync: {}", e.getMessage(), e);
            
            response.put("status", "error");
            response.put("message", "Batch sync failed: " + e.getMessage());
            
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
        }
    }

    /**
     * Health check endpoint
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> healthCheck() {
        Map<String, Object> response = new HashMap<>();
        
        try {
            String fhirStatus = fhirClientService.getFhirServerStatus();
            
            response.put("status", "healthy");
            response.put("service", "proxyfhir");
            response.put("fhirServer", fhirStatus);
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.ok(response);
            
        } catch (Exception e) {
            logger.error("Health check failed: {}", e.getMessage());
            
            response.put("status", "unhealthy");
            response.put("service", "proxyfhir");
            response.put("error", e.getMessage());
            response.put("timestamp", System.currentTimeMillis());
            
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
        }
    }

    /**
     * Get service info
     */
    @GetMapping("/info")
    public ResponseEntity<Map<String, Object>> getServiceInfo() {
        Map<String, Object> response = new HashMap<>();
        response.put("service", "HealthFlow ProxyFHIR");
        response.put("version", "1.0.0");
        response.put("description", "FHIR Data Ingestion Service");
        response.put("endpoints", Map.of(
            "syncPatient", "POST /api/v1/fhir/sync/patient/{patientId}",
            "syncMultiple", "POST /api/v1/fhir/sync/patients",
            "health", "GET /api/v1/fhir/health",
            "info", "GET /api/v1/fhir/info"
        ));
        
        return ResponseEntity.ok(response);
    }
}