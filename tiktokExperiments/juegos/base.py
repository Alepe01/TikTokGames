from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JuegoBase(ABC):
    """Contrato común: el panel nunca depende de un minijuego concreto."""

    nombre = "Juego"
    acepta_votos_tiktok = True

    @abstractmethod
    def configurar_datos(self, datos: dict[str, Any]) -> None:
        """Carga los datos escritos por el anfitrión."""

    @abstractmethod
    def iniciar_ronda(self) -> None:
        """Abre el periodo en el que se aceptan votos."""

    @abstractmethod
    def procesar_voto(self, usuario: str, voto: str) -> None:
        """Recibe un voto ya validado por el gestor."""

    @abstractmethod
    def cerrar_ronda(self) -> None:
        """Cierra la votación y calcula/publica el resultado."""

    @abstractmethod
    def dibujar(self, superficie: Any) -> None:
        """Dibuja sólo el estado actual sobre la superficie Pygame."""

    def manejar_evento(self, evento: Any) -> None:
        """Entrada local opcional (por ejemplo, clics del mouse en un tablero)."""
