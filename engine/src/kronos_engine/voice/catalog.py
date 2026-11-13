"""Voces de Piper que Kronos ofrece para elegir.

Son una selección de https://huggingface.co/rhasspy/piper-voices: dos de mujer
y dos de hombre por idioma. El género se asignó midiendo el tono de cada voz.
"""

from kronos_engine.core.voices import VoiceInfo

VOICES = [
    VoiceInfo("es_AR-daniela-high", "Daniela", "es", "Argentina", "female"),
    VoiceInfo("es_MX-claude-high", "Claude", "es", "México", "female"),
    VoiceInfo("es_ES-davefx-medium", "Dave", "es", "España", "male"),
    VoiceInfo("es_MX-ald-medium", "Ald", "es", "México", "male"),
    VoiceInfo("en_US-lessac-medium", "Lessac", "en", "Estados Unidos", "female"),
    VoiceInfo("en_US-amy-medium", "Amy", "en", "Estados Unidos", "female"),
    VoiceInfo("en_US-ryan-medium", "Ryan", "en", "Estados Unidos", "male"),
    VoiceInfo("en_US-hfc_male-medium", "HFC", "en", "Estados Unidos", "male"),
]

# Voz con la que se arranca si el usuario todavía no eligió.
DEFAULT_VOICES = {"es": "es_AR-daniela-high", "en": "en_US-lessac-medium"}

# Lo que dice cada voz al probarla.
SAMPLES = {
    "es": "Hola, soy Kronos. Así suena mi voz.",
    "en": "Hi, I'm Kronos. This is how my voice sounds.",
}
