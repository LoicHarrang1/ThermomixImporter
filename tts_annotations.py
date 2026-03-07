"""
Module TTS (Thermomix Time Settings) Annotations
Génère et gère les annotations structurées pour les paramètres Thermomix
"""
import re
from typing import Optional, Dict, Any, Tuple
import json


class TTSAnnotation:
    """Génère des annotations TTS (Thermomix Time Settings) pour Cookidoo"""
    
    # Pattern pour détecter les paramètres Thermomix (SANS vitesses spéciales qui sont des modes)
    # Détecte: "X min/Y°C/vitesse Z" ou "X sec/vitesse Z" ou "X min/Varoma/vitesse Z" etc
    # Mais EXCLUT vitesse pétrin/turbo/mixage/rechauffage/rice cooker
    THERMOMIX_PATTERN = re.compile(
        r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(\d+(?:\.\d+)?))?',
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


class ModeAnnotation:
    """Génère des annotations MODE pour les modes de cuisson Thermomix"""
    
    # Patterns pour détecter les modes de cuisson
    # Ces patterns détectent les vitesses spéciales (pétrin, turbo, etc.) dans les TTS
    # Format: "X min/vitesse pétrin" ou "X sec/vitesse turbo" etc
    PETRIN_MODE_FROM_TTS = re.compile(r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(pétrin|petrin))\b', re.IGNORECASE)
    TURBO_MODE_FROM_TTS = re.compile(r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(turbo))\b', re.IGNORECASE)
    MIXAGE_MODE_FROM_TTS = re.compile(r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(mixage))\b', re.IGNORECASE)
    RECHAUFFAGE_MODE_FROM_TTS = re.compile(r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(rechauffage|réchauffage))\b', re.IGNORECASE)
    RICE_COOKER_MODE_FROM_TTS = re.compile(r'(?:(?:(\d+)\s*min(?:\s*(?:et)?\s*(\d+)\s*(?:sec|s))?)|(?:(\d+)\s*(?:sec|s)))(?:\s*/\s*(?:(\d+)°?[CcFf]|(Varoma|Vapor)))?(?:\s*/\s*vitesse\s*(rice\s*cooker))\b', re.IGNORECASE)
    
    # Patterns pour détecter les modes simples (comme dans les payloads de Cookidoo)
    # Format: "Pétrin /5 min" ou "Réchauffer 65°C"
    PETRIN_MODE = re.compile(r'\bpétrin\s*/?(?:\s*)(\d+)\s*(min|minutes|sec|secondes|s)\b', re.IGNORECASE)
    TURBO_MODE = re.compile(r'\bturbo\s*/?(?:\s*)(\d+)\s*(min|minutes|sec|secondes|s)\b', re.IGNORECASE)
    MIXAGE_MODE = re.compile(r'\bmixage\s*/?(?:\s*)(\d+)\s*(min|minutes|sec|secondes|s)\b', re.IGNORECASE)
    RECHAUFFER_MODE = re.compile(r'\brechauffage\s*/?(?:\s*)(\d+)°?c?|\bréchauffer\s*/?(?:\s*)(\d+)°?c?\b', re.IGNORECASE)
    RICE_COOKER_MODE = re.compile(r'\brice\s+cooker\s*/?(?:\s*)(\d+)\s*(min|minutes|sec|secondes|s)\b', re.IGNORECASE)
    
    MODE_MAPPING = {
        'petrin': ('dough', 'soft', None),
        'turbo': ('turbo', '2', None),
        'mixage': ('mixing', '1', None),
        'rechauffage': ('warm_up', '1', 'temperature'),
        'rechauffer': ('warm_up', '1', 'temperature'),  # alias
        'rice_cooker': ('rice_cooker', '1', None),
    }
    
    @staticmethod
    def extract_mode_from_tts(text: str) -> Optional[Dict[str, Any]]:
        """
        Extrait un mode de cuisson depuis une instruction TTS
        (ex: "Mélanger 1 min/vitesse pétrin")
        
        Args:
            text: Texte contenant des paramètres avec vitesse spéciale
        
        Returns:
            Dict avec {mode_type, time, temperature} ou None
        """
        # Chercher Pétrin
        match = ModeAnnotation.PETRIN_MODE_FROM_TTS.search(text)
        if match:
            minutes = int(match.group(1)) if match.group(1) else 0
            seconds_after_min = int(match.group(2)) if match.group(2) else 0
            seconds_only = int(match.group(3)) if match.group(3) else 0
            total_seconds = (minutes * 60) + seconds_after_min + seconds_only
            temperature = int(match.group(4)) if match.group(4) else None
            return {"type": "petrin", "time": total_seconds, "temperature": temperature}
        
        # Chercher Turbo
        match = ModeAnnotation.TURBO_MODE_FROM_TTS.search(text)
        if match:
            minutes = int(match.group(1)) if match.group(1) else 0
            seconds_after_min = int(match.group(2)) if match.group(2) else 0
            seconds_only = int(match.group(3)) if match.group(3) else 0
            total_seconds = (minutes * 60) + seconds_after_min + seconds_only
            temperature = int(match.group(4)) if match.group(4) else None
            return {"type": "turbo", "time": total_seconds, "temperature": temperature}
        
        # Chercher Mixage
        match = ModeAnnotation.MIXAGE_MODE_FROM_TTS.search(text)
        if match:
            minutes = int(match.group(1)) if match.group(1) else 0
            seconds_after_min = int(match.group(2)) if match.group(2) else 0
            seconds_only = int(match.group(3)) if match.group(3) else 0
            total_seconds = (minutes * 60) + seconds_after_min + seconds_only
            temperature = int(match.group(4)) if match.group(4) else None
            return {"type": "mixage", "time": total_seconds, "temperature": temperature}
        
        # Chercher Rechauffage
        match = ModeAnnotation.RECHAUFFAGE_MODE_FROM_TTS.search(text)
        if match:
            minutes = int(match.group(1)) if match.group(1) else 0
            seconds_after_min = int(match.group(2)) if match.group(2) else 0
            seconds_only = int(match.group(3)) if match.group(3) else 0
            total_seconds = (minutes * 60) + seconds_after_min + seconds_only
            temperature = int(match.group(4)) if match.group(4) else None
            return {"type": "rechauffage", "time": total_seconds, "temperature": temperature}
        
        # Chercher Rice Cooker
        match = ModeAnnotation.RICE_COOKER_MODE_FROM_TTS.search(text)
        if match:
            minutes = int(match.group(1)) if match.group(1) else 0
            seconds_after_min = int(match.group(2)) if match.group(2) else 0
            seconds_only = int(match.group(3)) if match.group(3) else 0
            total_seconds = (minutes * 60) + seconds_after_min + seconds_only
            temperature = int(match.group(4)) if match.group(4) else None
            return {"type": "rice_cooker", "time": total_seconds, "temperature": temperature}
        
        return None
    
    @staticmethod
    def extract_mode(text: str) -> Optional[Dict[str, Any]]:
        """
        Détecte et extrait un mode de cuisson du texte
        
        Args:
            text: Texte contenant un mode de cuisson
        
        Returns:
            Dict avec {mode_type, time, temperature} ou None
        """
        # D'abord essayer de trouver un mode depuis une TTS (vitesse spéciale)
        mode_data = ModeAnnotation.extract_mode_from_tts(text)
        if mode_data:
            return mode_data
        
        # Chercher Pétrin simple
        match = ModeAnnotation.PETRIN_MODE.search(text)
        if match:
            duration = int(match.group(1))
            unit = match.group(2).lower()
            time_seconds = duration * 60 if unit in ['min', 'minutes'] else duration
            return {"type": "petrin", "time": time_seconds, "temperature": None}
        
        # Chercher Turbo simple
        match = ModeAnnotation.TURBO_MODE.search(text)
        if match:
            duration = int(match.group(1))
            unit = match.group(2).lower()
            time_seconds = duration * 60 if unit in ['min', 'minutes'] else duration
            return {"type": "turbo", "time": time_seconds, "temperature": None}
        
        # Chercher Mixage simple
        match = ModeAnnotation.MIXAGE_MODE.search(text)
        if match:
            duration = int(match.group(1))
            unit = match.group(2).lower()
            time_seconds = duration * 60 if unit in ['min', 'minutes'] else duration
            return {"type": "mixage", "time": time_seconds, "temperature": None}
        
        # Chercher Réchauffage simple
        match = ModeAnnotation.RECHAUFFER_MODE.search(text)
        if match:
            temperature = int(match.group(1)) if match.group(1) else int(match.group(2)) if match.group(2) else None
            if temperature:
                return {"type": "rechauffage", "time": None, "temperature": temperature}
        
        # Chercher Rice Cooker simple
        match = ModeAnnotation.RICE_COOKER_MODE.search(text)
        if match:
            duration = int(match.group(1))
            unit = match.group(2).lower()
            time_seconds = duration * 60 if unit in ['min', 'minutes'] else duration
            return {"type": "rice_cooker", "time": time_seconds, "temperature": None}
        
        return None
    
    @staticmethod
    @staticmethod
    def find_position_in_text(text: str, mode_data: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """
        Trouve la position du mode dans le texte
        
        Args:
            text: Texte complet
            mode_data: Data du mode extrait
        
        Returns:
            Tuple (offset, length) ou None
        """
        # Chercher patterns depuis TTS d'abord (plus spécifiques)
        patterns_from_tts = [
            ModeAnnotation.PETRIN_MODE_FROM_TTS,
            ModeAnnotation.TURBO_MODE_FROM_TTS,
            ModeAnnotation.MIXAGE_MODE_FROM_TTS,
            ModeAnnotation.RECHAUFFAGE_MODE_FROM_TTS,
            ModeAnnotation.RICE_COOKER_MODE_FROM_TTS
        ]
        
        for pattern in patterns_from_tts:
            match = pattern.search(text)
            if match:
                return (match.start(), match.end() - match.start())
        
        # Chercher patterns simples
        patterns = [
            ModeAnnotation.PETRIN_MODE,
            ModeAnnotation.TURBO_MODE,
            ModeAnnotation.MIXAGE_MODE,
            ModeAnnotation.RECHAUFFER_MODE,
            ModeAnnotation.RICE_COOKER_MODE
        ]
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return (match.start(), match.end() - match.start())
        
        return None
    
    @staticmethod
    def create_mode_annotation(text: str, mode_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crée une annotation MODE complète
        
        Args:
            text: Texte contenant le mode
            mode_data: Données extraites du mode
        
        Returns:
            Annotation MODE ou None
        """
        position = ModeAnnotation.find_position_in_text(text, mode_data)
        if not position:
            return None
        
        offset, length = position
        mode_type = mode_data["type"]
        mode_name, speed, temp_type = ModeAnnotation.MODE_MAPPING.get(mode_type, (None, None, None))
        
        if not mode_name:
            return None
        
        data = {}
        
        if mode_data["time"] is not None:
            data["time"] = mode_data["time"]
        
        if mode_data["temperature"] is not None:
            data["temperature"] = {
                "unit": "C",
                "value": str(mode_data["temperature"])
            }
        
        if speed:
            data["speed"] = speed
        
        return {
            "type": "MODE",
            "name": mode_name,
            "data": data,
            "position": {
                "offset": offset,
                "length": length
            }
        }
    
    @staticmethod
    def generate_from_text(text: str) -> Optional[Dict[str, Any]]:
        """
        Génère automatiquement une annotation MODE à partir du texte
        
        Args:
            text: Texte avec un mode de cuisson
        
        Returns:
            Annotation MODE complète ou None
        """
        mode_data = ModeAnnotation.extract_mode(text)
        if not mode_data:
            return None
        
        return ModeAnnotation.create_mode_annotation(text, mode_data)


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
        Ajoute automatiquement des annotations (MODE ou TTS) au texte
        
        Les modes de cuisson (Pétrin, Turbo, etc.) sont détectés d'abord.
        Si pas de mode, une annotation TTS est ajoutée si les paramètres Thermomix sont présents.
        
        Returns:
            True si annotation ajoutée, False sinon
        """
        # D'abord chercher un MODE
        mode_annotation = ModeAnnotation.generate_from_text(self.text)
        if mode_annotation:
            self.annotations = [mode_annotation]
            return True
        
        # Sinon chercher une TTS
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
