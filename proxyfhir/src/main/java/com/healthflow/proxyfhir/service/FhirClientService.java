package com.healthflow.proxyfhir.service;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.gclient.IQuery;
import com.healthflow.proxyfhir.entity.FhirBundle;
import com.healthflow.proxyfhir.repository.FhirBundleRepository;
import org.hl7.fhir.r4.model.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;

@Service
public class FhirClientService {

    private static final Logger logger = LoggerFactory.getLogger(FhirClientService.class);

    @Value("${fhir.server.base-url:https://hapi.fhir.org/baseR4}")
    private String fhirServerBaseUrl;

    private final FhirContext fhirContext;
    private final IGenericClient fhirClient;
    private final FhirBundleRepository fhirBundleRepository;
    private final KafkaProducerService kafkaProducerService;

    @Autowired
    public FhirClientService(FhirBundleRepository fhirBundleRepository, 
                           KafkaProducerService kafkaProducerService) {
        this.fhirBundleRepository = fhirBundleRepository;
        this.kafkaProducerService = kafkaProducerService;
        this.fhirContext = FhirContext.forR4();
        this.fhirClient = fhirContext.newRestfulGenericClient(fhirServerBaseUrl);
    }

    /**
     * Fetch patient data from FHIR server and process it
     */
    public FhirBundle fetchAndProcessPatientData(String patientId) {
        try {
            logger.info("Fetching FHIR data for patient: {}", patientId);

            // Create a Bundle to collect all patient-related resources
            Bundle patientBundle = createPatientBundle(patientId);

            // Convert Bundle to JSON
            String bundleJson = fhirContext.newJsonParser()
                .setPrettyPrint(true)
                .encodeResourceToString(patientBundle);

            // Calculate hash to avoid duplicates
            String dataHash = calculateHash(bundleJson);

            // Check if this exact data already exists
            if (fhirBundleRepository.existsByOriginalDataHash(dataHash)) {
                logger.info("Bundle with hash {} already exists, skipping", dataHash);
                return null;
            }

            // Save to database
            FhirBundle fhirBundleEntity = new FhirBundle(
                patientId,
                "Patient",
                bundleJson,
                dataHash
            );

            FhirBundle savedBundle = fhirBundleRepository.save(fhirBundleEntity);
            logger.info("Saved FHIR bundle with ID: {}", savedBundle.getId());

            // Publish to Kafka
            kafkaProducerService.publishFhirRawData(savedBundle.getId().toString(), patientId);

            return savedBundle;

        } catch (Exception e) {
            logger.error("Error fetching FHIR data for patient {}: {}", patientId, e.getMessage(), e);
            throw new RuntimeException("Failed to fetch FHIR data", e);
        }
    }

    /**
     * Create a comprehensive bundle for a patient
     */
    private Bundle createPatientBundle(String patientId) {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.COLLECTION);
        bundle.setId("patient-bundle-" + patientId);

        List<Bundle.BundleEntryComponent> entries = new ArrayList<>();

        try {
            // Fetch Patient resource
            Patient patient = fhirClient.read()
                .resource(Patient.class)
                .withId(patientId)
                .execute();
            
            if (patient != null) {
                entries.add(createBundleEntry(patient));
                logger.debug("Added Patient resource to bundle");
            }

            // Fetch Observations for the patient
            Bundle observationsBundle = fhirClient.search()
                .forResource(Observation.class)
                .where(Observation.SUBJECT.hasId(patientId))
                .count(100)
                .returnBundle(Bundle.class)
                .execute();

            if (observationsBundle != null && observationsBundle.hasEntry()) {
                for (Bundle.BundleEntryComponent entry : observationsBundle.getEntry()) {
                    if (entry.getResource() instanceof Observation) {
                        entries.add(createBundleEntry(entry.getResource()));
                    }
                }
                logger.debug("Added {} Observation resources to bundle", observationsBundle.getEntry().size());
            }

            // Fetch Conditions for the patient
            Bundle conditionsBundle = fhirClient.search()
                .forResource(Condition.class)
                .where(Condition.SUBJECT.hasId(patientId))
                .count(50)
                .returnBundle(Bundle.class)
                .execute();

            if (conditionsBundle != null && conditionsBundle.hasEntry()) {
                for (Bundle.BundleEntryComponent entry : conditionsBundle.getEntry()) {
                    if (entry.getResource() instanceof Condition) {
                        entries.add(createBundleEntry(entry.getResource()));
                    }
                }
                logger.debug("Added {} Condition resources to bundle", conditionsBundle.getEntry().size());
            }

            // Fetch MedicationRequests for the patient
            Bundle medicationsBundle = fhirClient.search()
                .forResource(MedicationRequest.class)
                .where(MedicationRequest.SUBJECT.hasId(patientId))
                .count(50)
                .returnBundle(Bundle.class)
                .execute();

            if (medicationsBundle != null && medicationsBundle.hasEntry()) {
                for (Bundle.BundleEntryComponent entry : medicationsBundle.getEntry()) {
                    if (entry.getResource() instanceof MedicationRequest) {
                        entries.add(createBundleEntry(entry.getResource()));
                    }
                }
                logger.debug("Added {} MedicationRequest resources to bundle", medicationsBundle.getEntry().size());
            }

            // Fetch DiagnosticReports for the patient
            Bundle diagnosticReportsBundle = fhirClient.search()
                .forResource(DiagnosticReport.class)
                .where(DiagnosticReport.SUBJECT.hasId(patientId))
                .count(30)
                .returnBundle(Bundle.class)
                .execute();

            if (diagnosticReportsBundle != null && diagnosticReportsBundle.hasEntry()) {
                for (Bundle.BundleEntryComponent entry : diagnosticReportsBundle.getEntry()) {
                    if (entry.getResource() instanceof DiagnosticReport) {
                        entries.add(createBundleEntry(entry.getResource()));
                    }
                }
                logger.debug("Added {} DiagnosticReport resources to bundle", diagnosticReportsBundle.getEntry().size());
            }

        } catch (Exception e) {
            logger.warn("Error fetching some FHIR resources for patient {}: {}", patientId, e.getMessage());
            // Continue with partial data if some resources fail
        }

        bundle.setEntry(entries);
        bundle.setTotal(entries.size());

        logger.info("Created bundle with {} entries for patient {}", entries.size(), patientId);
        return bundle;
    }

    /**
     * Create a bundle entry for a resource
     */
    private Bundle.BundleEntryComponent createBundleEntry(Resource resource) {
        Bundle.BundleEntryComponent entry = new Bundle.BundleEntryComponent();
        entry.setResource(resource);
        entry.setFullUrl(resource.getResourceType() + "/" + resource.getId());
        return entry;
    }

    /**
     * Calculate SHA-256 hash of the bundle data
     */
    private String calculateHash(String data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data.getBytes());
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) {
                    hexString.append('0');
                }
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 algorithm not available", e);
        }
    }

    /**
     * Get FHIR server status
     */
    public String getFhirServerStatus() {
        try {
            CapabilityStatement capability = fhirClient.capabilities()
                .ofType(CapabilityStatement.class)
                .execute();
            return "Connected to " + capability.getName() + " - " + capability.getStatus();
        } catch (Exception e) {
            return "Error connecting to FHIR server: " + e.getMessage();
        }
    }
}