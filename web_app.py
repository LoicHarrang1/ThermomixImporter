#!/usr/bin/env python3
"""
Interface web pour Cookomix → Cookidoo
Application Flask simple pour importer des recettes
"""

import asyncio
from flask import Flask, render_template, request, jsonify, session
import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrape_cookomix import scrape_recipe, RecipeData
from cookidoo_service import CookidooService, load_cookidoo_credentials
from thermomix_formatter import enhance_instructions
from tts_annotations import StepWithTTS, IngredientAnnotation, ModeAnnotation
import html

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-prodution'
app.permanent_session_lifetime = timedelta(hours=2)


def clean_html_entities(text: str) -> str:
    """Nettoie les entités HTML dans le texte."""
    return html.unescape(text)


def transform_to_cookidoo_format(recipe: RecipeData, servings: int | None = None, prep_time: int = 30, total_time: int = 60) -> dict:
    """Transforme les données Cookomix au format Cookidoo."""
    detected_servings = getattr(recipe, 'servings', None)
    final_servings = servings or detected_servings or 4
    
    clean_title = clean_html_entities(recipe.title or "").strip()
    cleaned_ingredients = [clean_html_entities(ing).strip() for ing in (recipe.ingredients or [])]
    
    cleaned_instructions = []
    for instruction in (recipe.instructions or []):
        import re
        cleaned = re.sub(r'^\d+\.\s*', '', instruction)
        cleaned = clean_html_entities(cleaned)
        cleaned_instructions.append(cleaned)
    
    cleaned_instructions = enhance_instructions(cleaned_instructions, normalize=True)
    
    return {
        "name": clean_title,
        "ingredients": cleaned_ingredients,
        "steps": cleaned_instructions,
        "servings": final_servings,
        "prep_time": prep_time,
        "total_time": total_time,
        "url": recipe.url
    }


def extract_ingredient_from_step(step_text: str, ingredients: list) -> str | None:
    """Cherche si l'étape mentionne un ingrédient."""
    step_lower = step_text.lower()
    
    for ingredient in ingredients:
        ingredient_name = ingredient.split('-')[0].strip().lower()
        
        if ingredient_name in step_lower:
            import re
            pattern = rf'(\d+(?:\s*,\d+)?)\s*(?:grammes?|g|ml|l|cuillères?|c\.à\.c|cuillère|pincée|pincées|œufs?|oeufs?)\s*(?:de|du|de la|d\')?.*?{ingredient_name}'
            match = re.search(pattern, step_lower)
            
            if match:
                return step_text[match.start():match.end()]
    
    return None


def add_ingredient_annotations(steps_with_tts: list, ingredients: list) -> list:
    """Ajoute les annotations INGREDIENT aux étapes."""
    for step in steps_with_tts:
        ingredient_mention = extract_ingredient_from_step(step.text, ingredients)
        
        if ingredient_mention:
            annotation = IngredientAnnotation.create_ingredient_annotation(ingredient_mention)
            if step.annotations:
                step.annotations.append(annotation)
            else:
                step.annotations = [annotation]
    
    return steps_with_tts


def format_annotations_for_display(annotations: list) -> dict:
    """Formate les annotations pour l'affichage HTML."""
    result = {}
    for ann in annotations:
        ann_type = ann.get('type', 'UNKNOWN')
        data = ann.get('data', {})
        
        if ann_type == 'TTS':
            time_s = data.get('time', 0)
            temp = data.get('temperature')
            speed = data.get('speed')
            
            params = []
            if time_s:
                minutes = time_s // 60
                seconds = time_s % 60
                if minutes > 0 and seconds > 0:
                    params.append(f"{minutes}m{seconds}s")
                elif minutes > 0:
                    params.append(f"{minutes}m")
                else:
                    params.append(f"{seconds}s")
            
            if temp:
                if isinstance(temp, dict):
                    value = temp.get('value', '')
                    unit = temp.get('unit', 'C')
                    params.append(f"{value}°{unit}")
                else:
                    params.append(f"{temp}°C")
            
            if speed:
                params.append(f"v{speed}")
            
            result['TTS'] = ' | '.join(params)
        
        elif ann_type == 'INGREDIENT':
            result['INGREDIENT'] = data.get('description', '')
    
    return result


@app.route('/')
def index():
    """Page d'accueil."""
    return render_template('index.html')


@app.route('/import-direct', methods=['POST'])
def import_direct():
    """Importe directement une recette sur Cookidoo."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL requise'}), 400
        
        # Scraper la recette (fonction synchrone)
        recipe = scrape_recipe(url)
        
        if not recipe or not recipe.title:
            return jsonify({'error': 'Impossible de trouver la recette à cette URL'}), 400
        
        # Transformer au format Cookidoo
        recipe_data = transform_to_cookidoo_format(recipe)
        
        # Préparer les étapes avec annotations
        steps_with_tts = [StepWithTTS.from_string(step) for step in recipe_data["steps"]]
        steps_with_tts = add_ingredient_annotations(steps_with_tts, recipe_data["ingredients"])
        
        # Charger les credentials
        email, password = load_cookidoo_credentials()
        service = CookidooService(email, password)
        
        # Wrapper async
        async def do_import():
            try:
                api = await service.login()

                # Créer la recette
                recipe_id = await service.create_custom_recipe_with_tts(
                    name=recipe_data['name'],
                    ingredients=recipe_data['ingredients'],
                    steps=steps_with_tts,
                    servings=recipe_data['servings'],
                    prep_time=recipe_data['prep_time'],
                    total_time=recipe_data['total_time'],
                )

                # Construire l'URL
                base_url = api.localization.url.split('/foundation')[0] if '/foundation' in api.localization.url else api.localization.url
                recipe_url = f"{base_url}/foundation/{api.localization.language}/recipes/custom-recipes/{recipe_id}"

                return recipe_id, recipe_url
            finally:
                await service.close()

        recipe_id, recipe_url = asyncio.run(do_import())

        return jsonify({
            'success': True,
            'recipe_id': recipe_id,
            'recipe_url': recipe_url,
            'recipe_name': recipe_data['name']
        })
    
    except Exception as e:
        return jsonify({'error': f'Erreur lors de l\'import: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
