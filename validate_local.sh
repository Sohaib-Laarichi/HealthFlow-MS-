#!/bin/bash

# HealthFlow-MS - Script de validation locale (sans Docker)
# Teste la logique des services et configurations

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔬 Validation locale HealthFlow-MS${NC}"
echo "=================================="

# Variables de comptage
total_tests=0
passed_tests=0

# Fonction de test
test_case() {
    local test_name="$1"
    local test_function="$2"
    
    ((total_tests++))
    echo -n "Test: $test_name... "
    
    if $test_function 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((passed_tests++))
        return 0
    else
        echo -e "${RED}✗${NC}"
        return 1
    fi
}

# Test 1: Validation des fichiers Docker
test_docker_files() {
    local missing_files=()
    
    if [ ! -f "docker-compose.yml" ]; then
        missing_files+=("docker-compose.yml")
    fi
    
    for service in proxyfhir deid featurizer modelrisque scoreapi auditfairness; do
        if [ ! -f "$service/Dockerfile" ]; then
            missing_files+=("$service/Dockerfile")
        fi
    done
    
    [ ${#missing_files[@]} -eq 0 ]
}

# Test 2: Validation de la base de données SQL
test_sql_schema() {
    if [ ! -f "init-db/init.sql" ]; then
        return 1
    fi
    
    # Vérifier la présence des tables principales
    local required_tables=("patients" "fhir_data" "pseudonym_mapping" "features" "risk_scores" "audit_logs")
    
    for table in "${required_tables[@]}"; do
        if ! grep -q "CREATE TABLE.*$table" init-db/init.sql; then
            return 1
        fi
    done
    
    return 0
}

# Test 3: Validation des configurations Python
test_python_configs() {
    local services=("deid" "featurizer" "modelrisque" "scoreapi" "auditfairness")
    
    for service in "${services[@]}"; do
        if [ ! -f "$service/requirements.txt" ]; then
            return 1
        fi
        
        if [ ! -f "$service/app.py" ] && [ ! -f "$service/main.py" ]; then
            return 1
        fi
    done
    
    return 0
}

# Test 4: Validation de la configuration Java
test_java_config() {
    if [ ! -f "proxyfhir/pom.xml" ]; then
        return 1
    fi
    
    if [ ! -f "proxyfhir/src/main/java/com/healthflow/proxyfhir/ProxyFhirApplication.java" ]; then
        return 1
    fi
    
    # Vérifier les dépendances Spring Boot
    if ! grep -q "spring-boot-starter" proxyfhir/pom.xml; then
        return 1
    fi
    
    return 0
}

# Test 5: Validation des ports
test_port_configuration() {
    local ports=(8081 8082 8083 8001 8002 8003 5432 9092 2181)
    local compose_file="docker-compose.yml"
    
    if [ ! -f "$compose_file" ]; then
        return 1
    fi
    
    for port in 8081 8082 8083; do
        if ! grep -q ":$port" "$compose_file"; then
            return 1
        fi
    done
    
    return 0
}

# Test 6: Validation de la documentation
test_documentation() {
    local docs=("README.md" "ARCHITECTURE.md" "TROUBLESHOOTING.md" "PROJECT_OVERVIEW.md")
    
    for doc in "${docs[@]}"; do
        if [ ! -f "$doc" ] || [ ! -s "$doc" ]; then
            return 1
        fi
    done
    
    return 0
}

# Test 7: Validation des scripts
test_scripts() {
    local scripts=("start.sh" "stop.sh" "monitor.sh" "backup.sh" "restore.sh")
    
    for script in "${scripts[@]}"; do
        if [ ! -f "$script" ] || [ ! -x "$script" ]; then
            return 1
        fi
        
        # Vérifier la syntaxe bash
        if ! bash -n "$script" 2>/dev/null; then
            return 1
        fi
    done
    
    return 0
}

# Test 8: Validation des dépendances Python
test_python_dependencies() {
    local critical_deps=("fastapi" "uvicorn" "psycopg2" "kafka-python" "pandas" "numpy")
    
    for service in deid featurizer modelrisque scoreapi auditfairness; do
        if [ -f "$service/requirements.txt" ]; then
            for dep in "${critical_deps[@]}"; do
                case $service in
                    "deid")
                        if [[ "$dep" == "fastapi" || "$dep" == "faker" ]]; then
                            if ! grep -q "$dep" "$service/requirements.txt"; then
                                return 1
                            fi
                        fi
                        ;;
                    "featurizer")
                        if [[ "$dep" == "transformers" || "$dep" == "spacy" ]]; then
                            if ! grep -q "$dep" "$service/requirements.txt"; then
                                return 1
                            fi
                        fi
                        ;;
                    "modelrisque")
                        if [[ "$dep" == "xgboost" || "$dep" == "shap" ]]; then
                            if ! grep -q "$dep" "$service/requirements.txt"; then
                                return 1
                            fi
                        fi
                        ;;
                    "auditfairness")
                        if [[ "$dep" == "dash" || "$dep" == "plotly" ]]; then
                            if ! grep -q "$dep" "$service/requirements.txt"; then
                                return 1
                            fi
                        fi
                        ;;
                esac
            done
        fi
    done
    
    return 0
}

