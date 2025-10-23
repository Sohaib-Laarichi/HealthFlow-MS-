# 🏥 HealthFlow-MS

**Plateforme intelligente d'analyse de risque médical basée sur des microservices**

[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.2-green.svg)](https://spring.io/projects/spring-boot)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-Event%20Streaming-orange.svg)](https://kafka.apache.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🗺️ Vue d'ensemble

HealthFlow-MS est une plateforme MLOps complète conçue pour l'analyse de risque médical en temps réel. Elle traite les données FHIR R4, applique des algorithmes d'intelligence artificielle pour prédire les risques de santé, et fournit des explications interprétables pour soutenir les décisions cliniques.

### 🎯 Objectifs principaux

- **Ingestion FHIR** : Traitement standardisé des données médicales
- **Pseudonymisation** : Protection de la vie privée conforme HIPAA/GDPR
- **IA Médicale** : Prédiction de risques avec modèles XGBoost et BioBERT
- **Explicabilité** : Visualisations SHAP pour l'interprétabilité des modèles
- **Monitoring** : Surveillance de la dérive des données et de l'équité des algorithmes

## 🆕 Mises à jour récentes (2025-10)

- Docker Compose: commandes mises à jour vers `docker compose` (v2) et ajout de `--build` lors du premier lancement.
- Kafka: configuration d’écouteurs annoncés corrigée pour un fonctionnement inter-conteneurs (`PLAINTEXT://kafka:9092, PLAINTEXT_HOST://localhost:9094`).
- ProxyFHIR: image runtime durcie, healthcheck via Actuator, et client FHIR initialisé au démarrage.
- ScoreAPI: healthcheck basé sur curl dans le conteneur, docs disponibles sur `/docs`.
- AuditFairness: design modernisé (thème Bootstrap Minty, navbar, cartes, loaders, footer).
- Dépendances Python: corrections mineures (evidently compatible Pydantic v2, renommage `python-dateutil`, suppression d’entrées stdlib erronées).

Voir TROUBLESHOOTING.md pour les conseils de débogage courants.

## 🏗️ Architecture du Système

### Architecture Microservices Event-Driven

```mermaid
graph TB
    FHIR[Serveur FHIR Externe] --> ProxyFHIR[ProxyFHIR Service]
    ProxyFHIR --> PostgreSQL[(PostgreSQL)]
    ProxyFHIR --> Kafka1[fhir.data.raw]
    
    Kafka1 --> DeID[DeID Service]
    DeID --> PostgreSQL
    DeID --> Kafka2[fhir.data.anonymized]
    
    Kafka2 --> Featurizer[Featurizer Service]
    Featurizer --> Kafka3[features.patient.ready]
    
    Kafka3 --> ModelRisque[ModelRisque Service]
    ModelRisque --> PostgreSQL
    ModelRisque --> Kafka4[risk.score.calculated]
    
    PostgreSQL --> ScoreAPI[ScoreAPI Service]
    PostgreSQL --> AuditFairness[AuditFairness Dashboard]
    
    ScoreAPI --> WebApp[Applications Cliniques]
    AuditFairness --> DataScientist[Data Scientists]
```

### 📊 Flux de Données

1. **ProxyFHIR** → Ingestion des données FHIR et publication dans `fhir.data.raw`
2. **DeID** → Consommation, anonymisation et publication dans `fhir.data.anonymized`
3. **Featurizer** → Extraction NLP/stats et publication dans `features.patient.ready`
4. **ModelRisque** → Prédiction ML et stockage en base + publication d'alertes
5. **ScoreAPI** → Exposition REST sécurisée des résultats
6. **AuditFairness** → Monitoring continu de l'équité et dérive

## 🚀 Démarrage Rapide

### Prérequis

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- 20GB espace disque

### Installation

1. **Cloner le repository**
```bash
git clone https://github.com/your-org/HealthFlow-MS.git
cd HealthFlow-MS
```

2. **Lancer l'environnement complet**
```bash
docker compose up -d --build
```

3. **Vérifier le statut des services**
```bash
docker compose ps
```

4. **Accéder aux interfaces**
- **ScoreAPI Documentation** : http://localhost:8082/docs
- **AuditFairness Dashboard** : http://localhost:8083
- **DataManager (gestion des données)** : http://localhost:8084/docs
- **ProxyFHIR Health** : http://localhost:8081/api/v1/fhir/health

## 🔗 Liens utiles

- Frontends et APIs
  - AuditFairness Dashboard: http://localhost:8083
  - DataManager (CRUD des données): http://localhost:8084/docs
  - ScoreAPI OpenAPI Docs: http://localhost:8082/docs
  - ScoreAPI ReDoc: http://localhost:8082/redoc
  - ScoreAPI Health: http://localhost:8082/health
  - ProxyFHIR Health: http://localhost:8081/api/v1/fhir/health
  - ProxyFHIR Actuator (health): http://localhost:8081/actuator/health
  - ProxyFHIR Prometheus metrics: http://localhost:8081/actuator/prometheus

- Infrastructure
  - Kafka (interne, pour services): kafka:9092
  - Kafka (hôte, pour tests locaux): localhost:9094
  - Kafka Topics: `fhir.data.raw`, `fhir.data.anonymized`, `features.patient.ready`, `risk.score.calculated`
  - PostgreSQL: postgres:5432 (hôte: localhost:5432)
  - Base de données: healthflow | Utilisateur: healthflow | Mot de passe: healthflow123

- Documentation
  - README (présent document)
  - Dépannage: TROUBLESHOOTING.md
  - Vue d’ensemble: PROJECT_OVERVIEW.md
  - État du projet: PROJECT_STATUS.md

## 📡 Données du dashboard depuis HAPI FHIR

Pour que le dashboard affiche des données réelles issues de HAPI FHIR (https://hapi.fhir.org/baseR4/), suivez ces étapes:

1) Démarrer la stack
- docker compose up -d --build

2) Désactiver le mode démo du dashboard (déjà configuré par défaut)
- Le service AuditFairness est lancé avec DASH_DEMO_MODE=0 dans docker-compose.yml, il n'affichera donc que les données réelles présentes en base.

