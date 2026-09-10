"""Adaptador TikTokLive: no toca nunca Tkinter, Pygame ni los juegos."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, ConnectEvent, GiftEvent

if TYPE_CHECKING:
    from TikTokGames.tiktokExperiments.GameManager import GameManager

UNIQUE_ID = "qu1scalus2"  # Cambia por tu usuario, sin @.


EstadoCallback = Callable[[str], None]


class ServicioTikTok:
    """Arranca una sola conexión bajo demanda desde el botón del panel."""

    def __init__(self, manager: GameManager, al_cambiar_estado: EstadoCallback) -> None:
        self.manager = manager
        self.al_cambiar_estado = al_cambiar_estado
        self._hilo: threading.Thread | None = None
        self._bloqueo = threading.Lock()

    def conectar(self, unique_id: str = UNIQUE_ID) -> bool:
        with self._bloqueo:
            if self._hilo and self._hilo.is_alive():
                return False
            self.al_cambiar_estado("Conectando a TikTok Live…")
            self._hilo = threading.Thread(
                target=self._conectar_en_hilo,
                args=(unique_id,),
                name="TikTokLive",
                daemon=True,
            )
            self._hilo.start()
            return True

    def _conectar_en_hilo(self, unique_id: str) -> None:
        try:
            iniciar_tiktok(self.manager, unique_id, self.al_cambiar_estado)
        except Exception as error:
            # También cubre errores al construir el cliente antes de client.run().
            self.al_cambiar_estado(f"No se pudo conectar a TikTok Live: {error}")


def iniciar_tiktok(manager: GameManager, unique_id: str = UNIQUE_ID, al_cambiar_estado: EstadoCallback | None = None) -> None:
    """Se ejecuta dentro del hilo TikTok; client.run() mantiene asyncio aislado."""
    client = TikTokLiveClient(unique_id=unique_id)

    @client.on(ConnectEvent)
    async def al_conectar(event: ConnectEvent) -> None:
        mensaje = f"Conectado correctamente a @{event.unique_id} (sala {client.room_id})"
        print(mensaje)
        if al_cambiar_estado:
            al_cambiar_estado(mensaje)

    @client.on(CommentEvent)
    async def al_comentario(event: CommentEvent) -> None:
        # EARLY RETURN: si no hay votación, no se imprime, normaliza ni encola nada.
        if not manager.votacion_activa:
            return
        # El juego muestra el nombre visible del espectador, no su identificador técnico.
        usuario = str(event.user.nickname or event.user.unique_id)
        manager.encolar_voto(usuario, event.comment)

    @client.on(GiftEvent)
    async def al_regalo(event: GiftEvent) -> None:
        # El listener queda activo desde que se conecta. Se descarta barato hasta
        # que un minijuego declare una mecánica basada en regalos.
        if not manager.votacion_activa:
            return
        return

    try:
        client.run()
    except Exception as error:
        # No afecta las ventanas; el anfitrión puede seguir operando offline.
        mensaje = f"No se pudo conectar a TikTok Live: {error}"
        print(mensaje)
        if al_cambiar_estado:
            al_cambiar_estado(mensaje)


if __name__ == "__main__":
    # Modo de prueba aislado: conecta, pero no procesa votos sin un GameManager.
    print("Ejecuta main.py para conectar TikTok al sistema de juegos.")