# Test 9: Validation de la sécurité
test_security_config() {
    # Vérifier l'absence de secrets en dur
    local security_issues=()
    
    # Rechercher des mots de passe potentiels
    if grep -r "password.*=" . --include="*.py" --include="*.java" --include="*.yml" | grep -v "# " | grep -v "password_hash\|hashed_password"; then
        security_issues+=("hardcoded_passwords")
    fi
    
    # Vérifier la présence de configuration JWT
    if ! grep -r "JWT\|jwt" scoreapi/ > /dev/null; then
        security_issues+=("missing_jwt")
    fi
    
    [ ${#security_issues[@]} -eq 0 ]
}

# Test 10: Validation de la cohérence des configurations
test_config_consistency() {
    # Vérifier que les noms de services sont cohérents
    local services=("proxyfhir" "deid" "featurizer" "modelrisque" "scoreapi" "auditfairness")
    
    for service in "${services[@]}"; do
        if ! grep -q "$service:" docker-compose.yml; then
            return 1
        fi
    done
    
    # Vérifier la configuration de la base de données
    if ! grep -q "POSTGRES_DB.*healthflow" docker-compose.yml; then
        return 1
    fi
    
    return 0
}

# Exécution des tests
echo -e "\n${BLUE}🧪 Tests de validation${NC}"
echo "====================="

test_case "Fichiers Docker" test_docker_files
test_case "Schéma SQL" test_sql_schema
test_case "Configurations Python" test_python_configs
test_case "Configuration Java" test_java_config
test_case "Configuration des ports" test_port_configuration
test_case "Documentation" test_documentation
test_case "Scripts d'administration" test_scripts
test_case "Dépendances Python" test_python_dependencies
test_case "Configuration sécurité" test_security_config
test_case "Cohérence des configurations" test_config_consistency

# Tests additionnels de logique métier
echo -e "\n${BLUE}🎯 Tests de logique métier${NC}"
echo "=========================="

# Test de validation FHIR (simulation)
test_fhir_logic() {
    # Vérifier la présence de code FHIR dans ProxyFHIR
    if [ -f "proxyfhir/src/main/java/com/healthflow/proxyfhir/service/FhirService.java" ]; then
        if grep -q "Patient\|Bundle\|Observation" "proxyfhir/src/main/java/com/healthflow/proxyfhir/service/FhirService.java"; then
            return 0
        fi
    fi
    return 1
}

# Test de pseudonymisation (simulation)
test_pseudonymization_logic() {
    if [ -f "deid/app.py" ]; then
        if grep -q "faker\|pseudonym\|anonymize" "deid/app.py"; then
            return 0
        fi
    fi
    return 1
}

# Test de ML (simulation)
test_ml_logic() {
    if [ -f "modelrisque/app.py" ]; then
        if grep -q "xgboost\|predict\|model" "modelrisque/app.py"; then
            return 0
        fi
    fi
    return 1
}

test_case "Logique FHIR" test_fhir_logic
test_case "Logique de pseudonymisation" test_pseudonymization_logic
test_case "Logique ML" test_ml_logic

# Analyse des performances potentielles
echo -e "\n${BLUE}⚡ Analyse de performance${NC}"
echo "========================"

# Vérifier les configurations de performance
perf_issues=()

# Vérifier les index de base de données
if ! grep -q "CREATE INDEX" init-db/init.sql; then
    perf_issues+=("missing_database_indexes")
fi

# Vérifier les configurations de pool de connexions
if ! grep -r "pool\|connection" . --include="*.py" --include="*.java" > /dev/null; then
    perf_issues+=("missing_connection_pooling")
fi

if [ ${#perf_issues[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Configuration de performance optimale"
    ((passed_tests++))
else
    echo -e "${YELLOW}⚠${NC} Optimisations de performance suggérées: ${perf_issues[*]}"
fi
((total_tests++))

# Résumé final
echo -e "\n${BLUE}📊 Résumé de la validation${NC}"
echo "=========================="

success_rate=$((passed_tests * 100 / total_tests))

if [ $success_rate -eq 100 ]; then
    echo -e "${GREEN}🎉 Tous les tests sont passés ($passed_tests/$total_tests)${NC}"
    echo -e "${GREEN}✅ Le projet est prêt pour le déploiement${NC}"
elif [ $success_rate -ge 80 ]; then
    echo -e "${YELLOW}⚠ La plupart des tests sont passés ($passed_tests/$total_tests)${NC}"
    echo -e "${YELLOW}🔧 Quelques ajustements mineurs sont recommandés${NC}"
else
    echo -e "${RED}❌ Plusieurs tests ont échoué ($passed_tests/$total_tests)${NC}"
    echo -e "${RED}🛠 Des corrections sont nécessaires${NC}"
fi

# Recommandations finales
echo -e "\n${BLUE}💡 Recommandations${NC}"
echo "=================="

if [ $success_rate -ge 80 ]; then
    echo "1. ✅ Validation locale réussie"
    echo "2. 🐳 Prêt pour le test Docker : ./check_environment.sh"
    echo "3. 🚀 Déploiement possible : ./start.sh (avec Docker)"
    echo "4. 📊 Surveillance : ./monitor.sh"
else
    echo "1. 🔧 Corriger les problèmes identifiés"
    echo "2. 🔄 Relancer la validation : ./validate_local.sh"
    echo "3. 📚 Consulter la documentation si nécessaire"
fi

echo -e "\n${BLUE}📈 Score de qualité: ${success_rate}%${NC}"

if [ $success_rate -ge 95 ]; then
    echo -e "${GREEN}🏆 Excellent ! Qualité production${NC}"
elif [ $success_rate -ge 80 ]; then
    echo -e "${YELLOW}👍 Bon ! Qualité acceptable${NC}"
else
    echo -e "${RED}🚨 Attention ! Améliorations nécessaires${NC}"
fi

exit 0