3) Ingérer un patient réel depuis HAPI FHIR
- Choisir un Patient ID valide visible sur https://hapi.fhir.org/baseR4
- Lancer l'ingestion via ProxyFHIR:
  - curl -X POST http://localhost:8081/api/v1/fhir/sync/patient/<PATIENT_ID>

4) Laisser le pipeline traiter
- DeID anonymise → Featurizer extrait les features → ModelRisque calcule le score et écrit dans PostgreSQL (prediction_results).
- Suivre les logs si besoin:
  - docker compose logs -f deid featurizer modelrisque

5) Consulter les résultats
- ScoreAPI: http://localhost:8082/docs (GET /api/v1/score/{patient_pseudo_id})
- Dashboard: http://localhost:8083 (les graphiques doivent refléter les données réelles)

Astuce: si aucune donnée n’apparaît, vérifiez que le Patient ID existe bien sur HAPI et patientez quelques instants le temps que le pipeline termine le traitement.

## ♻️ Voir le nouveau dashboard (rebuild)

Si vous avez modifié le code du dashboard AuditFairness et que l’interface ne reflète pas les changements, reconstruisez uniquement ce service sans cache puis redémarrez-le.

Commandes rapides:
```bash
# Depuis la racine du repo
docker compose build --no-cache auditfairness
docker compose up -d auditfairness
```

Ou utilisez le script d’aide:
```bash
bash scripts/rebuild_dashboard.sh
```

Astuces:
- Rafraîchissez le navigateur avec un hard‑reload (Ctrl+F5) pour éviter le cache.
- Consultez les logs du service pour vérifier le démarrage:
  ```bash
  docker compose logs -f --tail=100 auditfairness
  ```
- Si des dépendances Python ont changé, exécutez la reconstruction complète au premier essai.

### 🧪 Test du Pipeline Complet

1. **Obtenir un token d'authentification**
```bash
curl -X POST http://localhost:8082/auth/token
```

2. **Ingérer des données FHIR**
```bash
curl -X POST http://localhost:8081/api/v1/fhir/sync/patient/123 \
  -H "Content-Type: application/json"
```

3. **Vérifier le score de risque** (après quelques minutes)
```bash
curl -X GET http://localhost:8082/api/v1/score/PATIENT_XXXXXX \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. **Accéder aux explications**
```bash
curl -X GET http://localhost:8082/api/v1/explain/PATIENT_XXXXXX \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📋 Services Détaillés

### 1. ProxyFHIR (Java/Spring Boot)

**Port** : 8081 | **Responsabilité** : Ingestion FHIR

#### Endpoints Principaux
- `POST /api/v1/fhir/sync/patient/{id}` - Synchroniser un patient
- `POST /api/v1/fhir/sync/patients` - Synchronisation batch
- `GET /api/v1/fhir/health` - Health check

