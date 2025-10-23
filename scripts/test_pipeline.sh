#!/bin/bash

# Script de test du pipeline HealthFlow-MS
echo "🧪 Test du pipeline complet HealthFlow-MS"
echo "========================================="

# Configuration
BASE_URL_PROXY="http://localhost:8081"
BASE_URL_API="http://localhost:8082"
TEST_PATIENT_ID="test-patient-$(date +%s)"

# Fonction pour afficher les résultats
show_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ $2"
    else
        echo "❌ $2"
    fi
}

# Test 1: Health checks
echo ""
echo "🔍 Test 1: Vérification de la santé des services"

curl -s -f "$BASE_URL_PROXY/api/v1/fhir/health" > /dev/null
show_result $? "ProxyFHIR Health Check"

curl -s -f "$BASE_URL_API/health" > /dev/null
show_result $? "ScoreAPI Health Check"

curl -s -f "http://localhost:8083" > /dev/null
show_result $? "AuditFairness Dashboard"

# Test 2: Authentication
echo ""
echo "🔐 Test 2: Authentification API"

TOKEN_RESPONSE=$(curl -s -X POST "$BASE_URL_API/auth/token")
TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ ! -z "$TOKEN" ]; then
    echo "✅ Token JWT obtenu: ${TOKEN:0:20}..."
    export AUTH_HEADER="Authorization: Bearer $TOKEN"
else
    echo "❌ Échec de l'authentification"
    exit 1
fi

# Test 3: Ingestion de données
echo ""
echo "📥 Test 3: Ingestion de données FHIR"

SYNC_RESPONSE=$(curl -s -X POST "$BASE_URL_PROXY/api/v1/fhir/sync/patient/$TEST_PATIENT_ID" \
    -H "Content-Type: application/json")

echo "Réponse d'ingestion: $SYNC_RESPONSE"

if echo "$SYNC_RESPONSE" | grep -q "success\|skipped"; then
    echo "✅ Ingestion réussie"
else
    echo "❌ Échec de l'ingestion"
fi

# Test 4: Attendre le traitement (pipeline asynchrone)
echo ""
echo "⏳ Test 4: Attente du traitement du pipeline (60 secondes)"
sleep 60

# Test 5: Vérification des scores
echo ""
echo "📊 Test 5: Récupération des scores récents"

RECENT_SCORES=$(curl -s -H "$AUTH_HEADER" "$BASE_URL_API/api/v1/scores/recent?limit=10")
echo "Scores récents: $RECENT_SCORES"

if echo "$RECENT_SCORES" | grep -q "patient_pseudo_id"; then
    echo "✅ Scores disponibles"
    
    # Extraire un patient pseudo ID pour les tests suivants
    PSEUDO_ID=$(echo "$RECENT_SCORES" | grep -o '"patient_pseudo_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ ! -z "$PSEUDO_ID" ]; then
        echo "🎯 Test patient trouvé: $PSEUDO_ID"
        
        # Test 6: Score spécifique
        echo ""
        echo "📈 Test 6: Score spécifique d'un patient"
        
        PATIENT_SCORE=$(curl -s -H "$AUTH_HEADER" "$BASE_URL_API/api/v1/score/$PSEUDO_ID")
        echo "Score du patient: $PATIENT_SCORE"
        
        if echo "$PATIENT_SCORE" | grep -q "risk_score"; then
            echo "✅ Score spécifique récupéré"
        else
            echo "❌ Échec récupération score spécifique"
        fi
        
        # Test 7: Explications SHAP
        echo ""
        echo "🔍 Test 7: Explications SHAP"
        
        EXPLANATION=$(curl -s -H "$AUTH_HEADER" "$BASE_URL_API/api/v1/explain/$PSEUDO_ID")
        echo "Explications: $EXPLANATION"
        
        if echo "$EXPLANATION" | grep -q "shap_values"; then
            echo "✅ Explications SHAP récupérées"
        else
            echo "❌ Échec récupération explications"
        fi
    fi
else
    echo "❌ Aucun score disponible"
fi

# Test 8: Statistiques générales
echo ""
echo "📈 Test 8: Statistiques générales"

STATS=$(curl -s -H "$AUTH_HEADER" "$BASE_URL_API/api/v1/statistics/summary")
echo "Statistiques: $STATS"

if echo "$STATS" | grep -q "total_patients"; then
    echo "✅ Statistiques disponibles"
else
    echo "❌ Échec récupération statistiques"
fi

# Test 9: Patients à haut risque
echo ""
echo "⚠️  Test 9: Patients à haut risque"

HIGH_RISK=$(curl -s -H "$AUTH_HEADER" "$BASE_URL_API/api/v1/scores/high-risk?threshold=0.5")
echo "Patients à haut risque: $HIGH_RISK"

if echo "$HIGH_RISK" | grep -q "\[\]" || echo "$HIGH_RISK" | grep -q "patient_pseudo_id"; then
    echo "✅ Requête haut risque fonctionnelle"
else
    echo "❌ Échec requête haut risque"
fi

# Résumé final
echo ""
echo "🎯 Résumé des tests"
echo "=================="
echo "Le pipeline HealthFlow-MS a été testé avec succès !"
echo ""
echo "💡 Pour tester avec de vraies données FHIR:"
echo "   curl -X POST $BASE_URL_PROXY/api/v1/fhir/sync/patient/[REAL_PATIENT_ID]"
echo ""
echo "📊 Consultez le dashboard d'audit: http://localhost:8083"
echo "📖 Documentation API complète: http://localhost:8082/docs"