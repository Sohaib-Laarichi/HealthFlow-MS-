#!/bin/bash

# Script d'arrêt HealthFlow-MS
echo "🛑 Arrêt de HealthFlow-MS"
echo "========================"

# Arrêter tous les services
echo "⏹️  Arrêt des services..."
docker compose down

# Option de nettoyage complet
read -p "Voulez-vous effectuer un nettoyage complet (volumes, images) ? (y/N): " cleanup

if [[ $cleanup =~ ^[Yy]$ ]]; then
    echo "🧹 Nettoyage complet..."
    
    # Supprimer les volumes (attention: perte de données!)
    echo "⚠️  Suppression des volumes de données..."
    docker compose down -v
    
    # Supprimer les images du projet
    echo "🗑️  Suppression des images..."
    docker rmi $(docker images "healthflow-ms*" -q) 2>/dev/null || true
    
    # Nettoyage système Docker
    echo "🧽 Nettoyage du système Docker..."
    docker system prune -f
    
    echo "✅ Nettoyage complet terminé"
else
    echo "✅ Services arrêtés (données conservées)"
fi

echo ""
echo "💡 Pour redémarrer: ./start.sh"