#### Configuration
```properties
# application.properties
fhir.server.base-url=https://hapi.fhir.org/baseR4
spring.datasource.url=jdbc:postgresql://postgres:5432/healthflow
spring.kafka.bootstrap-servers=kafka:9092
```

### 2. DeID (Python)

**Responsabilité** : Anonymisation des données FHIR

#### Fonctionnalités
- Pseudonymisation cohérente avec Faker
- Mapping persistant des identifiants
- Support FHIR R4 complet
- Préservation de la structure des données

#### Variables d'Environnement
```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
POSTGRES_HOST=postgres
DEID_SALT=healthflow-deid-salt-2024
```

### 3. Featurizer (Python/NLP)

**Responsabilité** : Extraction de features médicales

#### Technologies Utilisées
- **BioBERT** : Embeddings contextuels médicaux
- **spaCy sci** : Entités médicales nommées
- **Statistiques** : Agrégation des signes vitaux
- **Features temporelles** : Tendances et évolutions

#### Features Extraites
- Démographiques (âge, genre, statut marital)
- Conditions médicales (comptages par catégorie)
- Médicaments (classes thérapeutiques)
- Signes vitaux (moyennes, tendances, valeurs récentes)
- Entités NLP (symptômes, maladies, traitements)
- Embeddings BioBERT (représentation sémantique)

### 4. ModelRisque (Python/ML)

**Responsabilité** : Prédiction de risque avec explicabilité

#### Modèle ML
- **Algorithme** : XGBoost Classifier
- **Explicabilité** : SHAP TreeExplainer
- **Métriques** : Score de risque (0-1) + niveau de confiance
- **Catégories** : LOW, MODERATE, HIGH, CRITICAL

#### Pipeline de Prédiction
1. Préparation du vecteur de features
2. Normalisation avec StandardScaler
3. Prédiction XGBoost
4. Calcul des valeurs SHAP
5. Génération d'explications textuelles
6. Persistance en base de données

### 5. ScoreAPI (Python/FastAPI)

**Port** : 8082 | **Responsabilité** : API REST sécurisée

#### Sécurité
- **Authentification** : JWT Bearer tokens
- **Autorisation** : Middleware de vérification
- **CORS** : Configuration pour applications web
- **Rate Limiting** : Protection contre les abus

#### Endpoints API

##### Authentification
```bash
POST /auth/token
```
**Réponse** :
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

##### Score de Risque
```bash
GET /api/v1/score/{patient_pseudo_id}
Authorization: Bearer {token}
```
**Réponse** :
```json
{
  "patient_pseudo_id": "PATIENT_123456",
  "risk_score": 0.75,
  "prediction_confidence": 0.89,
  "risk_level": "HIGH",
  "model_version": "v1.0",
  "prediction_timestamp": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-15T10:30:05Z"
}
```

##### Explications SHAP
```bash
GET /api/v1/explain/{patient_pseudo_id}
Authorization: Bearer {token}
```
**Réponse** :
```json
{
  "patient_pseudo_id": "PATIENT_123456",
  "risk_score": 0.75,
  "shap_values": {
    "age": 0.12,
    "total_conditions": 0.08,
    "heart_rate_mean": 0.05
  },
  "top_risk_factors": ["age", "total_conditions", "heart_rate_mean"],
  "explanation_text": "Key risk factors: Age increases risk (impact: 0.120); Total Conditions increases risk (impact: 0.080)",
  "model_version": "v1.0",
  "prediction_timestamp": "2024-01-15T10:30:00Z"
}
```

##### Statistiques
```bash
GET /api/v1/statistics/summary
GET /api/v1/scores/recent?limit=50
GET /api/v1/scores/high-risk?threshold=0.7
```

### 6. AuditFairness (Python/Dash)

**Port** : 8083 | **Responsabilité** : Dashboard de monitoring

#### Fonctionnalités de Monitoring

##### Métriques d'Équité
- **Disparate Impact** : Ratio des taux de risque élevé par groupe démographique
- **Equal Opportunity** : Égalité des vrais positifs
- **Demographic Parity** : Distribution équitable des prédictions

##### Détection de Dérive
- **Data Drift** : Évolution des distributions de features
- **Concept Drift** : Changement des relations input-output
- **Population Shift** : Modification des caractéristiques démographiques

##### Visualisations
- Distribution des scores de risque
- Tendances temporelles
- Analyse par groupes démographiques
- Rapports de dérive EvidentlyAI

