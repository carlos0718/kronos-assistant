"""Elección de la voz: cambia la que está en uso y permite probar las demás."""

from collections.abc import Callable
from typing import Protocol

from kronos_engine.core.voices import UnknownVoiceError, VoiceInfo
from kronos_engine.voice.catalog import SAMPLES, VOICES
from kronos_engine.voice.speaker import Play, Speech


class SwitchableTts(Protocol):
    @property
    def voice(self) -> str: ...

    def set_voice(self, voice: str) -> None: ...

    async def synthesize(self, text: str) -> Speech: ...


class PiperVoices:
    """Implementa `VoiceControl` sobre las voces del catálogo.

    `tts` es el que usa la conversación; `make_tts` crea uno aparte para
    probar una voz sin tocar la que está en uso. `remember` guarda la elección.
    """

    def __init__(
        self,
        tts: SwitchableTts,
        make_tts: Callable[[str], SwitchableTts],
        play: Play,
        remember: Callable[[str], None],
    ) -> None:
        self._tts = tts
        self._make_tts = make_tts
        self._play = play
        self._remember = remember
        self._preview: SwitchableTts | None = None

    def available(self) -> list[VoiceInfo]:
        return list(VOICES)

    def current(self) -> str:
        return self._tts.voice

    async def select(self, voice_id: str) -> None:
        _find(voice_id)
        self._tts.set_voice(voice_id)
        self._remember(voice_id)

    async def preview(self, voice_id: str) -> None:
        info = _find(voice_id)
        if voice_id == self._tts.voice:
            tts = self._tts
        else:
            # Se conserva la última voz probada, por si el usuario la vuelve a escuchar.
            if self._preview is None or self._preview.voice != voice_id:
                self._preview = self._make_tts(voice_id)
            tts = self._preview
        speech = await tts.synthesize(SAMPLES[info.language])
        await self._play(speech.samples, speech.sample_rate)


def _find(voice_id: str) -> VoiceInfo:
    for info in VOICES:
        if info.id == voice_id:
            return info
    raise UnknownVoiceError(f"No existe la voz {voice_id}.")
