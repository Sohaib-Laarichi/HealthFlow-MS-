#!/bin/bash

# HealthFlow-MS - Script de surveillance des services
# Monitore la santé de tous les microservices

set -e

echo "🔍 Surveillance de la santé des services HealthFlow-MS"
echo "=================================================="

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour vérifier si un service est actif
check_service() {
    local service_name=$1
    local status=$(docker compose ps --format "table {{.Service}}\t{{.State}}" | grep "$service_name" | awk '{print $2}' || echo "not_found")
    
    if [ "$status" = "running" ]; then
        echo -e "${GREEN}✓${NC} $service_name : ${GREEN}Actif${NC}"
        return 0
    elif [ "$status" = "exited" ]; then
        echo -e "${RED}✗${NC} $service_name : ${RED}Arrêté${NC}"
        return 1
    else
        echo -e "${YELLOW}?${NC} $service_name : ${YELLOW}État inconnu${NC}"
        return 1
    fi
}

# Fonction pour vérifier la connectivité réseau
check_connectivity() {
    local service_name=$1
    local port=$2
    local host=${3:-localhost}
    
    if timeout 5 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $service_name ($host:$port) : ${GREEN}Accessible${NC}"
        return 0
    else
        echo -e "${RED}✗${NC} $service_name ($host:$port) : ${RED}Inaccessible${NC}"
        return 1
    fi
}

# Fonction pour vérifier la santé d'un endpoint HTTP
check_health_endpoint() {
    local service_name=$1
    local url=$2
    
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$response" -ge 200 ] && [ "$response" -lt 300 ]; then
        echo -e "${GREEN}✓${NC} $service_name Health Check : ${GREEN}HTTP $response${NC}"
        return 0
    else
        echo -e "${RED}✗${NC} $service_name Health Check : ${RED}HTTP $response${NC}"
        return 1
    fi
}

# Fonction pour afficher les logs récents d'un service
show_recent_logs() {
    local service_name=$1
    echo -e "\n${BLUE}📋 Logs récents pour $service_name :${NC}"
    docker compose logs --tail=5 "$service_name" 2>/dev/null || echo "Logs non disponibles"
}

# Variables de comptage
total_services=0
healthy_services=0

echo -e "\n${BLUE}🔧 Infrastructure Services${NC}"
echo "========================="

# Vérification PostgreSQL
((total_services++))
if check_service "postgres" && check_connectivity "PostgreSQL" 5432; then
    ((healthy_services++))
fi

# Vérification Zookeeper
((total_services++))
if check_service "zookeeper" && check_connectivity "Zookeeper" 2181; then
    ((healthy_services++))
fi

# Vérification Kafka
((total_services++))
if check_service "kafka" && check_connectivity "Kafka" 9092; then
    ((healthy_services++))
fi

echo -e "\n${BLUE}🚀 Application Services${NC}"
echo "======================="

# Vérification ProxyFHIR
((total_services++))
if check_service "proxyfhir"; then
    if check_connectivity "ProxyFHIR" 8081 && check_health_endpoint "ProxyFHIR" "http://localhost:8081/actuator/health"; then
        ((healthy_services++))
    fi
else
    show_recent_logs "proxyfhir"
fi

# Vérification DeID
((total_services++))
if check_service "deid"; then
    if check_connectivity "DeID" 8001 && check_health_endpoint "DeID" "http://localhost:8001/health"; then
        ((healthy_services++))
    fi
else
    show_recent_logs "deid"
fi

# Vérification Featurizer
((total_services++))
if check_service "featurizer"; then
    if check_connectivity "Featurizer" 8002 && check_health_endpoint "Featurizer" "http://localhost:8002/health"; then
        ((healthy_services++))
    fi
else
    show_recent_logs "featurizer"
fi

# Vérification ModelRisque
((total_services++))
if check_service "modelrisque"; then
    if check_connectivity "ModelRisque" 8003 && check_health_endpoint "ModelRisque" "http://localhost:8003/health"; then
        ((healthy_services++))
    fi
else
    show_recent_logs "modelrisque"
fi

# Vérification ScoreAPI
((total_services++))
if check_service "scoreapi"; then
    if check_connectivity "ScoreAPI" 8082 && check_health_endpoint "ScoreAPI" "http://localhost:8082/health"; then
        ((healthy_services++))
    fi
else
    show_recent_logs "scoreapi"
fi

# Vérification AuditFairness
((total_services++))
if check_service "auditfairness"; then
    if check_connectivity "AuditFairness" 8083 && check_health_endpoint "AuditFairness" "http://localhost:8083/_dash-dependencies"; then
        ((healthy_services++))
    fi
else
    show_recent_logs "auditfairness"
fi

# Résumé de la santé
echo -e "\n${BLUE}📊 Résumé de la santé${NC}"
echo "===================="

health_percentage=$((healthy_services * 100 / total_services))

if [ $health_percentage -eq 100 ]; then
    echo -e "${GREEN}✓ Tous les services sont opérationnels${NC} ($healthy_services/$total_services)"
elif [ $health_percentage -ge 80 ]; then
    echo -e "${YELLOW}⚠ La plupart des services sont opérationnels${NC} ($healthy_services/$total_services)"
else
    echo -e "${RED}✗ Plusieurs services ont des problèmes${NC} ($healthy_services/$total_services)"
fi

# Vérifications supplémentaires
echo -e "\n${BLUE}🔍 Vérifications supplémentaires${NC}"
echo "==============================="

# Utilisation des ressources
echo -e "\n${BLUE}💾 Utilisation des ressources :${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "Stats non disponibles"

# Espace disque
echo -e "\n${BLUE}💿 Espace disque Docker :${NC}"
docker system df 2>/dev/null || echo "Info disque non disponible"

# Réseaux Docker
echo -e "\n${BLUE}🌐 Réseaux actifs :${NC}"
docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>/dev/null || echo "Réseaux non disponibles"

# Recommandations
echo -e "\n${BLUE}💡 Recommandations${NC}"
echo "=================="

if [ $health_percentage -lt 100 ]; then
    echo "• Vérifiez les logs des services défaillants"
    echo "• Redémarrez les services problématiques : docker compose restart [service]"
    echo "• Vérifiez les ressources système disponibles"
fi

echo "• Surveillez régulièrement la santé des services"
echo "• Configurez des alertes pour les services critiques"
echo "• Sauvegardez régulièrement la base de données PostgreSQL"

echo -e "\n${BLUE}🔄 Pour surveiller en continu :${NC}"
echo "watch -n 30 ./monitor.sh"

echo -e "\n${GREEN}Surveillance terminée.${NC}"
echo "Date : $(date)"

exit 0