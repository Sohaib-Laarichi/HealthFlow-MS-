# 🛠️ Guide de Dépannage HealthFlow-MS

## 🚨 Problèmes Courants et Solutions

### 1. Échec de démarrage des services

#### Symptômes
```bash
ERROR: Service 'proxyfhir' failed to build
ERROR: Failed to start container
```

#### Solutions
```bash
# Nettoyer les conteneurs et images
docker compose down --volumes --remove-orphans
docker system prune -a

# Reconstruire depuis zéro
docker compose build --no-cache
docker compose up -d
```

### 2. Problèmes de connectivité PostgreSQL

#### Symptômes
```
Connection refused to PostgreSQL
FATAL: database "healthflow" does not exist
```

#### Solutions
```bash
# Vérifier l'état de PostgreSQL
docker compose logs postgres

# Recréer la base de données
docker compose down
docker volume rm healthflow-ms_postgres_data
docker compose up -d postgres

# Attendre l'initialisation complète
docker compose logs -f postgres
```

### 3. Kafka non accessible

#### Symptômes
```
kafka.errors.NoBrokersAvailable
Connection refused to Kafka
```

#### Solutions
```bash
# Redémarrer Zookeeper et Kafka dans l'ordre
docker compose restart zookeeper
sleep 10
docker compose restart kafka
sleep 20

# Vérifier la connectivité
docker compose exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092
```

### 4. Services Python qui crashent

#### Symptômes
```
ModuleNotFoundError: No module named 'xxx'
ImportError: cannot import name 'xxx'
```

#### Solutions
```bash
# Reconstruire l'image spécifique
docker compose build [service-name] --no-cache

# Vérifier les logs détaillés
docker compose logs -f [service-name]

# Redémarrer un service spécifique
docker compose restart [service-name]
```

### 5. Erreurs d'authentification JWT

#### Symptômes
```
401 Unauthorized
Invalid JWT token
Token has expired
```

#### Solutions
```bash
# Générer un nouveau token de test
curl -X POST http://localhost:8082/token \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass"}'

# Utiliser le token dans les requêtes
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8082/api/patients
```

### 6. Ports déjà utilisés

#### Symptômes
```
Error starting userland proxy: listen tcp 0.0.0.0:8081: bind: address already in use
```

#### Solutions
```bash
# Identifier les processus utilisant les ports
sudo netstat -tulpn | grep :8081
sudo lsof -i :8081

# Tuer le processus utilisant le port
sudo kill -9 [PID]

# Ou modifier les ports dans docker-compose.yml
```

### 7. Manque de mémoire

#### Symptômes
```
Container killed due to memory limit
java.lang.OutOfMemoryError
MemoryError in Python
```

#### Solutions
```bash
# Augmenter la mémoire Docker
# Linux: /etc/docker/daemon.json
{
  "default-ulimits": {
    "memlock": {
      "name": "memlock",
      "soft": -1,
      "hard": -1
    }
  }
}

# Redémarrer Docker
sudo systemctl restart docker

# Ajuster les limites dans docker-compose.yml
services:
  proxyfhir:
    deploy:
      resources:
        limits:
          memory: 2G
```

### 8. Problèmes de permissions fichiers

#### Symptômes
```
Permission denied
cannot create directory
```

#### Solutions
```bash
# Corriger les permissions
sudo chown -R $USER:$USER ./HealthFlow-MS

# Permissions Docker socket
sudo chmod 666 /var/run/docker.sock
```

## 🔍 Commandes de Diagnostic

### État général du système
```bash
# Vue d'ensemble des services
docker compose ps

# Utilisation des ressources
docker stats

# Espace disque
docker system df

# Santé complète
./monitor.sh
```

### Logs détaillés
```bash
# Tous les logs
docker compose logs

# Logs d'un service spécifique
docker compose logs -f proxyfhir

# Logs avec timestamps
docker compose logs -t --since 1h

# Logs d'erreur uniquement
docker compose logs | grep -i error
```

