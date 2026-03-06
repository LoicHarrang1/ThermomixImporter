#!/usr/bin/env python3
"""
Import batch de recettes Cookomix vers Cookidoo

Importe plusieurs recettes depuis un fichier texte contenant des URLs.

Usage:
  python batch_import.py urls.txt
  python batch_import.py urls.txt --delay 10 --dry-run
  
Format du fichier:
  Une URL par ligne, lignes vides et commentaires (#) ignorés
  
Exemple urls.txt:
  # Recettes de base
  https://www.cookomix.com/recettes/pate-a-pizza-thermomix/
  https://www.cookomix.com/recettes/manouche-thermomix/
  
  # Desserts
  https://www.cookomix.com/recettes/cookies-thermomix/
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ajouter le répertoire parent pour importer le scraper
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrape_cookomix import scrape_recipe
from import_from_cookomix import (
    transform_to_cookidoo_format,
    upload_to_cookidoo,
    print_recipe_preview
)


def load_urls_from_file(filepath: Path) -> list[str]:
    """
    Charge les URLs depuis un fichier texte.
    
    Args:
        filepath: Chemin vers le fichier contenant les URLs
        
    Returns:
        Liste des URLs valides
    """
    urls = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Ignorer les lignes vides et commentaires
            if not line or line.startswith('#'):
                continue
            
            # Vérifier que c'est une URL
            if not line.startswith('http'):
                print(f"⚠️  Ligne {line_num}: URL invalide ignorée: {line}")
                continue
            
            urls.append(line)
    
    return urls


async def batch_import(
    urls: list[str],
    delay: int = 5,
    dry_run: bool = False,
    servings: int | None = None,
    prep_time: int = 30,
    total_time: int = 60,
) -> tuple[int, int]:
    """
    Importe plusieurs recettes en batch.
    
    Args:
        urls: Liste des URLs Cookomix
        delay: Délai entre chaque import en secondes
        dry_run: Mode dry-run (pas d'upload)
        servings: Nombre de portions (None = auto)
        prep_time: Temps de préparation par défaut
        total_time: Temps total par défaut
        
    Returns:
        Tuple (nombre de succès, nombre d'échecs)
    """
    success_count = 0
    error_count = 0
    results = []
    
    print("\n" + "=" * 70)
    print(f"🍳 BATCH IMPORT: {len(urls)} recettes à importer")
    print("=" * 70)
    
    for i, url in enumerate(urls, 1):
        print(f"\n{'─' * 70}")
        print(f"📋 Recette {i}/{len(urls)}")
        print(f"{'─' * 70}")
        print(f"URL: {url}")
        
        try:
            # Scraping
            print(f"\n1️⃣  Scraping...")
            recipe = scrape_recipe(url)
            print(f"   ✅ {recipe.title}")
            print(f"   📝 {len(recipe.ingredients)} ingrédients, {len(recipe.instructions)} étapes")
            
            # Transformation
            print(f"\n2️⃣  Formatage...")
            recipe_data = transform_to_cookidoo_format(
                recipe,
                servings=servings,
                prep_time=prep_time,
                total_time=total_time
            )
            print(f"   ✅ Recette formatée")
            
            # Upload (si pas en dry-run)
            if not dry_run:
                print(f"\n3️⃣  Upload vers Cookidoo...")
                recipe_id, recipe_url = await upload_to_cookidoo(recipe_data)
                print(f"   ✅ Créée!")
                print(f"   🆔 {recipe_id}")
                
                results.append({
                    "url": url,
                    "title": recipe_data["name"],
                    "recipe_id": recipe_id,
                    "recipe_url": recipe_url,
                    "status": "success"
                })
                success_count += 1
                
                # Délai entre les uploads pour ne pas surcharger l'API
                if i < len(urls):
                    print(f"\n⏳ Pause de {delay}s avant la prochaine recette...")
                    time.sleep(delay)
            else:
                print(f"\n🔍 Mode DRY-RUN: Pas d'upload")
                results.append({
                    "url": url,
                    "title": recipe_data["name"],
                    "status": "skipped"
                })
                success_count += 1
        
        except Exception as e:
            print(f"\n   ❌ Erreur: {e}")
            results.append({
                "url": url,
                "error": str(e),
                "status": "error"
            })
            error_count += 1
            
            # Continuer avec les autres recettes
            if i < len(urls):
                print(f"\n⏭️  Passage à la recette suivante...")
                time.sleep(2)
    
    # Résumé
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DE L'IMPORT")
    print("=" * 70)
    print(f"\n✅ Succès: {success_count}")
    print(f"❌ Échecs: {error_count}")
    print(f"📋 Total: {len(urls)}")
    
    if results:
        print("\n📝 Détails:")
        for result in results:
            if result["status"] == "success":
                print(f"\n  ✅ {result['title']}")
                print(f"     🔗 {result.get('recipe_url', 'N/A')}")
            elif result["status"] == "skipped":
                print(f"\n  ⏭️  {result['title']} (dry-run)")
            else:
                print(f"\n  ❌ {result['url']}")
                print(f"     Error: {result.get('error', 'Unknown')}")
    
    print("\n" + "=" * 70)
    
    return success_count, error_count


def parse_args() -> argparse.Namespace:
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Import batch de recettes Cookomix vers Cookidoo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Format du fichier d'URLs:
  Une URL par ligne
  Lignes vides et commentaires (#) ignorés
  
Exemple:
  # Recettes de base
  https://www.cookomix.com/recettes/pate-a-pizza-thermomix/
  https://www.cookomix.com/recettes/manouche-thermomix/
        """
    )
    
    parser.add_argument(
        "urls_file",
        type=Path,
        help="Fichier texte contenant les URLs Cookomix (une par ligne)"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Délai en secondes entre chaque import (défaut: 5)"
    )
    parser.add_argument(
        "--servings",
        type=int,
        help="Nombre de portions pour toutes les recettes (défaut: auto-détection)"
    )
    parser.add_argument(
        "--prep-time",
        type=int,
        default=30,
        help="Temps de préparation par défaut en minutes (défaut: 30)"
    )
    parser.add_argument(
        "--total-time",
        type=int,
        default=60,
        help="Temps total par défaut en minutes (défaut: 60)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode test: scraper sans uploader"
    )
    
    return parser.parse_args()


async def main_async() -> int:
    """Fonction principale asynchrone."""
    args = parse_args()
    
    # Vérifier que le fichier existe
    if not args.urls_file.exists():
        print(f"❌ Erreur: Fichier '{args.urls_file}' introuvable")
        return 1
    
    # Charger les URLs
    print(f"📂 Chargement des URLs depuis '{args.urls_file}'...")
    urls = load_urls_from_file(args.urls_file)
    
    if not urls:
        print("❌ Aucune URL valide trouvée dans le fichier")
        return 1
    
    print(f"✅ {len(urls)} URL(s) chargée(s)")
    
    if args.dry_run:
        print("🔍 Mode DRY-RUN activé (pas d'upload sur Cookidoo)")
    
    # Lancer l'import batch
    success, errors = await batch_import(
        urls=urls,
        delay=args.delay,
        dry_run=args.dry_run,
        servings=args.servings,
        prep_time=args.prep_time,
        total_time=args.total_time
    )
    
    return 0 if errors == 0 else 1


def main() -> int:
    """Point d'entrée principal."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
