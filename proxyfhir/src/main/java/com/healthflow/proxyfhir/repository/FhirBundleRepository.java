package com.healthflow.proxyfhir.repository;

import com.healthflow.proxyfhir.entity.FhirBundle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface FhirBundleRepository extends JpaRepository<FhirBundle, UUID> {

    /**
     * Find the latest bundle for a specific patient
     */
    Optional<FhirBundle> findTopByPatientIdOrderByCreatedAtDesc(String patientId);

    /**
     * Find all bundles for a specific patient
     */
    List<FhirBundle> findByPatientIdOrderByCreatedAtDesc(String patientId);

    /**
     * Find bundles by type
     */
    List<FhirBundle> findByBundleTypeOrderByCreatedAtDesc(String bundleType);

    /**
     * Find bundles created after a specific date
     */
    List<FhirBundle> findByCreatedAtAfterOrderByCreatedAtDesc(LocalDateTime createdAfter);

    /**
     * Check if a bundle with specific hash already exists (to avoid duplicates)
     */
    boolean existsByOriginalDataHash(String originalDataHash);

    /**
     * Count bundles by patient
     */
    @Query("SELECT COUNT(f) FROM FhirBundle f WHERE f.patientId = :patientId")
    long countByPatientId(@Param("patientId") String patientId);

    /**
     * Find recent bundles for processing (used by scheduled jobs)
     */
    @Query("SELECT f FROM FhirBundle f WHERE f.createdAt >= :since ORDER BY f.createdAt ASC")
    List<FhirBundle> findRecentBundles(@Param("since") LocalDateTime since);
}