### Tests de connectivité
```bash
# Test PostgreSQL
docker compose exec postgres psql -U healthflow -d healthflow -c "SELECT version();"

# Test Kafka
docker compose exec kafka kafka-console-producer.sh --topic test-topic --bootstrap-server localhost:9092

# Test endpoints HTTP
curl -f http://localhost:8081/actuator/health
curl -f http://localhost:8082/health
```

### Inspection des conteneurs
```bash
# Entrer dans un conteneur
docker compose exec proxyfhir bash
docker compose exec postgres psql -U healthflow -d healthflow

# Inspecter la configuration réseau
docker network inspect healthflow-ms_default

# Variables d'environnement
docker compose exec proxyfhir env
```

## 🚀 Procédures de Récupération

### Récupération rapide
```bash
# Redémarrage complet
./stop.sh
./start.sh

# Ou plus agressif
docker compose down --volumes
docker compose up -d
```

### Récupération avec sauvegarde
```bash
# Sauvegarder la base de données
docker compose exec postgres pg_dump -U healthflow -d healthflow > backup.sql

# Restaurer depuis une sauvegarde
docker compose exec -T postgres psql -U healthflow -d healthflow < backup.sql
```

### Reset complet du système
```bash
# ⚠️ ATTENTION: Supprime toutes les données
docker compose down --volumes --remove-orphans
docker system prune -a --volumes
docker volume prune

# Reconstruire tout
docker compose build --no-cache
docker compose up -d
```

## 📊 Monitoring et Alertes

### Surveillance continue
```bash
# Surveiller la santé
watch -n 30 ./monitor.sh

# Surveiller les logs en temps réel
docker compose logs -f

# Surveiller les ressources
watch -n 5 "docker stats --no-stream"
```

### Alertes personnalisées
```bash
# Script d'alerte simple
#!/bin/bash
health_check=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8082/health)
if [ "$health_check" != "200" ]; then
    echo "ALERTE: ScoreAPI non accessible" | mail -s "HealthFlow Alert" admin@example.com
fi
```

## 🔧 Optimisations Performance

### Base de données
```sql
-- Optimiser PostgreSQL
VACUUM ANALYZE;
REINDEX DATABASE healthflow;

-- Statistiques des requêtes lentes
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

### Kafka
```bash
# Nettoyer les anciens messages
docker compose exec kafka kafka-topics.sh --delete --topic patient-data --bootstrap-server localhost:9092
docker compose exec kafka kafka-topics.sh --create --topic patient-data --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092
```

### Docker
```bash
# Nettoyer l'espace disque
docker system prune -a
docker volume prune

# Optimiser les images
docker compose build --compress
```

## 📞 Support et Escalade

### Informations à collecter
```bash
# Générer un rapport de diagnostic
echo "=== DIAGNOSTIC HEALTHFLOW-MS ===" > diagnostic.log
echo "Date: $(date)" >> diagnostic.log
echo "Docker version: $(docker --version)" >> diagnostic.log
echo "Docker Compose version: $(docker compose version)" >> diagnostic.log
echo "" >> diagnostic.log
echo "=== Services Status ===" >> diagnostic.log
docker compose ps >> diagnostic.log
echo "" >> diagnostic.log
echo "=== System Resources ===" >> diagnostic.log
docker stats --no-stream >> diagnostic.log
echo "" >> diagnostic.log
echo "=== Recent Logs ===" >> diagnostic.log
docker compose logs --tail=50 >> diagnostic.log
```

### Contacts de support
- **Documentation** : README.md et dossier docs/
- **Issues GitHub** : [Créer une issue]
- **Logs système** : Toujours inclure les logs avec les rapports de bug

### Informations requises pour le support
1. Version du système d'exploitation
2. Version Docker et Docker Compose
3. Fichier docker-compose.yml utilisé
4. Logs complets des services concernés
5. Configuration réseau locale
6. Ressources système disponibles