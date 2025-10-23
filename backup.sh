#!/bin/bash

# HealthFlow-MS - Script de sauvegarde automatique
# Sauvegarde la base de données et les configurations

set -e

# Configuration
BACKUP_DIR="./backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="healthflow_backup_${DATE}"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔄 Démarrage de la sauvegarde HealthFlow-MS${NC}"
echo "============================================="

# Créer le répertoire de sauvegarde
mkdir -p "$BACKUP_DIR"

# Vérifier que PostgreSQL est en cours d'exécution
if ! docker compose ps postgres | grep -q "running"; then
    echo -e "${RED}❌ PostgreSQL n'est pas en cours d'exécution${NC}"
    exit 1
fi

echo -e "${BLUE}📦 Sauvegarde de la base de données...${NC}"

# Sauvegarde de la base de données
docker compose exec -T postgres pg_dump -U healthflow -d healthflow --clean --if-exists > "${BACKUP_DIR}/${BACKUP_FILE}.sql"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Base de données sauvegardée : ${BACKUP_FILE}.sql${NC}"
else
    echo -e "${RED}❌ Échec de la sauvegarde de la base de données${NC}"
    exit 1
fi

# Sauvegarde des configurations
echo -e "${BLUE}📋 Sauvegarde des configurations...${NC}"

tar -czf "${BACKUP_DIR}/${BACKUP_FILE}_config.tar.gz" \
    docker-compose.yml \
    .env* \
    init-db/ \
    scripts/ \
    docs/ \
    README.md \
    2>/dev/null || true

echo -e "${GREEN}✅ Configurations sauvegardées : ${BACKUP_FILE}_config.tar.gz${NC}"

# Sauvegarde des volumes Docker (optionnel)
echo -e "${BLUE}💾 Sauvegarde des volumes Docker...${NC}"

docker run --rm \
    -v healthflow-ms_postgres_data:/source:ro \
    -v $(pwd)/backups:/backup \
    alpine tar -czf "/backup/${BACKUP_FILE}_volumes.tar.gz" -C /source .

echo -e "${GREEN}✅ Volumes sauvegardés : ${BACKUP_FILE}_volumes.tar.gz${NC}"

# Statistiques de la sauvegarde
echo -e "\n${BLUE}📊 Statistiques de la sauvegarde${NC}"
echo "================================="

ls -lh "${BACKUP_DIR}/${BACKUP_FILE}"*

total_size=$(du -sh "${BACKUP_DIR}/${BACKUP_FILE}"* | awk '{sum += $1} END {print sum}')
echo -e "Taille totale : ${total_size}"

# Nettoyage des anciennes sauvegardes (garder les 7 dernières)
echo -e "\n${BLUE}🧹 Nettoyage des anciennes sauvegardes${NC}"
echo "======================================"

find "$BACKUP_DIR" -name "healthflow_backup_*" -type f -mtime +7 -delete 2>/dev/null || true
remaining=$(ls -1 "$BACKUP_DIR"/healthflow_backup_* 2>/dev/null | wc -l)
echo -e "Sauvegardes conservées : $remaining"

# Test de l'intégrité de la sauvegarde
echo -e "\n${BLUE}🔍 Test d'intégrité de la sauvegarde${NC}"
echo "===================================="

if gzip -t "${BACKUP_DIR}/${BACKUP_FILE}_config.tar.gz" 2>/dev/null; then
    echo -e "${GREEN}✅ Archive des configurations intègre${NC}"
else
    echo -e "${RED}❌ Archive des configurations corrompue${NC}"
fi

if gzip -t "${BACKUP_DIR}/${BACKUP_FILE}_volumes.tar.gz" 2>/dev/null; then
    echo -e "${GREEN}✅ Archive des volumes intègre${NC}"
else
    echo -e "${RED}❌ Archive des volumes corrompue${NC}"
fi

# Vérification de la sauvegarde SQL
if head -n 5 "${BACKUP_DIR}/${BACKUP_FILE}.sql" | grep -q "PostgreSQL database dump"; then
    echo -e "${GREEN}✅ Sauvegarde SQL valide${NC}"
else
    echo -e "${RED}❌ Sauvegarde SQL invalide${NC}"
fi

# Instructions de restauration
echo -e "\n${BLUE}📖 Instructions de restauration${NC}"
echo "==============================="
echo "Pour restaurer cette sauvegarde :"
echo ""
echo "1. Base de données :"
echo "   docker compose exec -T postgres psql -U healthflow -d healthflow < ${BACKUP_DIR}/${BACKUP_FILE}.sql"
echo ""
echo "2. Configurations :"
echo "   tar -xzf ${BACKUP_DIR}/${BACKUP_FILE}_config.tar.gz"
echo ""
echo "3. Volumes :"
echo "   docker run --rm -v healthflow-ms_postgres_data:/target -v \$(pwd)/backups:/backup alpine tar -xzf /backup/${BACKUP_FILE}_volumes.tar.gz -C /target"

# Génération d'un fichier de métadonnées
cat > "${BACKUP_DIR}/${BACKUP_FILE}_metadata.json" << EOF
{
  "backup_date": "$(date -Iseconds)",
  "healthflow_version": "1.0.0",
  "docker_compose_version": "$(docker compose version --short 2>/dev/null || echo 'unknown')",
  "postgres_version": "$(docker compose exec postgres psql -U healthflow -d healthflow -t -c 'SELECT version();' 2>/dev/null | head -n1 | xargs || echo 'unknown')",
  "backup_files": {
    "database": "${BACKUP_FILE}.sql",
    "config": "${BACKUP_FILE}_config.tar.gz",
    "volumes": "${BACKUP_FILE}_volumes.tar.gz"
  },
  "services_status": {
$(docker compose ps --format json 2>/dev/null | jq -s '.' 2>/dev/null || echo '    "error": "Unable to get services status"')
  }
}
EOF

echo -e "\n${GREEN}🎉 Sauvegarde terminée avec succès !${NC}"
echo "Fichiers créés :"
echo "- ${BACKUP_DIR}/${BACKUP_FILE}.sql"
echo "- ${BACKUP_DIR}/${BACKUP_FILE}_config.tar.gz"
echo "- ${BACKUP_DIR}/${BACKUP_FILE}_volumes.tar.gz"
echo "- ${BACKUP_DIR}/${BACKUP_FILE}_metadata.json"

echo -e "\n${YELLOW}💡 Conseil : Planifiez cette sauvegarde avec cron${NC}"
echo "Exemple : 0 2 * * * /path/to/backup.sh"

exit 0