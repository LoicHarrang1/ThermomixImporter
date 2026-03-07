#!/usr/bin/env python3
"""Test de détection des modes depuis les TTS Cookomix"""

from tts_annotations import ModeAnnotation, StepWithTTS
import json

# Tests depuis les formats Cookomix
cookomix_instructions = [
    "Mélanger 1 min/vitesse pétrin.",
    "Mélanger 5 sec/vitesse 8.",  # Ceci ne doit PAS être un MODE
    "Mélanger 30 sec/vitesse turbo.",
    "Cuire 10 min/Varoma/Vitesse Cuillère.",  # Ne doit pas être un MODE (Cuillère est ignoré)
]

print("🧪 TEST - DÉTECTION MODES DEPUIS TTS COOKOMIX")
print("=" * 80)

for instruction in cookomix_instructions:
    print(f"\n✓ Instruction: '{instruction}'")
    
    # Essayer de détecter un mode
    mode_data = ModeAnnotation.extract_mode_from_tts(instruction)
    
    if mode_data:
        print(f"  ✅ MODE détecté: {mode_data}")
        annotation = ModeAnnotation.create_mode_annotation(instruction, mode_data)
        print(f"     Annotation: {json.dumps(annotation, indent=6)}")
    else:
        print(f"  ℹ️  Pas de mode (sera TTS standard)")
        # Vérifier aussi via StepWithTTS
        step = StepWithTTS.from_string(instruction)
        if step.annotations:
            print(f"     Annotation: {json.dumps(step.annotations[0], indent=6)}")

print("\n" + "=" * 80)
print("✅ TESTS TERMINÉS")
