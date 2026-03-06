"""
Module TTS (Thermomix Time Settings) Annotations
Génère et gère les annotations structurées pour les paramètres Thermomix
"""
import re
from typing import Optional, Dict, Any, Tuple
import json


class TTSAnnotation:
    """Génère des annotations TTS (Thermomix Time Settings) pour Cookidoo"""
    
    # Pattern pour détecter les paramètres Thermomix
    # Détecte: "X min/Y°C/vitesse Z" ou "X sec/vitesse Z" ou "X min/Varoma/vitesse Z" etc
    THERMOMIX_PATTERN = re.compile(
        r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(\d+(?:\.\d+)?|pétrin|turbo))?',
        re.IGNORECASE
    )
    
    @staticmethod
    def extract_parameters(text: str) -> Optional[Dict[str, Any]]:
        """
        Extrait les paramètres Thermomix du texte
        
        Args:
            text: Texte contenant les paramètres (ex: "2 min/37°C/vitesse 2" ou "5 min/Varoma/vitesse 1")
        
        Returns:
            Dict avec {time (secondes), temperature (°C ou special mode), speed} ou None
        """
        match = TTSAnnotation.THERMOMIX_PATTERN.search(text)
        if not match:
            return None
        
        # group(1) = minutes (optionnel)
        # group(2) = secondes après min (optionnel)
        # group(3) = secondes seules (optionnel)
        # group(4) = température numérique (optionnel)
        # group(5) = mode spécial (Varoma, Vapor - optionnel)
        # group(6) = vitesse (optionnel)
        
        minutes = int(match.group(1)) if match.group(1) else 0
        seconds_after_min = int(match.group(2)) if match.group(2) else 0
        seconds_only = int(match.group(3)) if match.group(3) else 0
        temperature = match.group(4)
        special_mode = match.group(5)
        speed = match.group(6)
        
        # Calculer le temps total en secondes
        total_seconds = (minutes * 60) + seconds_after_min + seconds_only
        
        # Gérer la température: soit numérique, soit un mode spécial
        temp_value = None
        if temperature:
            temp_value = int(temperature)
        elif special_mode:
            # Mode spécial comme Varoma
            temp_value = special_mode.lower()
        
        # Convertir les vitesses spéciales
        speed_mapping = {
            'pétrin': 'soft',
            'petrin': 'soft',
            'turbo': 'max',
            'cuillère': None,
            'cuillere': None,
            'varoma': None,
        }
        
        if speed:
            speed_lower = speed.lower()
            if speed_lower in speed_mapping:
                speed = speed_mapping[speed_lower]
        
        return {
            "time": total_seconds,
            "temperature": temp_value,
            "speed": speed
        }
    
    @staticmethod
    def find_position_in_text(text: str, params: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """
        Trouve la position (offset, length) des paramètres dans le texte
        
        Args:
            text: Texte complet
            params: Paramètres extraits
        
        Returns:
            Tuple (offset, length) ou None
        """
        match = TTSAnnotation.THERMOMIX_PATTERN.search(text)
        if not match:
            return None
        
        start = match.start()
        end = match.end()
        length = end - start
        
        return (start, length)
    
    @staticmethod
    def create_tts_annotation(
        text: str,
        time: int,
        temperature: Optional[int | str] = None,
        speed: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crée une annotation TTS complète
        
        Args:
            text: Texte contenant l'instruction
            time: Temps en secondes
            temperature: Température en °C (int) ou mode spécial (str) comme "varoma" (optionnel)
            speed: Vitesse (optionnel)
        
        Returns:
            Dict annotation TTS ou None si paramètres invalides
        """
        position = TTSAnnotation.find_position_in_text(text, {})
        if not position:
            return None
        
        offset, length = position
        
        # Construire la structure data
        data = {"time": time}
        
        if temperature is not None:
            if isinstance(temperature, str):
                # Mode spécial comme "varoma"
                data["temperature"] = {
                    "unit": "C",
                    "value": temperature
                }
            else:
                # Température numérique
                data["temperature"] = {
                    "unit": "C",
                    "value": str(temperature)
                }
        
        if speed is not None:
            data["speed"] = str(speed)
        
        return {
            "type": "TTS",
            "data": data,
            "position": {
                "offset": offset,
                "length": length
            }
        }
    
    @staticmethod
    def generate_from_text(text: str) -> Optional[Dict[str, Any]]:
        """
        Génère automatiquement une annotation TTS à partir du texte
        
        Args:
            text: Texte avec paramètres Thermomix
        
        Returns:
            Annotation TTS complète ou None
        """
        # Ignorer les instructions contenant "four" (instrucitons de four, pas Thermomix)
        if "four" in text.lower():
            return None
        
        params = TTSAnnotation.extract_parameters(text)
        if not params:
            return None
        
        return TTSAnnotation.create_tts_annotation(
            text,
            time=params["time"],
            temperature=params.get("temperature"),
            speed=params.get("speed")
        )


class IngredientAnnotation:
    """Génère des annotations INGREDIENT pour automatiser la pesée"""
    
    @staticmethod
    def create_ingredient_annotation(ingredient_text: str) -> Dict[str, Any]:
        """
        Crée une annotation INGREDIENT pour un ingrédient
        
        Args:
            ingredient_text: Texte de l'ingrédient (ex: "Farine - 200 grammes")
        
        Returns:
            Annotation INGREDIENT complète
        """
        return {
            "type": "INGREDIENT",
            "data": {
                "description": ingredient_text
            },
            "position": {
                "offset": 0,
                "length": len(ingredient_text)
            }
        }


class StepWithTTS:
    """Représente une étape avec annotations TTS optionnelles"""
    
    def __init__(self, text: str, step_type: str = "STEP"):
        """
        Initialise une étape
        
        Args:
            text: Texte de l'étape
            step_type: Type d'étape (défaut: "STEP")
        """
        self.text = text
        self.type = step_type
        self.annotations = []
    
    def add_tts_annotation(self) -> bool:
        """
        Ajoute automatiquement une annotation TTS si le texte contient des paramètres
        
        Returns:
            True si annotation ajoutée, False sinon
        """
        annotation = TTSAnnotation.generate_from_text(self.text)
        if annotation:
            self.annotations = [annotation]
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'étape en dictionnaire pour l'API"""
        return {
            "type": self.type,
            "text": self.text,
            "annotations": self.annotations,
            "missedUsages": []
        }
    
    @staticmethod
    def from_string(text: str) -> "StepWithTTS":
        """Crée une étape avec annotations TTS automatiques"""
        step = StepWithTTS(text)
        step.add_tts_annotation()
        return step


# ============================================================================
# HELPERS
# ============================================================================

def normalize_thermomix_text(text: str) -> str:
    """
    Normalise le texte des paramètres Thermomix pour améliorer la reconnaissance
    
    Exemple: "2min/37°c/vitesse2" → "2 min / 37°C / vitesse 2"
              "10sec/vitesse10" → "10 sec / vitesse 10"
    
    Args:
        text: Texte brut
    
    Returns:
        Texte normalisé
    """
    # Normaliser les espaces autour des paramètres
    text = re.sub(r'(\d+)\s*min', r'\1 min', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*sec', r'\1 sec', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*s(?:\s|/|$)', r'\1 sec ', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*°\s*[CcFf]', lambda m: f"{m.group(1)}°C", text)
    text = re.sub(r'vitesse\s*([\d.]+|pétrin|turbo)', r'vitesse \1', text, flags=re.IGNORECASE)
    
    # Normaliser les séparateurs
    text = re.sub(r'\s*/\s*', ' / ', text)
    
    return text


if __name__ == "__main__":
    # Tests
    print("=" * 80)
    print("🧪 TESTS - TTS ANNOTATIONS")
    print("=" * 80)
    
    test_cases = [
        "2 min/37°C/vitesse 2",
        "2min/37°c/vitesse2",
        "Chauffer 3 min / 40°C / vitesse 3",
        "Pulvériser 10 sec / vitesse 10",
        "Mélanger 30 sec / vitesse 2",
        "Cuire 12 min / 90°C / vitesse 1",
        "Turbo / 5 sec",
        "Instruction sans paramètres",
    ]
    
    for text in test_cases:
        print(f"\n🔍 Texte: '{text}'")
        
        # Normaliser
        normalized = normalize_thermomix_text(text)
        print(f"   Normalisé: '{normalized}'")
        
        # Extraire
        params = TTSAnnotation.extract_parameters(normalized)
        if params:
            print(f"   ✅ Paramètres trouvés:")
            print(f"      - Temps: {params['time']}s")
            if params.get('temperature'):
                print(f"      - Température: {params['temperature']}°C")
            if params.get('speed'):
                print(f"      - Vitesse: {params['speed']}")
            
            # Générer annotation
            annotation = TTSAnnotation.generate_from_text(normalized)
            if annotation:
                print(f"   ✅ Annotation TTS générée:")
                print(json.dumps(annotation, ensure_ascii=False, indent=6))
        else:
            print(f"   ❌ Pas de paramètres Thermomix détectés")
        
        # Créer étape avec TTS
        step = StepWithTTS.from_string(normalized)
        has_tts = "✅ TTS" if step.annotations else "❌ No TTS"
        print(f"   {has_tts}")
    
    print("\n" + "=" * 80)
