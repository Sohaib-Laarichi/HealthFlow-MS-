#!/bin/bash

# HealthFlow-MS - Script de restauration
# Restaure une sauvegarde complète du système

set -e

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
BACKUP_DIR="./backups"

echo -e "${BLUE}🔄 Script de restauration HealthFlow-MS${NC}"
echo "======================================="

# Fonction d'affichage de l'aide
show_help() {
    echo "Usage: $0 [OPTIONS] BACKUP_NAME"
    echo ""
    echo "OPTIONS:"
    echo "  -h, --help           Afficher cette aide"
    echo "  -f, --force          Forcer la restauration sans confirmation"
    echo "  -d, --database-only  Restaurer uniquement la base de données"
    echo "  -c, --config-only    Restaurer uniquement les configurations"
    echo "  -v, --volumes-only   Restaurer uniquement les volumes"
    echo ""
    echo "BACKUP_NAME: Nom de la sauvegarde sans extension (ex: healthflow_backup_20240101_120000)"
    echo ""
    echo "Exemples:"
    echo "  $0 healthflow_backup_20240101_120000"
    echo "  $0 -d healthflow_backup_20240101_120000"
    echo "  $0 --force healthflow_backup_20240101_120000"
}

# Fonction pour lister les sauvegardes disponibles
list_backups() {
    echo -e "${BLUE}📋 Sauvegardes disponibles :${NC}"
    echo "=========================="
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        echo -e "${RED}Aucune sauvegarde trouvée dans $BACKUP_DIR${NC}"
        exit 1
    fi
    
    # Grouper les sauvegardes par nom de base
    for metadata in "$BACKUP_DIR"/*_metadata.json; do
        if [ -f "$metadata" ]; then
            backup_name=$(basename "$metadata" "_metadata.json")
            backup_date=$(cat "$metadata" | grep "backup_date" | cut -d'"' -f4 2>/dev/null || echo "Date inconnue")
            
            echo -e "${GREEN}📦 $backup_name${NC}"
            echo "   Date: $backup_date"
            
            # Vérifier quels fichiers sont disponibles
            sql_file="${BACKUP_DIR}/${backup_name}.sql"
            config_file="${BACKUP_DIR}/${backup_name}_config.tar.gz"
            volumes_file="${BACKUP_DIR}/${backup_name}_volumes.tar.gz"
            
            echo -n "   Fichiers: "
            [ -f "$sql_file" ] && echo -n "SQL " || echo -n "❌SQL "
            [ -f "$config_file" ] && echo -n "CONFIG " || echo -n "❌CONFIG "
            [ -f "$volumes_file" ] && echo -n "VOLUMES" || echo -n "❌VOLUMES"
            echo ""
            echo ""
        fi
    done
}

# Fonction de confirmation
confirm() {
    local message="$1"
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    echo -e "${YELLOW}⚠️  $message${NC}"
    read -p "Continuer ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Opération annulée${NC}"
        exit 1
    fi
}

# Fonction de restauration de la base de données
restore_database() {
    local backup_name="$1"
    local sql_file="${BACKUP_DIR}/${backup_name}.sql"
    
    if [ ! -f "$sql_file" ]; then
        echo -e "${RED}❌ Fichier de sauvegarde SQL non trouvé : $sql_file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}🗄️  Restauration de la base de données...${NC}"
    
    # Vérifier que PostgreSQL est en cours d'exécution
    if ! docker compose ps postgres | grep -q "running"; then
        echo -e "${YELLOW}🚀 Démarrage de PostgreSQL...${NC}"
        docker compose up -d postgres
        
        # Attendre que PostgreSQL soit prêt
        echo -e "${BLUE}⏳ Attente de PostgreSQL...${NC}"
        timeout 60 bash -c 'until docker compose exec postgres pg_isready -U healthflow; do sleep 2; done'
    fi
    
    # Restaurer la base de données
    docker compose exec -T postgres psql -U healthflow -d healthflow < "$sql_file"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Base de données restaurée avec succès${NC}"
    else
        echo -e "${RED}❌ Échec de la restauration de la base de données${NC}"
        return 1
    fi
}

# Fonction de restauration des configurations
restore_config() {
    local backup_name="$1"
    local config_file="${BACKUP_DIR}/${backup_name}_config.tar.gz"
    
    if [ ! -f "$config_file" ]; then
        echo -e "${RED}❌ Fichier de sauvegarde des configurations non trouvé : $config_file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📋 Restauration des configurations...${NC}"
    
    # Sauvegarder les fichiers actuels
    backup_current_config_dir="./config_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_current_config_dir"
    
    for file in docker-compose.yml .env* init-db scripts docs README.md; do
        if [ -e "$file" ]; then
            cp -r "$file" "$backup_current_config_dir/" 2>/dev/null || true
        fi
    done
    
    echo -e "${YELLOW}💾 Configuration actuelle sauvegardée dans $backup_current_config_dir${NC}"
    
    # Restaurer les configurations
    tar -xzf "$config_file"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Configurations restaurées avec succès${NC}"
    else
        echo -e "${RED}❌ Échec de la restauration des configurations${NC}"
        return 1
    fi
}

# Fonction de restauration des volumes
restore_volumes() {
    local backup_name="$1"
    local volumes_file="${BACKUP_DIR}/${backup_name}_volumes.tar.gz"
    
    if [ ! -f "$volumes_file" ]; then
        echo -e "${RED}❌ Fichier de sauvegarde des volumes non trouvé : $volumes_file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}💾 Restauration des volumes...${NC}"
    
    # Arrêter les services qui utilisent les volumes
    echo -e "${YELLOW}🛑 Arrêt des services...${NC}"
    docker compose down
    
    # Restaurer les volumes
    docker run --rm \
        -v healthflow-ms_postgres_data:/target \
        -v "$(pwd)/backups:/backup" \
        alpine tar -xzf "/backup/$(basename "$volumes_file")" -C /target
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Volumes restaurés avec succès${NC}"
    else
        echo -e "${RED}❌ Échec de la restauration des volumes${NC}"
        return 1
    fi
}

# Traitement des arguments
FORCE=false
DATABASE_ONLY=false
CONFIG_ONLY=false
VOLUMES_ONLY=false
BACKUP_NAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -d|--database-only)
            DATABASE_ONLY=true
            shift
            ;;
        -c|--config-only)
            CONFIG_ONLY=true
            shift
            ;;
        -v|--volumes-only)
            VOLUMES_ONLY=true
            shift
            ;;
        -*)
            echo -e "${RED}Option inconnue : $1${NC}"
            show_help
            exit 1
            ;;
        *)
            BACKUP_NAME="$1"
            shift
            ;;
    esac
done

# Si aucun nom de sauvegarde n'est fourni, lister les sauvegardes disponibles
if [ -z "$BACKUP_NAME" ]; then
    list_backups
    echo ""
    echo -e "${BLUE}💡 Utilisez '$0 <backup_name>' pour restaurer une sauvegarde${NC}"
    echo -e "${BLUE}💡 Utilisez '$0 -h' pour afficher l'aide complète${NC}"
    exit 0
fi

# Vérifier que les fichiers de sauvegarde existent
metadata_file="${BACKUP_DIR}/${BACKUP_NAME}_metadata.json"
if [ ! -f "$metadata_file" ]; then
    echo -e "${RED}❌ Sauvegarde non trouvée : $BACKUP_NAME${NC}"
    echo ""
    list_backups
    exit 1
fi

# Afficher les informations de la sauvegarde
echo -e "${BLUE}📊 Informations de la sauvegarde${NC}"
echo "==============================="
backup_date=$(cat "$metadata_file" | grep "backup_date" | cut -d'"' -f4 2>/dev/null || echo "Date inconnue")
echo "Nom: $BACKUP_NAME"
echo "Date: $backup_date"
echo ""

# Confirmer l'opération
if [ "$DATABASE_ONLY" = true ]; then
    confirm "Cette opération va restaurer UNIQUEMENT la base de données. Toutes les données actuelles seront remplacées."
elif [ "$CONFIG_ONLY" = true ]; then
    confirm "Cette opération va restaurer UNIQUEMENT les fichiers de configuration."
elif [ "$VOLUMES_ONLY" = true ]; then
    confirm "Cette opération va restaurer UNIQUEMENT les volumes Docker. Les services seront arrêtés."
else
    confirm "Cette opération va restaurer COMPLÈTEMENT le système. Toutes les données actuelles seront remplacées."
fi

# Exécuter la restauration
echo -e "\n${BLUE}🚀 Démarrage de la restauration...${NC}"

if [ "$DATABASE_ONLY" = true ]; then
    restore_database "$BACKUP_NAME"
elif [ "$CONFIG_ONLY" = true ]; then
    restore_config "$BACKUP_NAME"
elif [ "$VOLUMES_ONLY" = true ]; then
    restore_volumes "$BACKUP_NAME"
else
    # Restauration complète
    restore_config "$BACKUP_NAME"
    restore_volumes "$BACKUP_NAME"
    
    # Redémarrer les services
    echo -e "${BLUE}🚀 Redémarrage des services...${NC}"
    docker compose up -d
    
    # Attendre que PostgreSQL soit prêt
    echo -e "${BLUE}⏳ Attente de PostgreSQL...${NC}"
    timeout 60 bash -c 'until docker compose exec postgres pg_isready -U healthflow; do sleep 2; done'
    
    restore_database "$BACKUP_NAME"
fi

echo -e "\n${GREEN}🎉 Restauration terminée avec succès !${NC}"

if [ "$DATABASE_ONLY" = false ] && [ "$CONFIG_ONLY" = false ] && [ "$VOLUMES_ONLY" = false ]; then
    echo -e "\n${BLUE}🔍 Vérification de la santé des services...${NC}"
    sleep 10
    ./monitor.sh || true
fi

exit 0