# Installation de Docker pour HealthFlow-MS

## 🐳 Installation Docker

### Ubuntu/Debian
```bash
# Mise à jour du système
sudo apt update

# Installation des prérequis
sudo apt install apt-transport-https ca-certificates curl gnupg lsb-release

# Ajout de la clé GPG Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Ajout du repository Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installation Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Démarrage et activation
sudo systemctl start docker
sudo systemctl enable docker

# Ajout de votre utilisateur au groupe docker
sudo usermod -aG docker $USER
```

### CentOS/RHEL/Rocky Linux
```bash
# Installation des prérequis
sudo yum install -y yum-utils

# Ajout du repository Docker
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Installation Docker
sudo yum install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Démarrage et activation
sudo systemctl start docker
sudo systemctl enable docker

# Ajout de votre utilisateur au groupe docker
sudo usermod -aG docker $USER
```

### Fedora
```bash
# Installation Docker
sudo dnf install docker docker-compose

# Démarrage et activation
sudo systemctl start docker
sudo systemctl enable docker

# Ajout de votre utilisateur au groupe docker
sudo usermod -aG docker $USER
```

### macOS
1. Télécharger Docker Desktop depuis https://www.docker.com/products/docker-desktop
2. Installer le package .dmg
3. Lancer Docker Desktop

### Windows
1. Télécharger Docker Desktop depuis https://www.docker.com/products/docker-desktop
2. Installer le package .exe
3. Redémarrer si nécessaire
4. Lancer Docker Desktop

## ✅ Vérification de l'installation

```bash
# Vérifier Docker
docker --version
docker compose version

# Test simple
docker run hello-world
```

## 🚀 Lancement de HealthFlow-MS

Une fois Docker installé :

```bash
# Se déconnecter et reconnecter pour les permissions de groupe
# ou utiliser newgrp docker

# Aller dans le répertoire du projet
cd HealthFlow-MS

# Lancer le projet
./start.sh
```

## 🔧 Configuration système recommandée

### Ressources minimales
- **RAM** : 8GB minimum, 16GB recommandé
- **CPU** : 4 cores minimum
- **Stockage** : 20GB d'espace libre
- **Réseau** : Connexion internet pour télécharger les images

### Ports utilisés
- **8081** : ProxyFHIR (ingestion FHIR)
- **8082** : ScoreAPI (API REST)
- **8083** : AuditFairness (dashboard)
- **5432** : PostgreSQL (base de données)
- **9092** : Kafka (message broker)
- **2181** : Zookeeper (coordination Kafka)

### Optimisations Docker
```bash
# Allouer plus de mémoire à Docker (Linux)
sudo sysctl vm.max_map_count=262144

# Configuration Docker daemon (optionnel)
# /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## 🐛 Dépannage

### Problèmes de permissions
```bash
# Si erreur "permission denied"
sudo chown $USER:$USER /var/run/docker.sock
# ou
sudo chmod 666 /var/run/docker.sock
```

### Services qui ne démarrent pas
```bash
# Vérifier les logs
docker compose logs [service-name]

# Vérifier l'espace disque
df -h

# Vérifier la mémoire
free -h
```

### Problèmes réseau
```bash
# Redémarrer Docker
sudo systemctl restart docker

# Nettoyer les réseaux
docker network prune
```