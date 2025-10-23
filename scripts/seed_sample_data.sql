-- Seed sample prediction_results data for local testing
-- Safe to run multiple times: uses upserts on (patient_pseudo_id, prediction_timestamp)

-- Note: Requires PostgreSQL 15+ and uuid-ossp extension (already enabled in init.sql)

INSERT INTO prediction_results (
    patient_pseudo_id,
    risk_score,
    prediction_confidence,
    shap_values_json,
    feature_vector_json,
    model_version,
    prediction_timestamp
) VALUES
    (
        'PSEUDO_1001',
        0.8123,
        0.9011,
        '{"age": 0.023, "gender_male": 0.004, "heart_rate_mean": 0.051, "glucose_last": 0.034}',
        '{"patient_pseudo_id":"PSEUDO_1001","age":64,"gender_male":1,"gender_female":0,"heart_rate_mean":78.2,"systolic_bp_last":131.0,"diastolic_bp_last":82.0,"glucose_last":112.0}',
        'v1.0',
        NOW() - INTERVAL '2 days'
    ),
    (
        'PSEUDO_1002',
        0.3540,
        0.7720,
        '{"age": -0.011, "gender_female": 0.006, "heart_rate_mean": -0.008, "glucose_last": 0.012}',
        '{"patient_pseudo_id":"PSEUDO_1002","age":48,"gender_male":0,"gender_female":1,"heart_rate_mean":72.5,"systolic_bp_last":118.0,"diastolic_bp_last":76.0,"glucose_last":98.0}',
        'v1.0',
        NOW() - INTERVAL '1 days'
    ),
    (
        'PSEUDO_1003',
        0.6299,
        0.8350,
        '{"age": 0.017, "gender_male": -0.002, "heart_rate_mean": 0.026, "glucose_last": 0.019}',
        '{"patient_pseudo_id":"PSEUDO_1003","age":71,"gender_male":1,"gender_female":0,"heart_rate_mean":81.0,"systolic_bp_last":139.0,"diastolic_bp_last":86.0,"glucose_last":121.0}',
        'v1.0',
        NOW() - INTERVAL '12 hours'
    )
ON CONFLICT DO NOTHING; -- avoid duplicate rows if re-run
