#!/bin/bash

# HealthFlow-MS Startup Script
# Ce script lance l'environnement complet HealthFlow-MS

echo "🏥 Démarrage de HealthFlow-MS - Plateforme MLOps pour l'Analyse de Risque Médical"
echo "=================================================================="

# Vérification des prérequis
echo "🔍 Vérification des prérequis..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé. Veuillez installer Docker Engine."
    echo "   Installation Ubuntu/Debian: sudo apt-get install docker.io docker-compose-plugin"
    echo "   Installation CentOS/RHEL: sudo yum install docker docker-compose"
    echo "   Installation macOS: Installer Docker Desktop"
    exit 1
fi

if ! command -v docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé."
    echo "   Installer avec: pip install docker-compose"
    exit 1
fi

echo "✅ Docker et Docker Compose sont disponibles"

# Vérifier si les services sont déjà en cours d'exécution
if docker compose ps | grep -q "Up"; then
    echo "⚠️  Certains services sont déjà en cours d'exécution"
    read -p "Voulez-vous les redémarrer ? (y/N): " restart
    if [[ $restart =~ ^[Yy]$ ]]; then
        echo "🔄 Arrêt des services existants..."
        docker compose down
    fi
fi

# Nettoyer les ressources précédentes si nécessaire
echo "🧹 Nettoyage des ressources précédentes..."
docker system prune -f --volumes

# Construire et lancer les services
echo "🚀 Construction et lancement des services..."
docker compose up -d --build

# Attendre que les services soient prêts
echo "⏳ Attente du démarrage des services..."
sleep 30

# Vérifier le statut des services
echo "📊 Statut des services:"
docker compose ps

# Afficher les URLs d'accès
echo ""
echo "🌐 Interfaces disponibles:"
echo "  📖 ScoreAPI Documentation : http://localhost:8082/docs"
echo "  📊 AuditFairness Dashboard : http://localhost:8083"
echo "  🔧 ProxyFHIR Health Check  : http://localhost:8081/api/v1/fhir/health"
echo ""

# Test de connectivité
echo "🔍 Test de connectivité des services..."

# Test ProxyFHIR
if curl -s http://localhost:8081/api/v1/fhir/health > /dev/null; then
    echo "✅ ProxyFHIR: Service actif"
else
    echo "❌ ProxyFHIR: Service non accessible"
fi

# Test ScoreAPI
if curl -s http://localhost:8082/health > /dev/null; then
    echo "✅ ScoreAPI: Service actif"
else
    echo "❌ ScoreAPI: Service non accessible"
fi

# Test AuditFairness
if curl -s http://localhost:8083 > /dev/null; then
    echo "✅ AuditFairness: Dashboard actif"
else
    echo "❌ AuditFairness: Dashboard non accessible"
fi

echo ""
echo "🎉 HealthFlow-MS est prêt !"
echo ""
echo "📝 Prochaines étapes:"
echo "  1. Obtenir un token: curl -X POST http://localhost:8082/auth/token"
echo "  2. Ingérer des données: curl -X POST http://localhost:8081/api/v1/fhir/sync/patient/123"
echo "  3. Consulter le dashboard: http://localhost:8083"
echo ""
echo "📚 Documentation complète: README.md"
echo "🛑 Pour arrêter: docker compose down"