#!/bin/bash

# HealthFlow-MS - Script de vérification de l'environnement
# Vérifie tous les prérequis avant déploiement

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Vérification de l'environnement HealthFlow-MS${NC}"
echo "=================================================="

# Variables de comptage
total_checks=0
passed_checks=0

# Fonction de vérification
check() {
    local test_name="$1"
    local command="$2"
    local required="$3"
    
    ((total_checks++))
    
    echo -n "Vérification $test_name... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((passed_checks++))
        return 0
    else
        if [ "$required" = "true" ]; then
            echo -e "${RED}✗ (REQUIS)${NC}"
        else
            echo -e "${YELLOW}⚠ (OPTIONNEL)${NC}"
        fi
        return 1
    fi
}

# Fonction d'information système
system_info() {
    echo -e "\n${BLUE}📋 Informations système${NC}"
    echo "======================="
    
    echo "OS: $(uname -s) $(uname -r)"
    echo "Architecture: $(uname -m)"
    
    if command -v lsb_release > /dev/null 2>&1; then
        echo "Distribution: $(lsb_release -d | cut -f2)"
    elif [ -f /etc/os-release ]; then
        echo "Distribution: $(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)"
    fi
    
    echo "Shell: $SHELL"
    echo "User: $(whoami)"
    echo "Home: $HOME"
    echo "PWD: $(pwd)"
}

# Fonction de vérification des ressources
check_resources() {
    echo -e "\n${BLUE}💾 Ressources système${NC}"
    echo "==================="
    
    # RAM disponible
    if command -v free > /dev/null 2>&1; then
        total_ram=$(free -m | grep '^Mem:' | awk '{print $2}')
        available_ram=$(free -m | grep '^Mem:' | awk '{print $7}')
        
        echo "RAM totale: ${total_ram}MB"
        echo "RAM disponible: ${available_ram}MB"
        
        if [ "$total_ram" -lt 4096 ]; then
            echo -e "${YELLOW}⚠ RAM totale faible (recommandé: 8GB+)${NC}"
        fi
        
        if [ "$available_ram" -lt 2048 ]; then
            echo -e "${YELLOW}⚠ RAM disponible faible${NC}"
        fi
    else
        echo "Information RAM non disponible"
    fi
    
    # Espace disque
    if command -v df > /dev/null 2>&1; then
        disk_usage=$(df -h . | tail -1)
        available_space=$(echo "$disk_usage" | awk '{print $4}' | sed 's/G//')
        
        echo "Espace disque disponible: $(echo "$disk_usage" | awk '{print $4}')"
        
        if command -v numfmt > /dev/null 2>&1; then
            available_gb=$(echo "$available_space" | sed 's/[^0-9.]//g')
            if [ "$(echo "$available_gb < 10" | bc -l 2>/dev/null || echo "0")" = "1" ]; then
                echo -e "${YELLOW}⚠ Espace disque faible (recommandé: 20GB+)${NC}"
            fi
        fi
    fi
    
    # CPU
    if [ -f /proc/cpuinfo ]; then
        cpu_cores=$(nproc)
        echo "Cœurs CPU: $cpu_cores"
        
        if [ "$cpu_cores" -lt 2 ]; then
            echo -e "${YELLOW}⚠ Nombre de cœurs faible (recommandé: 4+)${NC}"
        fi
    fi
}

# Fonction de vérification réseau
check_network() {
    echo -e "\n${BLUE}🌐 Connectivité réseau${NC}"
    echo "====================="
    
    # Test de connectivité internet
    if ping -c 1 google.com > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Connexion internet"
    else
        echo -e "${RED}✗${NC} Pas de connexion internet"
    fi
    
    # Vérification des ports disponibles
    ports_to_check=(5432 8081 8082 8083 9092 2181)
    busy_ports=()
    
    for port in "${ports_to_check[@]}"; do
        if ss -tuln 2>/dev/null | grep ":$port " > /dev/null; then
            busy_ports+=($port)
        fi
    done
    
    if [ ${#busy_ports[@]} -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Tous les ports requis sont disponibles"
    else
        echo -e "${YELLOW}⚠${NC} Ports occupés: ${busy_ports[*]}"
        echo "  Les services suivants pourraient être en conflit:"
        for port in "${busy_ports[@]}"; do
            case $port in
                5432) echo "    - PostgreSQL (port $port)" ;;
                8081) echo "    - ProxyFHIR (port $port)" ;;
                8082) echo "    - ScoreAPI (port $port)" ;;
                8083) echo "    - AuditFairness (port $port)" ;;
                9092) echo "    - Kafka (port $port)" ;;
                2181) echo "    - Zookeeper (port $port)" ;;
            esac
        done
    fi
}

# Affichage des informations système
system_info

# Vérifications des prérequis
echo -e "\n${BLUE}🔧 Prérequis système${NC}"
echo "=================="

# Docker
check "Docker" "docker --version" "true"
if ! command -v docker > /dev/null 2>&1; then
    echo -e "  ${RED}Docker est requis. Consultez DOCKER_INSTALL.md${NC}"
fi

# Docker Compose
check "Docker Compose" "docker compose version" "true"
if ! command -v docker > /dev/null 2>&1 || ! docker compose version > /dev/null 2>&1; then
    echo -e "  ${RED}Docker Compose est requis${NC}"
