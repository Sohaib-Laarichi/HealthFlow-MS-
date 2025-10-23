package com.healthflow.proxyfhir.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.Type;
import org.hibernate.annotations.UuidGenerator;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "fhir_bundles")
public class FhirBundle {

    @Id
    @UuidGenerator
    @Column(name = "id")
    private UUID id;

    @Column(name = "patient_id", nullable = false)
    private String patientId;

    @Column(name = "bundle_type", nullable = false)
    private String bundleType = "Patient";

    @Column(name = "bundle_data", nullable = false, columnDefinition = "jsonb")
    private String bundleData;

    @Column(name = "original_data_hash")
    private String originalDataHash;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    // Constructors
    public FhirBundle() {}

    public FhirBundle(String patientId, String bundleType, String bundleData, String originalDataHash) {
        this.patientId = patientId;
        this.bundleType = bundleType;
        this.bundleData = bundleData;
        this.originalDataHash = originalDataHash;
    }

    // Getters and Setters
    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public String getPatientId() {
        return patientId;
    }

    public void setPatientId(String patientId) {
        this.patientId = patientId;
    }

    public String getBundleType() {
        return bundleType;
    }

    public void setBundleType(String bundleType) {
        this.bundleType = bundleType;
    }

    public String getBundleData() {
        return bundleData;
    }

    public void setBundleData(String bundleData) {
        this.bundleData = bundleData;
    }

    public String getOriginalDataHash() {
        return originalDataHash;
    }

    public void setOriginalDataHash(String originalDataHash) {
        this.originalDataHash = originalDataHash;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}