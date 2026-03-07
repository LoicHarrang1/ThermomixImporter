#!/usr/bin/env python3
"""
Script d'intégration Cookomix → Cookidoo

Scrape une recette depuis Cookomix et la crée automatiquement sur votre compte Cookidoo.

Usage:
  python import_from_cookomix.py <url>
  python import_from_cookomix.py https://www.cookomix.com/recettes/manouche-thermomix/
  
Options:
  --servings N        Nombre de portions (défaut: détecté ou 4)
  --prep-time N       Temps de préparation en minutes (défaut: 30)
  --total-time N      Temps total en minutes (défaut: 60)
  --no-upload         Scraper seulement, ne pas uploader sur Cookidoo
  --dry-run           Afficher ce qui serait créé sans l'uploader
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent pour importer le scraper
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrape_cookomix import scrape_recipe, RecipeData
from cookidoo_service import CookidooService, load_cookidoo_credentials
from thermomix_formatter import enhance_instructions, is_thermomix_instruction
from tts_annotations import StepWithTTS, IngredientAnnotation, ModeAnnotation


def clean_html_entities(text: str) -> str:
    """Nettoie les entités HTML dans le texte."""
    import html
    return html.unescape(text)


def transform_to_cookidoo_format(
    recipe: RecipeData,
    servings: int | None = None,
    prep_time: int = 30,
    total_time: int = 60,
) -> dict:
    """
    Transforme les données Cookomix au format attendu par Cookidoo.
    
    Args:
        recipe: Données scrapées depuis Cookomix
        servings: Nombre de portions (None = auto-detect ou 4 par défaut)
        prep_time: Temps de préparation en minutes
        total_time: Temps total en minutes
        
    Returns:
        Dict avec les données au format Cookidoo
    """
    # Nettoyer le titre
    clean_title = clean_html_entities(recipe.title)
    
    # Déterminer le nombre de portions
    final_servings = servings or 4
    
    # Essayer d'extraire le nombre de portions depuis les ingrédients
    if not servings:
        for ingredient in recipe.ingredients:
            if "personnes" in ingredient.lower() or "portions" in ingredient.lower():
                import re
                match = re.search(r'(\d+)\s*(?:personnes?|portions?)', ingredient.lower())
                if match:
                    final_servings = int(match.group(1))
                    break
    
    # Nettoyer les ingrédients
    cleaned_ingredients = [clean_html_entities(ing) for ing in recipe.ingredients]
    
    # Nettoyer les instructions (enlever les numéros si présents)
    cleaned_instructions = []
    for instruction in recipe.instructions:
        # Enlever "1. ", "2. ", etc. si présent
        import re
        cleaned = re.sub(r'^\d+\.\s*', '', instruction)
        cleaned = clean_html_entities(cleaned)
        cleaned_instructions.append(cleaned)
    
    # Normaliser les instructions Thermomix (améliore la reconnaissance par Cookidoo)
    cleaned_instructions = enhance_instructions(cleaned_instructions, normalize=True)
    
    return {
        "name": clean_title,
        "ingredients": cleaned_ingredients,
        "steps": cleaned_instructions,
        "servings": final_servings,
        "prep_time": prep_time,
        "total_time": total_time,
        "hints": [f"Recette importée depuis Cookomix: {recipe.url}"]
    }


def extract_ingredient_from_step(step_text: str, ingredients: list) -> str | None:
    """
    Cherche si l'étape mentionne un ingrédient et retourne la mention exacte.
    
    Args:
        step_text: Texte de l'étape
        ingredients: Liste des ingrédients de la recette
    
    Returns:
        La mention d'ingrédient trouvée ou None
    """
    step_lower = step_text.lower()
    
    for ingredient in ingredients:
        # Extraire le nom de l'ingrédient (avant le tiret)
        ingredient_name = ingredient.split('-')[0].strip().lower()
        
        # Chercher le nom dans l'étape
        if ingredient_name in step_lower:
            # Trouver la mention complète (avec quantité) dans l'étape
            # Par exemple: "100 grammes de farine" ou "100g de farine"
            import re
            # Pattern: nombre + unité + "de/du/de la" + nom_ingredient
            # Exemple: "100 grammes de farine", "50g d'huile", "2 oeufs"
            pattern = rf'(\d+(?:\s*,\d+)?)\s*(?:grammes?|g|ml|l|cuillères?|c\.à\.c|cuillère|pincée|pincées|œufs?|oeufs?)\s*(?:de|du|de la|d\')?.*?{ingredient_name}'
            match = re.search(pattern, step_lower)
            
            if match:
                # Retourner la mention trouvée avec la bonne casse
                return step_text[match.start():match.end()]
    
    return None


def add_ingredient_annotations(steps_with_tts: list, ingredients: list) -> list:
    """
    Ajoute les annotations INGREDIENT aux étapes où les ingrédients sont mentionnés.
    
    Args:
        steps_with_tts: Liste des étapes TTS
        ingredients: Liste des ingrédients
    
    Returns:
        Liste des étapes avec annotations INGREDIENT ajoutées quand approprié
    """
    for step in steps_with_tts:
        # Chercher si cette étape utilise un ingrédient
        ingredient_mention = extract_ingredient_from_step(step.text, ingredients)
        
        if ingredient_mention:
            # Ajouter annotation INGREDIENT à cette étape
            annotation = IngredientAnnotation.create_ingredient_annotation(ingredient_mention)
            # Ajouter à la liste existante (peut y avoir aussi une annotation TTS)
            if step.annotations:
                step.annotations.append(annotation)
            else:
                step.annotations = [annotation]
    
    return steps_with_tts


async def upload_to_cookidoo(recipe_data: dict) -> tuple[str, str]:
    """
    Upload une recette sur Cookidoo avec annotations TTS.
    
    Args:
        recipe_data: Données de recette au format Cookidoo
        
    Returns:
        Tuple (recipe_id, recipe_url)
    """
    # Charger les credentials
    email, password = load_cookidoo_credentials()
    
    # Se connecter à Cookidoo
    service = CookidooService(email, password)
    
    try:
        print(f"🔐 Connexion à Cookidoo ({email})...")
        api = await service.login()
        print("   ✅ Connecté!")
        
        # Convertir les étapes en objets StepWithTTS
        print(f"\n⚡ Génération des annotations TTS...")
        steps_with_tts = [StepWithTTS.from_string(step) for step in recipe_data["steps"]]
        
        # Ajouter les annotations INGREDIENT pour les étapes qui mentionnent des ingrédients
        print(f"📦 Détection des ingrédients dans les étapes...")
        steps_with_tts = add_ingredient_annotations(steps_with_tts, recipe_data["ingredients"])
        
        # Compter les étapes avec annotations
        tts_count = sum(1 for step in steps_with_tts if any(a.get('type') == 'TTS' for a in step.annotations))
        mode_count = sum(1 for step in steps_with_tts if any(a.get('type') == 'MODE' for a in step.annotations))
        ingredient_count = sum(1 for step in steps_with_tts if any(a.get('type') == 'INGREDIENT' for a in step.annotations))
        print(f"   ✅ {tts_count} étapes avec paramètres Thermomix")
        print(f"   ✅ {mode_count} étapes avec modes de cuisson")
        print(f"   ✅ {ingredient_count} étapes avec ingrédients détectés")
        
        # Créer la recette AVEC annotations TTS
        print(f"\n📤 Création de la recette '{recipe_data['name']}'...")
        recipe_id = await service.create_custom_recipe_with_tts(
            name=recipe_data["name"],
            ingredients=recipe_data["ingredients"],
            steps=steps_with_tts,
            servings=recipe_data["servings"],
            prep_time=recipe_data["prep_time"],
            total_time=recipe_data["total_time"],
            hints=recipe_data.get("hints"),
        )
        
        print(f"   ✅ Créée: {recipe_id}")
        
        # Construire l'URL
        base_url = api.localization.url.split('/foundation')[0] if '/foundation' in api.localization.url else api.localization.url
        recipe_url = f"{base_url}/foundation/{api.localization.language}/recipes/custom-recipes/{recipe_id}"
        
        return recipe_id, recipe_url
        
    finally:
        await service.close()


def print_recipe_preview(recipe_data: dict) -> None:
    """Affiche un aperçu de la recette."""
    print("\n" + "=" * 70)
    print(f"📋 APERÇU DE LA RECETTE")
    print("=" * 70)
    print(f"\n🍽️  Nom: {recipe_data['name']}")
    print(f"👥 Portions: {recipe_data['servings']}")
    print(f"⏱️  Temps de préparation: {recipe_data['prep_time']} min")
    print(f"⏲️  Temps total: {recipe_data['total_time']} min")
    
    print(f"\n📝 Ingrédients ({len(recipe_data['ingredients'])}):")
    for i, ingredient in enumerate(recipe_data['ingredients'], 1):
        print(f"  {i}. {ingredient}")
    
    # Compter les instructions Thermomix et avec TTS
    from tts_annotations import StepWithTTS
    steps_with_tts = [StepWithTTS.from_string(step) for step in recipe_data['steps']]
    thermomix_count = sum(1 for step in steps_with_tts if step.annotations)
    
    print(f"\n👨‍🍳 Instructions ({len(recipe_data['steps'])}):")
    if thermomix_count > 0:
        print(f"   ⚡ {thermomix_count} étapes avec annotations TTS (paramètres Thermomix)")
    
    for i, (step_text, step_obj) in enumerate(zip(recipe_data['steps'], steps_with_tts), 1):
        # Mettre en évidence les instructions avec annotations TTS
        if step_obj.annotations:
            # Afficher les paramètres extraits
            ann = step_obj.annotations[0]
            data = ann.get('data', {})
            time_s = data.get('time', 0)
            temp = data.get('temperature')
            speed = data.get('speed')
            
            params = []
            if time_s:
                params.append(f"{time_s}s")
            if temp:
                params.append(f"{temp.get('value')}°{temp.get('unit')}")
            if speed:
                params.append(f"v{speed}")
            
            print(f"  {i}. ⚡ {step_text} {{{', '.join(params)}}}")
        else:
            print(f"  {i}. {step_text}")
    
    if recipe_data.get('hints'):
        print(f"\n💡 Astuces:")
        for hint in recipe_data['hints']:
            print(f"  • {hint}")
    
    print("\n" + "=" * 70)


def parse_args() -> argparse.Namespace:
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Importer une recette Cookomix vers Cookidoo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python import_from_cookomix.py https://www.cookomix.com/recettes/manouche-thermomix/
  python import_from_cookomix.py <url> --servings 6 --prep-time 20 --total-time 45
  python import_from_cookomix.py <url> --dry-run
        """
    )
    
    parser.add_argument(
        "url",
        help="URL de la recette Cookomix à importer"
    )
    parser.add_argument(
        "--servings",
        type=int,
        help="Nombre de portions (défaut: auto-détection ou 4)"
    )
    parser.add_argument(
        "--prep-time",
        type=int,
        default=30,
        help="Temps de préparation en minutes (défaut: 30)"
    )
    parser.add_argument(
        "--total-time",
        type=int,
        default=60,
        help="Temps total en minutes (défaut: 60)"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Scraper seulement, ne pas uploader sur Cookidoo"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher ce qui serait créé sans l'uploader"
    )
    
    return parser.parse_args()


