from __future__ import annotations

import threading

import numpy as np

try:
    import sounddevice as sd
except ImportError:  # El sistema sigue funcionando aunque no exista sounddevice.
    sd = None


class DetectorDeVoz:
    """Lee únicamente nivel RMS del micrófono en un hilo de audio independiente."""

    def __init__(self, umbral: float = 0.025) -> None:
        self.umbral = umbral
        self.dispositivo: int | None = None
        self.hablando = threading.Event()
        self._stream: object | None = None

    def iniciar(self, dispositivo: int | None = None) -> bool:
        if sd is None or self._stream is not None:
            return self._stream is not None
        self.dispositivo = dispositivo
        try:
            self._stream = sd.InputStream(
                channels=1,
                samplerate=44_100,
                blocksize=1_024,
                device=dispositivo,
                callback=self._al_audio,
            )
            self._stream.start()  # type: ignore[union-attr]
            return True
        except Exception:
            self._stream = None
            self.hablando.clear()
            return False

    def detener(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()  # type: ignore[union-attr]
                self._stream.close()  # type: ignore[union-attr]
            except Exception:
                pass
        self._stream = None
        self.hablando.clear()

    def _al_audio(self, entrada: np.ndarray, _frames: int, _tiempo: object, _estado: object) -> None:
        rms = float(np.sqrt(np.mean(np.square(entrada))))
        if rms >= self.umbral:
            self.hablando.set()
        else:
            self.hablando.clear()