## 🗄️ Base de Données PostgreSQL

### Schéma Principal

#### Table `fhir_bundles`
```sql
CREATE TABLE fhir_bundles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id VARCHAR(255) NOT NULL,
    bundle_type VARCHAR(100) NOT NULL DEFAULT 'Patient',
    bundle_data JSONB NOT NULL,
    original_data_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### Table `pseudonym_mapping`
```sql
CREATE TABLE pseudonym_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_identifier VARCHAR(500) NOT NULL,
    pseudonym_identifier VARCHAR(500) NOT NULL,
    identifier_type VARCHAR(100) NOT NULL,
    salt_used VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### Table `prediction_results`
```sql
CREATE TABLE prediction_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_pseudo_id VARCHAR(255) NOT NULL,
    risk_score DECIMAL(5,4) NOT NULL CHECK (risk_score >= 0.0 AND risk_score <= 1.0),
    prediction_confidence DECIMAL(5,4),
    shap_values_json JSONB,
    feature_vector_json JSONB,
    model_version VARCHAR(50) DEFAULT 'v1.0',
    prediction_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### Table `audit_logs`
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    operation_type VARCHAR(100) NOT NULL,
    patient_pseudo_id VARCHAR(255),
    operation_metadata JSONB,
    execution_time_ms INTEGER,
    status VARCHAR(50) DEFAULT 'success',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 Configuration et Personnalisation

### Variables d'Environnement Importantes

#### Sécurité
```bash
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
DEID_SALT=healthflow-deid-salt-2024
```

#### Connexions Base de Données
```bash
POSTGRES_HOST=postgres
POSTGRES_DB=healthflow
POSTGRES_USER=healthflow
POSTGRES_PASSWORD=healthflow123
```

#### Kafka
```bash
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

#### Serveur FHIR
```bash
FHIR_SERVER_BASE_URL=https://hapi.fhir.org/baseR4
```

### Personnalisation du Modèle ML

Pour utiliser votre propre modèle :

1. **Entraîner le modèle** avec vos données
2. **Sauvegarder les artifacts** :
   ```python
   # Sauvegarder le modèle XGBoost
   model.save_model('/path/to/model.xgb')
   
   # Sauvegarder l'explainer SHAP
   with open('/path/to/explainer.pkl', 'wb') as f:
       pickle.dump(explainer, f)
   
   # Sauvegarder le scaler
   with open('/path/to/scaler.pkl', 'wb') as f:
       pickle.dump(scaler, f)
   ```

3. **Monter les fichiers** dans le conteneur ModelRisque
4. **Mettre à jour** la configuration du modèle

### Configuration des Features NLP

Pour personnaliser l'extraction de features :

1. **Modifier les concepts médicaux** dans `featurizer/app/main.py`
2. **Ajouter de nouveaux modèles** NLP
3. **Personnaliser les features** démographiques et cliniques

## 📊 Monitoring et Observabilité

### Métriques Disponibles

#### Métriques Métier
- Nombre de prédictions par jour
- Distribution des scores de risque
- Taux de patients à haut risque
- Temps de traitement par patient

#### Métriques Techniques
- Latence des APIs
- Throughput Kafka
- Utilisation CPU/Mémoire
- Erreurs par service

#### Métriques de Qualité ML
- Dérive des données d'entrée
- Stabilité des prédictions
- Métriques d'équité
- Confidence des prédictions

### Alerting

Le système génère des alertes pour :
- Patients à risque critique (score > 0.8)
- Dérive de données détectée
- Biais démographiques identifiés
- Erreurs système critiques

## 🔒 Sécurité et Conformité

### Anonymisation des Données

- **Pseudonymisation** : Remplacement cohérent des identifiants
- **Suppression** : Élimination des adresses et contacts
- **Hachage** : Protection cryptographique des mappings
- **Audit Trail** : Traçabilité complète des transformations

### Conformité RGPD/HIPAA

- **Privacy by Design** : Anonymisation dès l'ingestion
- **Data Minimization** : Collecte uniquement des données nécessaires
- **Right to be Forgotten** : Capacité de suppression
- **Access Control** : Authentification et autorisation

### Sécurité API

- **JWT Authentication** : Tokens signés et expirables
- **HTTPS Only** : Chiffrement en transit
- **Rate Limiting** : Protection contre les abus
- **Input Validation** : Validation stricte des entrées

## 🧪 Tests et Validation

### Tests Fonctionnels

