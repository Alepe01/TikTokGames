from __future__ import annotations

from pathlib import Path

import cv2
import pygame


class ReproductorFondos:
    """Reproduce un único fondo a la vez, en el mismo hilo de Pygame."""

    ANCHO, ALTO = 1080, 1920

    def __init__(self, carpeta: Path) -> None:
        self.carpeta = carpeta
        self._captura: cv2.VideoCapture | None = None
        self._ruta: Path | None = None
        self._loop = True
        self._termino = False
        self._ultimo_frame: pygame.Surface | None = None
        self._audio: pygame.mixer.Sound | None = None

    def cargar(self, nombre_video: str, nombre_audio: str | None = None, *, loop: bool = True) -> None:
        self.detener()
        self._ruta = self.carpeta / nombre_video
        self._loop = loop
        self._termino = False
        if self._ruta.is_file():
            captura = cv2.VideoCapture(str(self._ruta))
            if captura.isOpened():
                self._captura = captura
            else:
                captura.release()
        if nombre_audio:
            try:
                self._audio = pygame.mixer.Sound(str(self.carpeta / nombre_audio))
                self._audio.play(loops=-1 if loop else 0)
            except (pygame.error, FileNotFoundError):
                self._audio = None

    def detener(self) -> None:
        if self._captura:
            self._captura.release()
        self._captura = None
        self._ultimo_frame = None
        self._termino = False
        if self._audio:
            self._audio.stop()
        self._audio = None

    @property
    def termino(self) -> bool:
        return self._termino

    def dibujar(self, superficie: pygame.Surface) -> None:
        if not self._captura:
            superficie.fill((0, 0, 0))
            return
        correcto, frame = self._captura.read()
        if not correcto:
            if self._loop:
                self._captura.set(cv2.CAP_PROP_POS_FRAMES, 0)
                correcto, frame = self._captura.read()
            else:
                self._termino = True
        if correcto:
            frame = cv2.resize(frame, (self.ANCHO, self.ALTO), interpolation=cv2.INTER_AREA)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._ultimo_frame = pygame.image.frombuffer(frame.tobytes(), (self.ANCHO, self.ALTO), "RGB").copy()
        if self._ultimo_frame:
            superficie.blit(self._ultimo_frame, (0, 0))
        else:
            superficie.fill((0, 0, 0))
