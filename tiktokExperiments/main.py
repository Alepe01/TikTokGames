from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path

# Permite ejecutar este archivo directamente (python main.py) agregando la carpeta
# que contiene TikTokGames/ al sys.path, ya que los imports de abajo son absolutos.
_RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
if str(_RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PROYECTO))

from TikTokGames.tiktokExperiments.ComentariosyRegalos import ServicioTikTok
from TikTokGames.tiktokExperiments.GameManager import GameManager
from TikTokGames.tiktokExperiments.PanelControl import PanelControl
from TikTokGames.tiktokExperiments.ReproductorFondos import ReproductorFondos
from TikTokGames.tiktokExperiments.juegos import Ahorcado, CajaMusical, Memorama, PlaticaConP8, Trivia
from TikTokGames.tiktokExperiments.juegos import tema


def _activar_dpi_awareness() -> None:
    """Sin esto, Windows estira toda la ventana como si fuera un bitmap cuando hay
    escalado de pantalla activo (125%/150%, activado por defecto en la mayoría de
    laptops), y se ve borroso sin importar qué tan nítido dibuje pygame por dentro."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _resolucion_pantalla_show(root: tk.Tk) -> tuple[int, int]:
    """La ventana 9:16 más grande que cabe entera en la pantalla real del
    anfitrión: sin OBS de por medio, lo que se transmite es literalmente lo que
    la ventana muestra, así que no debe recortarse ni reescalarse borroso."""
    ancho_pantalla = root.winfo_screenwidth()
    alto_pantalla = root.winfo_screenheight()
    alto = alto_pantalla
    ancho = round(alto * 9 / 16)
    if ancho > ancho_pantalla:
        ancho = ancho_pantalla
        alto = round(ancho * 16 / 9)
    return ancho, alto


def main() -> None:
    _activar_dpi_awareness()
    root = tk.Tk()

    ancho, alto = _resolucion_pantalla_show(root)
    tema.ESCALA = alto / 960
    GameManager.ANCHO, GameManager.ALTO = ancho, alto
    ReproductorFondos.ANCHO, ReproductorFondos.ALTO = ancho, alto

    manager = GameManager(
        {
            "Trivia": Trivia(),
            "Ahorcado": Ahorcado(),
            "Caja Musical": CajaMusical(),
            "Memorama": Memorama(),
            "Platica con P8": PlaticaConP8(),
        }
    )
    # Pygame se queda en su propio hilo; Tkinter debe permanecer en el principal.
    hilo_show = threading.Thread(target=manager.ejecutar_pantalla, name="PantallaShow", daemon=True)
    hilo_show.start()

    # TikTok NO se inicia aquí: permite preparar y mostrar el juego sin live.
    panel = PanelControl(root, manager, conectar_tiktok=lambda: servicio.conectar())
    servicio = ServicioTikTok(manager, panel.mostrar_estado_tiktok)
    panel.ejecutar()
    manager.detener()
    hilo_show.join(timeout=2)


if __name__ == "__main__":
    main()