```bash
# Test du pipeline complet
./scripts/test_pipeline.sh

# Test des APIs
./scripts/test_apis.sh

# Test de charge
./scripts/load_test.sh
```

### Validation du Modèle

```bash
# Métriques de performance
./scripts/validate_model.sh

# Tests d'équité
./scripts/fairness_test.sh

# Tests de robustesse
./scripts/robustness_test.sh
```

## 🔧 Dépannage

### Problèmes Courants

#### Services qui ne démarrent pas
```bash
# Vérifier les logs
docker-compose logs [service-name]

# Redémarrer un service
docker-compose restart [service-name]

# Reconstruire les images
docker-compose build [service-name]
```

#### Problèmes de connectivité Kafka
```bash
# Vérifier les topics
docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Vérifier les consumers
docker-compose exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --list
```

#### Problèmes de base de données
```bash
# Connexion à PostgreSQL
docker-compose exec postgres psql -U healthflow -d healthflow

# Vérifier les tables
\dt

# Vérifier les données
SELECT COUNT(*) FROM prediction_results;
```

### Logs et Debugging

Les logs sont disponibles via :
```bash
# Logs en temps réel
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f proxyfhir

# Logs avec timestamp
docker-compose logs -t
```

## 📈 Performance et Scalabilité

### Optimisations Recommandées

#### Production Ready
1. **Load Balancer** : HAProxy ou NGINX
2. **Database Cluster** : PostgreSQL HA
3. **Kafka Cluster** : Multi-broker setup
4. **Monitoring** : Prometheus + Grafana
5. **Logging** : ELK Stack

#### Scaling Horizontal
```bash
# Mise à l'échelle avec Docker Compose v2 (exemples)
docker compose up -d --scale featurizer=3
docker compose up -d --scale modelrisque=2
docker compose up -d --scale scoreapi=3
```

#### Optimisations Kafka
- Partitioning par patient_id
- Compression des messages
- Batch processing
- Consumer groups dédiés

## 🤝 Contribution

### Structure du Projet

```
HealthFlow-MS/
├── docker-compose.yml          # Infrastructure complète
├── init-db/
│   └── init.sql               # Schémas PostgreSQL
├── proxyfhir/                 # Service Java/Spring Boot
│   ├── src/main/java/         # Code source Java
│   ├── pom.xml               # Dépendances Maven
│   └── Dockerfile            # Image Docker
├── deid/                     # Service Python d'anonymisation
│   ├── app/main.py          # Logic principale
│   ├── requirements.txt     # Dépendances Python
│   └── Dockerfile           # Image Docker
├── featurizer/              # Service d'extraction NLP
│   ├── app/main.py         # Extraction de features
│   ├── requirements.txt    # Dépendances ML/NLP
│   └── Dockerfile          # Image Docker
├── modelrisque/            # Service de prédiction ML
│   ├── app/main.py        # Modèle XGBoost + SHAP
│   ├── model/             # Artifacts du modèle
│   ├── requirements.txt   # Dépendances ML
│   └── Dockerfile         # Image Docker
├── scoreapi/              # API REST FastAPI
│   ├── app/main.py       # Endpoints sécurisés
│   ├── requirements.txt  # Dépendances API
│   └── Dockerfile        # Image Docker
├── auditfairness/        # Dashboard Dash
│   ├── app/dashboard.py  # Interface de monitoring
│   ├── requirements.txt  # Dépendances dashboard
│   └── Dockerfile        # Image Docker
└── README.md             # Documentation complète
```

### Guidelines de Développement

1. **Code Quality** : Tests unitaires obligatoires
2. **Documentation** : Docstrings et commentaires
3. **Security** : Scan des vulnérabilités
4. **Performance** : Profiling des services critiques

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙋‍♂️ Support

### Documentation Supplémentaire
- [Architecture Decision Records](docs/adr/)
- [API Documentation](docs/api/)
- [Deployment Guide](docs/deployment/)
- [Troubleshooting Guide](docs/troubleshooting/)

### Contacts
- **Équipe Technique** : tech-team@healthflow.com
- **Support** : support@healthflow.com
- **Sécurité** : security@healthflow.com

---

**HealthFlow-MS** - *Transforming Healthcare through Intelligent Risk Assessment*


## ❓ Où insérer des données ? (Where to insert data)

Selon votre besoin, il existe trois façons d’alimenter le système:

