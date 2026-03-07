#!/usr/bin/env python3
"""Test de détection des modes de cuisson"""

from tts_annotations import ModeAnnotation, TTSAnnotation, StepWithTTS
import json


def test_mode_detection():
    """Test la détection des modes de cuisson"""
    
    test_cases = [
        # Modes avec durée
        ("Pétrin /5 min", "petrin", 300),
        ("Pétrin 5 min", "petrin", 300),
        ("Pétrin / 5 minutes", "petrin", 300),
        ("Turbo / 2 min", "turbo", 120),
        ("Turbo 30 sec", "turbo", 30),
        ("Mixage / 1 min", "mixage", 60),
        
        # Modes avec température
        ("Réchauffer /65°C", "rechauffer", 65),
        ("Réchauffer 65°C", "rechauffer", 65),
        ("Réchauffer / 60°C", "rechauffer", 60),
        
        # Rice cooker
        ("Rice cooker / 10 min", "rice_cooker", 600),
    ]
    
    print("🧪 TEST - DÉTECTION DES MODES DE CUISSON")
    print("=" * 80)
    
    for text, expected_mode_type, expected_value in test_cases:
        print(f"\n✓ Test: '{text}'")
        
        mode_data = ModeAnnotation.extract_mode(text)
        
        if not mode_data:
            print(f"  ❌ ERREUR: Aucun mode détecté!")
            continue
        
        if mode_data["type"] != expected_mode_type:
            print(f"  ❌ ERREUR: Type de mode={mode_data['type']}, attendu={expected_mode_type}")
            continue
        
        # Vérifier la durée ou la température
        if mode_data["time"] is not None and mode_data["time"] != expected_value:
            print(f"  ❌ ERREUR: time={mode_data['time']}, attendu={expected_value}")
            continue
        
        if mode_data["temperature"] is not None and mode_data["temperature"] != expected_value:
            print(f"  ❌ ERREUR: temperature={mode_data['temperature']}, attendu={expected_value}")
            continue
        
        print(f"  ✅ Mode détecté avec succès")
        print(f"     Data: {mode_data}")
    
    print("\n" + "=" * 80)


def test_mode_annotation_generation():
    """Test la génération complète d'annotations MODE"""
    
    test_cases = [
        "Pétrin /5 min",
        "Réchauffer 65°C",
        "Turbo / 2 min 30 sec",
    ]
    
    print("\n🧪 TEST - GÉNÉRATION D'ANNOTATIONS MODE")
    print("=" * 80)
    
    for text in test_cases:
        print(f"\n✓ Test: '{text}'")
        
        annotation = ModeAnnotation.generate_from_text(text)
        
        if not annotation:
            print(f"  ❌ ERREUR: Aucune annotation générée!")
            continue
        
        print(f"  ✅ Annotation générée:")
        print(f"     {json.dumps(annotation, indent=6)}")
    
    print("\n" + "=" * 80)


def test_stepwithtts_mode_detection():
    """Test que StepWithTTS détecte les modes correctement"""
    
    test_cases = [
        ("Pétrin /5 min", "MODE"),
        ("Réchauffer 65°C", "MODE"),
        ("Chauffer 2 min / 37°C / vitesse 2", "TTS"),  # Pas un mode, c'est une TTS
        ("Mélanger 5 min / vitesse pétrin", "TTS"),     # C'est une TTS, pas un MODE
    ]
    
    print("\n🧪 TEST - STEPWITHTTS MODE VS TTS")
    print("=" * 80)
    
    for text, expected_annotation_type in test_cases:
        print(f"\n✓ Test: '{text}'")
        
        step = StepWithTTS.from_string(text)
        
        if not step.annotations:
            if expected_annotation_type is None:
                print(f"  ✅ Aucune annotation (attendu)")
            else:
                print(f"  ❌ ERREUR: Aucune annotation, attendu {expected_annotation_type}")
            continue
        
        annotation_type = step.annotations[0].get('type')
        if annotation_type == expected_annotation_type:
            print(f"  ✅ Annotation détectée: {annotation_type}")
            print(f"     {json.dumps(step.annotations[0], indent=6)}")
        else:
            print(f"  ❌ ERREUR: Type={annotation_type}, attendu={expected_annotation_type}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_mode_detection()
    test_mode_annotation_generation()
    test_stepwithtts_mode_detection()
    print("\n✅ TESTS TERMINÉS")
