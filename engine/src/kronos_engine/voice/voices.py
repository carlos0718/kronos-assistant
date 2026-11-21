"""Elección de la voz: cambia la que está en uso y permite probar las demás.

Las voces son de Piper (en la computadora) o de ElevenLabs (en la nube, con
ids que empiezan con `elevenlabs:`). `RoutedTts` habla con la que esté en uso,
sea del proveedor que sea.
"""

from collections.abc import Callable
from typing import Protocol

from kronos_engine.core.voices import CloudKey, UnknownVoiceError, VoiceInfo
from kronos_engine.voice.catalog import SAMPLES, VOICES
from kronos_engine.voice.elevenlabs import is_elevenlabs_voice
from kronos_engine.voice.speaker import Play, Speech


class SwitchableTts(Protocol):
    @property
    def voice(self) -> str: ...

    def set_voice(self, voice: str) -> None: ...

    async def synthesize(self, text: str) -> Speech: ...


class PreloadableTts(SwitchableTts, Protocol):
    def preload(self) -> None: ...


class RoutedTts:
    """Habla con la voz en uso; al pasar de Piper a ElevenLabs, o al revés, cambia de motor.

    `make` crea el motor de voz que corresponde a una voz.
    """

    def __init__(self, voice: str, make: Callable[[str], PreloadableTts]) -> None:
        self._make = make
        self._tts = make(voice)

    @property
    def voice(self) -> str:
        return self._tts.voice

    def set_voice(self, voice: str) -> None:
        if is_elevenlabs_voice(voice) == is_elevenlabs_voice(self._tts.voice):
            self._tts.set_voice(voice)
            return
        self._tts = self._make(voice)
        self._tts.preload()

    def preload(self) -> None:
        self._tts.preload()

    async def synthesize(self, text: str) -> Speech:
        return await self._tts.synthesize(text)


def _piper_voices() -> list[VoiceInfo]:
    return list(VOICES)


class SelectableVoices:
    """Implementa `VoiceControl` sobre las voces de `catalog`.

    `tts` es el que usa la conversación; `make_tts` crea uno aparte para
    probar una voz sin tocar la que está en uso. `remember` guarda la elección.
    `key` es la clave de ElevenLabs, y `local_voice` la voz de la computadora a
    la que se vuelve si se borra.
    """

    def __init__(
        self,
        tts: SwitchableTts,
        make_tts: Callable[[str], SwitchableTts],
        play: Play,
        remember: Callable[[str], None],
        catalog: Callable[[], list[VoiceInfo]] = _piper_voices,
        *,
        key: CloudKey,
        local_voice: str,
    ) -> None:
        self._tts = tts
        self._make_tts = make_tts
        self._play = play
        self._remember = remember
        self._catalog = catalog
        self._key = key
        self._local_voice = local_voice
        self._preview: SwitchableTts | None = None

    def available(self) -> list[VoiceInfo]:
        return self._catalog()

    def current(self) -> str:
        return self._tts.voice

    async def select(self, voice_id: str) -> None:
        self._find(voice_id)
        self._tts.set_voice(voice_id)
        self._remember(voice_id)

    async def preview(self, voice_id: str) -> None:
        info = self._find(voice_id)
        if voice_id == self._tts.voice:
            tts = self._tts
        else:
            # Se conserva la última voz probada, por si el usuario la vuelve a escuchar.
            if self._preview is None or self._preview.voice != voice_id:
                self._preview = self._make_tts(voice_id)
            tts = self._preview
        speech = await tts.synthesize(SAMPLES[info.language])
        await self._play(speech.samples, speech.sample_rate)

    def has_key(self) -> bool:
        return bool(self._key.get())

    async def set_key(self, key: str) -> None:
        self._key.set(key)
        # Sin clave, la voz de ElevenLabs en uso ya no podría hablar.
        if not key.strip() and is_elevenlabs_voice(self._tts.voice):
            await self.select(self._local_voice)

    def _find(self, voice_id: str) -> VoiceInfo:
        for info in self._catalog():
            if info.id == voice_id:
                return info
        raise UnknownVoiceError(f"No existe la voz {voice_id}.")