1) Chemin recommandé (réaliste) — via ProxyFHIR et le serveur FHIR public
- Objectif: Ingestion FHIR réelle puis pipeline EDA (Kafka) jusqu’aux scores.
- Étapes:
  - Démarrer la stack: docker compose up -d --build
  - Choisir un Patient ID valide depuis https://hapi.fhir.org/baseR4 (ex. un id que vous voyez via l’UI HAPI)
  - Ingestion: curl -X POST http://localhost:8081/api/v1/fhir/sync/patient/<PATIENT_ID>
  - Le service ProxyFHIR écrit le bundle brut dans PostgreSQL (table fhir_bundles) et publie un message dans Kafka (fhir.data.raw).
  - DeID, Featurizer, ModelRisque consomment en chaîne et finissent par écrire les résultats dans prediction_results.

2) Chemin développeur — via Kafka (pipeline simulé)
- Objectif: Tester une partie du pipeline sans le FHIR externe.
- Référence: scripts/test_pipeline.sh (exemple de test bout‑à‑bout). Vous pouvez publier manuellement dans les topics Kafka si nécessaire.
- Kafka interne pour les services: kafka:9092 (hôte: localhost:9094)
- Topics clés: fhir.data.raw → fhir.data.anonymized → features.patient.ready → risk.score.calculated

3) Chemin rapide (démo/UX) — injection directe en base
- Objectif: Voir immédiatement des scores dans ScoreAPI et des graphiques dans le dashboard sans attendre le pipeline.
- Commande:
  - bash scripts/seed_sample_data.sh
- Ce script insère quelques lignes réalistes dans la table prediction_results.
- Vérification rapide:
  - docker compose exec postgres psql -U healthflow -d healthflow -c "SELECT patient_pseudo_id, risk_score, prediction_timestamp FROM prediction_results ORDER BY prediction_timestamp DESC LIMIT 10;"
- Ensuite:
  - ScoreAPI: http://localhost:8082/docs (GET /api/v1/score/{patient_pseudo_id})
  - Dashboard: http://localhost:8083 (mettre DASH_DEMO_MODE=0 dans docker-compose.yml pour désactiver le mode démo)

Notes importantes
- fhir_bundles (brut) est alimentée uniquement par ProxyFHIR. N’insérez pas directement des bundles bruts sauf cas de test contrôlé.
- prediction_results est la table lue par ScoreAPI et AuditFairness. Pour des démonstrations rapides, l’injection directe via scripts/seed_sample_data.sh est la plus simple.
- Sécurité: ScoreAPI requiert un JWT pour les endpoints protégés. Générez un token via POST /auth/token (voir section « Test du Pipeline Complet » ci‑dessus).


## 🧰 Gestion des nouvelles données (DataManager)

Le service DataManager permet d’ajouter, modifier, supprimer et lister des résultats de prédiction, ainsi que de déclencher l’ingestion FHIR manuellement.

- UI de documentation: http://localhost:8084/docs
- Port conteneur: 8001 (exposé en 8084 côté hôte)

Endpoints clés (tous protégés par JWT):
- POST /auth/token → génère un token de développement (à utiliser en Authorization: Bearer ...)
- POST /api/v1/predictions → créer une ligne dans prediction_results
- GET /api/v1/predictions → lister
- GET /api/v1/predictions/{id} → récupérer par id
- PUT /api/v1/predictions/{id} → mettre à jour
- DELETE /api/v1/predictions/{id} → supprimer
- POST /api/v1/ingest/patient/{patient_id} → relayer une ingestion vers ProxyFHIR

Exemples rapides:
```bash
# 1) Obtenir un token (dev)
TOKEN=$(curl -s -X POST http://localhost:8084/auth/token | jq -r .access_token)

# 2) Créer un résultat de prédiction
curl -s -X POST http://localhost:8084/api/v1/predictions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_pseudo_id": "PSEUDO_DEMO_1",
    "risk_score": 0.73,
    "prediction_confidence": 0.85,
    "shap_values_json": {"age": 0.02, "heart_rate_mean": 0.04},
    "feature_vector_json": {"age": 67, "heart_rate_mean": 82},
    "model_version": "v1.0"
  }'

# 3) Vérifier via ScoreAPI (utiliser le token ScoreAPI si configuré)
curl -s http://localhost:8082/docs

# 4) Voir dans le dashboard (mettre DASH_DEMO_MODE=0 pour afficher uniquement les données réelles)
open http://localhost:8083
```

Sécurité: en production, configurez un SECRET distinct (JWT_SECRET_KEY) et désactivez l’endpoint /auth/token. 
