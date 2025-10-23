-- HealthFlow-MS Database Schema
-- Initialization script for PostgreSQL

-- Extension pour UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table pour stocker les Bundles FHIR bruts
CREATE TABLE fhir_bundles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id VARCHAR(255) NOT NULL,
    bundle_type VARCHAR(100) NOT NULL DEFAULT 'Patient',
    bundle_data JSONB NOT NULL,
    original_data_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour optimiser les recherches par patient_id
CREATE INDEX idx_fhir_bundles_patient_id ON fhir_bundles(patient_id);
CREATE INDEX idx_fhir_bundles_created_at ON fhir_bundles(created_at);
CREATE INDEX idx_fhir_bundles_bundle_type ON fhir_bundles(bundle_type);

-- Table de mapping pour la pseudonymisation (DeID)
CREATE TABLE pseudonym_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_identifier VARCHAR(500) NOT NULL,
    pseudonym_identifier VARCHAR(500) NOT NULL,
    identifier_type VARCHAR(100) NOT NULL, -- 'patient_id', 'practitioner_id', 'organization_id', etc.
    salt_used VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index unique pour éviter les doublons et optimiser les lookups
CREATE UNIQUE INDEX idx_pseudonym_original ON pseudonym_mapping(original_identifier, identifier_type);
CREATE INDEX idx_pseudonym_pseudo ON pseudonym_mapping(pseudonym_identifier);

-- Table pour stocker les résultats de prédiction (ModelRisque -> ScoreAPI)
CREATE TABLE prediction_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_pseudo_id VARCHAR(255) NOT NULL,
    risk_score DECIMAL(5,4) NOT NULL CHECK (risk_score >= 0.0 AND risk_score <= 1.0),
    prediction_confidence DECIMAL(5,4),
    shap_values_json JSONB,
    feature_vector_json JSONB,
    model_version VARCHAR(50) DEFAULT 'v1.0',
    prediction_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour optimiser les recherches par patient et date
CREATE INDEX idx_prediction_patient_id ON prediction_results(patient_pseudo_id);
CREATE INDEX idx_prediction_timestamp ON prediction_results(prediction_timestamp);
CREATE INDEX idx_prediction_score ON prediction_results(risk_score);

-- Table pour l'audit et les logs (AuditFairness)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    operation_type VARCHAR(100) NOT NULL, -- 'ingestion', 'anonymization', 'prediction', etc.
    patient_pseudo_id VARCHAR(255),
    operation_metadata JSONB,
    execution_time_ms INTEGER,
    status VARCHAR(50) DEFAULT 'success', -- 'success', 'error', 'warning'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour l'audit et le monitoring
CREATE INDEX idx_audit_service_name ON audit_logs(service_name);
CREATE INDEX idx_audit_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_status ON audit_logs(status);
CREATE INDEX idx_audit_patient_id ON audit_logs(patient_pseudo_id);

-- Table pour stocker les métriques de performance des modèles
CREATE TABLE model_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_version VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL, -- 'accuracy', 'auc_roc', 'fairness_demographic_parity', etc.
    metric_value DECIMAL(10,6) NOT NULL,
    population_segment VARCHAR(100), -- 'all', 'age_65+', 'gender_female', etc.
    calculation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Index pour les métriques
CREATE INDEX idx_model_metrics_version ON model_metrics(model_version);
CREATE INDEX idx_model_metrics_name ON model_metrics(metric_name);
CREATE INDEX idx_model_metrics_date ON model_metrics(calculation_date);

-- Table pour les configurations système
CREATE TABLE system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(255) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Configurations par défaut
INSERT INTO system_config (config_key, config_value, description) VALUES
('fhir.server.base_url', 'https://hapi.fhir.org/baseR4', 'URL de base du serveur FHIR externe'),
('model.version.current', 'v1.0', 'Version actuelle du modèle de risque'),
('anonymization.salt.default', 'healthflow-salt-2024', 'Salt par défaut pour la pseudonymisation'),
('feature.extraction.enabled_models', '["biobert", "spacy_sci"]', 'Modèles NLP activés'),
('api.rate_limit.requests_per_minute', '100', 'Limite de requêtes par minute pour ScoreAPI'),
('audit.retention.days', '365', 'Durée de rétention des logs d''audit en jours');

-- Fonction pour mettre à jour automatiquement updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at
CREATE TRIGGER update_fhir_bundles_updated_at BEFORE UPDATE ON fhir_bundles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Vue pour les dernières prédictions par patient
CREATE VIEW latest_predictions AS
SELECT DISTINCT ON (patient_pseudo_id) 
    patient_pseudo_id,
    risk_score,
    prediction_confidence,
    shap_values_json,
    model_version,
    prediction_timestamp
FROM prediction_results
ORDER BY patient_pseudo_id, prediction_timestamp DESC;

-- Vue pour les statistiques d'audit par service
CREATE VIEW service_stats AS
SELECT 
    service_name,
    COUNT(*) as total_operations,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_operations,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_operations,
    AVG(execution_time_ms) as avg_execution_time_ms,
    MAX(created_at) as last_operation
FROM audit_logs
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY service_name;

-- Commentaires pour la documentation
COMMENT ON TABLE fhir_bundles IS 'Stockage des données FHIR brutes avec métadonnées de traçabilité';
COMMENT ON TABLE pseudonym_mapping IS 'Table de mapping pour la pseudonymisation des identifiants';
COMMENT ON TABLE prediction_results IS 'Résultats des prédictions de risque avec explicabilité SHAP';
COMMENT ON TABLE audit_logs IS 'Logs d''audit pour toutes les opérations du système';
COMMENT ON TABLE model_metrics IS 'Métriques de performance et d''équité des modèles ML';
COMMENT ON TABLE system_config IS 'Configuration système centralisée';

-- Afficher un message de confirmation
DO $$
BEGIN
    RAISE NOTICE 'HealthFlow-MS database schema initialized successfully!';
    RAISE NOTICE 'Tables created: fhir_bundles, pseudonym_mapping, prediction_results, audit_logs, model_metrics, system_config';
    RAISE NOTICE 'Views created: latest_predictions, service_stats';
END $$;