async def main_async() -> int:
    """Fonction principale asynchrone."""
    args = parse_args()
    
    print("=" * 70)
    print("🍳 IMPORT COOKOMIX → COOKIDOO")
    print("=" * 70)
    
    # Étape 1: Scraping Cookomix
    print(f"\n1️⃣  Scraping depuis Cookomix...")
    print(f"   URL: {args.url}")
    
    try:
        recipe = scrape_recipe(args.url)
        print(f"   ✅ Recette récupérée: {recipe.title}")
        print(f"   📝 {len(recipe.ingredients)} ingrédients, {len(recipe.instructions)} étapes")
        print(f"   📊 Source: {recipe.source}")
    except Exception as e:
        print(f"   ❌ Erreur lors du scraping: {e}")
        return 1
    
    # Étape 2: Transformation au format Cookidoo
    print(f"\n2️⃣  Transformation au format Cookidoo...")
    recipe_data = transform_to_cookidoo_format(
        recipe,
        servings=args.servings,
        prep_time=args.prep_time,
        total_time=args.total_time
    )
    print(f"   ✅ Recette formatée")
    
    # Afficher l'aperçu
    print_recipe_preview(recipe_data)
    
    # Étape 3: Upload sur Cookidoo (si demandé)
    if args.no_upload or args.dry_run:
        if args.dry_run:
            print("\n🔍 Mode DRY-RUN: Aucune recette ne sera créée sur Cookidoo")
        else:
            print("\n⏸️  Option --no-upload: Recette non uploadée")
        print("\n✅ Scraping terminé avec succès!")
        return 0
    
    print(f"\n3️⃣  Upload vers Cookidoo...")
    
    try:
        recipe_id, recipe_url = await upload_to_cookidoo(recipe_data)
        
        print(f"   ✅ Recette créée avec succès!")
        print(f"\n" + "=" * 70)
        print(f"✨ RECETTE CRÉÉE SUR COOKIDOO")
        print(f"=" * 70)
        print(f"\n🆔 Recipe ID: {recipe_id}")
        print(f"🔗 URL: {recipe_url}")
        print(f"\n💡 Vous pouvez maintenant consulter votre recette dans l'app Cookidoo!")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"   ❌ Erreur lors de l'upload: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Point d'entrée principal."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
