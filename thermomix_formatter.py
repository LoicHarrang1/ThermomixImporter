"""
Utilitaires pour formatter et enrichir les instructions Thermomix.
"""
import re
from typing import List


# Patterns de reconnaissance Thermomix
THERMOMIX_PARAMS_PATTERN = re.compile(
    r'(\d+)\s*(min|sec|secondes?|minutes?)\s*/\s*(\d+)°C\s*/\s*vitesse\s+(\d+|pétrin|mijotage)',
    re.IGNORECASE
)


def is_thermomix_instruction(text: str) -> bool:
    """
    Détecte si une instruction contient des paramètres Thermomix.
    
    Args:
        text: Texte de l'instruction
        
    Returns:
        True si l'instruction contient des paramètres Thermomix reconnus
    """
    thermomix_keywords = [
        r'\d+\s*sec',
        r'\d+\s*min',
        r'vitesse\s+\d+',
        r'vitesse\s+pétrin',
        r'vitesse\s+mijotage',
        r'\d+°C',
        r'sens\s+inverse',
        r'turbo',
        r'varoma',
    ]
    
    for pattern in thermomix_keywords:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def normalize_thermomix_instruction(text: str) -> str:
    """
    Normalise une instruction Thermomix pour améliorer la reconnaissance par l'API.
    
    Examples:
        "Chauffer 2min / 37°c / vitesse2" -> "Chauffer 2 min / 37°C / vitesse 2"
        "Mélanger 30sec/vitesse 4" -> "Mélanger 30 sec / vitesse 4"
    
    Args:
        text: Texte de l'instruction
        
    Returns:
        Instruction normalisée
    """
    result = text
    
    # Normaliser les unités de temps
    result = re.sub(r'(\d+)\s*(sec|secondes?)', r'\1 sec', result, flags=re.IGNORECASE)
    result = re.sub(r'(\d+)\s*(min|minutes?)', r'\1 min', result, flags=re.IGNORECASE)
    
    # Normaliser les températures
    result = re.sub(r'(\d+)\s*°\s*c\b', r'\1°C', result, flags=re.IGNORECASE)
    
    # Normaliser les vitesses
    result = re.sub(r'vitesse\s*(\d+)', r'vitesse \1', result, flags=re.IGNORECASE)
    result = re.sub(r'vitesse\s+(pétrin|mijotage)', r'vitesse \1', result, flags=re.IGNORECASE)
    
    # Ajouter des espaces autour des "/"
    result = re.sub(r'\s*/\s*', ' / ', result)
    
    # Normaliser "sens inverse"
    result = re.sub(r'sens\s+inverse', 'sens inverse 🔄', result, flags=re.IGNORECASE)
    if '🔄' in result:
        result = result.replace('sens inverse 🔄 🔄', 'sens inverse 🔄')
    
    # Normaliser les modes
    result = re.sub(r'\bturbo\b', 'Turbo', result, flags=re.IGNORECASE)
    result = re.sub(r'\bvaroma\b', 'Varoma', result, flags=re.IGNORECASE)
    
    return result


def extract_thermomix_params(text: str) -> dict | None:
    """
    Extrait les paramètres Thermomix structurés depuis le texte.
    
    Args:
        text: Texte de l'instruction
        
    Returns:
        Dict avec time, temperature, speed ou None si pas de paramètres
    """
    # Pattern principal: X min / Y°C / vitesse Z
    match = THERMOMIX_PARAMS_PATTERN.search(text)
    if match:
        time_val = match.group(1)
        time_unit = match.group(2)
        temperature = match.group(3)
        speed = match.group(4)
        
        # Convertir en secondes
        time_seconds = int(time_val)
        if time_unit.lower().startswith('min'):
            time_seconds *= 60
        
        return {
            'time': time_seconds,
            'temperature': int(temperature),
            'speed': speed,
        }
    
    # Essayer de parser des patterns partiels
    params = {}
    
    # Temps seul
    time_match = re.search(r'(\d+)\s*(min|sec|secondes?|minutes?)', text, re.IGNORECASE)
    if time_match:
        time_val = int(time_match.group(1))
        time_unit = time_match.group(2)
        if time_unit.lower().startswith('min'):
            time_val *= 60
        params['time'] = time_val
    
    # Température seule
    temp_match = re.search(r'(\d+)°C', text)
    if temp_match:
        params['temperature'] = int(temp_match.group(1))
    
    # Vitesse seule
    speed_match = re.search(r'vitesse\s+(\d+|pétrin|mijotage)', text, re.IGNORECASE)
    if speed_match:
        params['speed'] = speed_match.group(1)
    
    return params if params else None