fi

# Git (optionnel pour cloner le repo)
check "Git" "git --version" "false"

# Curl (pour les tests d'API)
check "Curl" "curl --version" "false"

# jq (pour le parsing JSON)
check "jq" "jq --version" "false"

# Vérifications des permissions Docker
echo -e "\n${BLUE}🔐 Permissions Docker${NC}"
echo "===================="

if command -v docker > /dev/null 2>&1; then
    if docker ps > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Permissions Docker OK"
        ((passed_checks++))
    else
        echo -e "${RED}✗${NC} Permissions Docker insuffisantes"
        echo -e "  ${YELLOW}Solutions possibles:${NC}"
        echo "  - sudo usermod -aG docker \$USER && newgrp docker"
        echo "  - sudo chmod 666 /var/run/docker.sock"
        echo "  - Redémarrer la session utilisateur"
    fi
    ((total_checks++))
fi

# Vérification de l'environnement Docker
if command -v docker > /dev/null 2>&1 && docker ps > /dev/null 2>&1; then
    echo -e "\n${BLUE}🐳 Environnement Docker${NC}"
    echo "======================"
    
    # Version Docker
    docker_version=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "inconnu")
    echo "Version Docker: $docker_version"
    
    # Version Docker Compose
    compose_version=$(docker compose version --short 2>/dev/null || echo "inconnu")
    echo "Version Docker Compose: $compose_version"
    
    # Informations Docker daemon
    if docker info > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Docker daemon actif"
        
        # Vérifier l'espace disque Docker
        docker_space=$(docker system df --format "table {{.Type}}\t{{.Size}}" 2>/dev/null | tail -n +2 | awk '{sum += $2} END {print sum}' 2>/dev/null || echo "0")
        echo "Espace utilisé par Docker: ${docker_space:-0}"
    else
        echo -e "${RED}✗${NC} Docker daemon non accessible"
    fi
fi

# Vérifications spécifiques au projet
echo -e "\n${BLUE}📁 Structure du projet${NC}"
echo "====================="

required_files=(
    "docker-compose.yml"
    "init-db/init.sql"
    "proxyfhir/Dockerfile"
    "deid/Dockerfile"
    "featurizer/Dockerfile"
    "modelrisque/Dockerfile"
    "scoreapi/Dockerfile"
    "auditfairness/Dockerfile"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file"
        ((passed_checks++))
    else
        echo -e "${RED}✗${NC} $file (manquant)"
    fi
    ((total_checks++))
done

# Vérifications des scripts
echo -e "\n${BLUE}🔨 Scripts disponibles${NC}"
echo "====================="

scripts=("start.sh" "stop.sh" "monitor.sh" "backup.sh" "restore.sh")

for script in "${scripts[@]}"; do
    if [ -f "$script" ] && [ -x "$script" ]; then
        echo -e "${GREEN}✓${NC} $script"
        ((passed_checks++))
    else
        echo -e "${YELLOW}⚠${NC} $script (manquant ou non exécutable)"
    fi
    ((total_checks++))
done

# Vérifications des ressources
check_resources

# Vérifications réseau
check_network

# Recommandations finales
echo -e "\n${BLUE}📊 Résumé des vérifications${NC}"
echo "=========================="

success_rate=$((passed_checks * 100 / total_checks))

if [ $success_rate -eq 100 ]; then
    echo -e "${GREEN}🎉 Toutes les vérifications sont passées ($passed_checks/$total_checks)${NC}"
    echo -e "${GREEN}✅ Votre environnement est prêt pour HealthFlow-MS${NC}"
elif [ $success_rate -ge 80 ]; then
    echo -e "${YELLOW}⚠ La plupart des vérifications sont passées ($passed_checks/$total_checks)${NC}"
    echo -e "${YELLOW}🔧 Quelques ajustements pourraient être nécessaires${NC}"
else
    echo -e "${RED}❌ Plusieurs vérifications ont échoué ($passed_checks/$total_checks)${NC}"
    echo -e "${RED}🛠 Des corrections sont nécessaires avant le déploiement${NC}"
fi

echo -e "\n${BLUE}💡 Prochaines étapes${NC}"
echo "=================="

if [ $success_rate -lt 100 ]; then
    echo "1. Résolvez les problèmes identifiés ci-dessus"
    echo "2. Consultez DOCKER_INSTALL.md pour l'installation Docker"
    echo "3. Relancez ce script: ./check_environment.sh"
    echo "4. Une fois tous les prérequis satisfaits, lancez: ./start.sh"
else
    echo "1. Votre environnement est prêt !"
    echo "2. Lancez le système: ./start.sh"
    echo "3. Surveillez la santé: ./monitor.sh"
    echo "4. Testez le pipeline: ./scripts/test_pipeline.sh"
fi

echo -e "\n${BLUE}📚 Documentation${NC}"
echo "================"
echo "- README.md : Guide de démarrage"
echo "- DOCKER_INSTALL.md : Installation Docker"
echo "- TROUBLESHOOTING.md : Résolution de problèmes"
echo "- PROJECT_OVERVIEW.md : Vue d'ensemble complète"

exit 0