def enhance_instructions(instructions: List[str], normalize: bool = True) -> List[str]:
    """
    Améliore une liste d'instructions pour mieux être reconnue par Cookidoo.
    
    Args:
        instructions: Liste des instructions originales
        normalize: Si True, normalise le format des paramètres Thermomix
        
    Returns:
        Liste des instructions enrichies
    """
    enhanced = []
    
    for instruction in instructions:
        result = instruction
        
        if normalize and is_thermomix_instruction(result):
            result = normalize_thermomix_instruction(result)
        
        enhanced.append(result)
    
    return enhanced


def format_thermomix_instruction(
    action: str,
    time: int | None = None,
    temperature: int | None = None,
    speed: str | int | None = None,
    reverse: bool = False,
    mode: str | None = None,
) -> str:
    """
    Crée une instruction Thermomix formatée correctement.
    
    Args:
        action: Action principale (ex: "Mélanger", "Chauffer", "Mixer")
        time: Temps en secondes
        temperature: Température en °C
        speed: Vitesse (1-10, "pétrin", "mijotage")
        reverse: Si True, ajoute "sens inverse"
        mode: Mode spécial ("Turbo", "Varoma")
        
    Returns:
        Instruction formatée
        
    Examples:
        >>> format_thermomix_instruction("Mélanger", 120, 37, 2)
        "Mélanger 2 min / 37°C / vitesse 2"
        
        >>> format_thermomix_instruction("Mixer", 30, speed=5, reverse=True)
        "Mixer 30 sec / sens inverse 🔄 / vitesse 5"
    """
    parts = [action]
    
    params = []
    
    # Temps
    if time is not None:
        if time >= 60:
            params.append(f"{time // 60} min")
        else:
            params.append(f"{time} sec")
    
    # Température
    if temperature is not None:
        params.append(f"{temperature}°C")
    
    # Sens inverse
    if reverse:
        params.append("sens inverse 🔄")
    
    # Vitesse
    if speed is not None:
        params.append(f"vitesse {speed}")
    
    # Mode spécial
    if mode:
        params.append(mode)
    
    if params:
        parts.append(" / ".join(params))
    
    return " ".join(parts) + "."


# Exemples d'utilisation
if __name__ == "__main__":
    # Test de normalisation
    tests = [
        "Chauffer 2min/37°c/vitesse2",
        "Mélanger 30sec / vitesse 4",
        "Mixer 10 sec/sens inverse/vitesse 10",
        "Pétrir 3 min / vitesse pétrin",
    ]
    
    print("TESTS DE NORMALISATION:\n")
    for test in tests:
        normalized = normalize_thermomix_instruction(test)
        params = extract_thermomix_params(normalized)
        print(f"Original:   {test}")
        print(f"Normalisé:  {normalized}")
        print(f"Paramètres: {params}")
        print()
    
    print("\nTESTS DE CRÉATION D'INSTRUCTIONS:\n")
    
    examples = [
        ("Mélanger les ingrédients", 120, 37, 2, False, None),
        ("Mixer", 30, None, 5, True, None),
        ("Pétrir la pâte", 180, None, "pétrin", False, None),
        ("Cuire", 900, None, "mijotage", False, "Varoma"),
    ]
    
    for action, time, temp, speed, reverse, mode in examples:
        instruction = format_thermomix_instruction(action, time, temp, speed, reverse, mode)
        print(f"✅ {instruction}")
