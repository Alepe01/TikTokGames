from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

import pygame

from TikTokGames.tiktokExperiments.juegos import tema
from TikTokGames.tiktokExperiments.juegos.base import JuegoBase
from TikTokGames.tiktokExperiments.ReproductorFondos import ReproductorFondos
from TikTokGames.tiktokExperiments.PresentadorVirtual import DetectorDeVoz


class GameManager:
    """Dueño del estado del juego y del único hilo que toca Pygame."""

    ANCHO, ALTO, FPS = 1080, 1920, 30
    ESCENARIOS = ("Fuera del circo", "Gradas", "Escenario")
    RECURSOS = Path(__file__).resolve().parent / "esenarios y utileria"

    def __init__(self, juegos: dict[str, JuegoBase], juego_inicial: str = "Trivia") -> None:
        if juego_inicial not in juegos:
            raise ValueError("El juego inicial debe existir en el catálogo.")
        self._juegos = juegos
        self._nombre_juego_activo = juego_inicial
        self._juego_activo = juegos[juego_inicial]
        self._votos: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=2_000)
        self._comandos: queue.Queue[tuple[str, dict[str, Any] | None]] = queue.Queue()
        self._cerrar = threading.Event()
        self._votacion_activa = threading.Event()
        self._escenario_activo: str | None = None
        self._mostrando_instrucciones = False
        self._fondos = ReproductorFondos(self.RECURSOS)
        self._presentador_activo = False
        self._detector_voz = DetectorDeVoz()
        self._presentador_cerrado: pygame.Surface | None = None
        self._presentador_abierto: pygame.Surface | None = None
        self._presentador_ahorcado_cerrado: pygame.Surface | None = None
        self._presentador_ahorcado_abierto: pygame.Surface | None = None
        self._microfono_seleccionado: int | None = None
        self._personaje_p8 = "p8"

    @property
    def nombres_juegos(self) -> tuple[str, ...]:
        return tuple(self._juegos)

    @property
    def opciones_escena(self) -> tuple[str, ...]:
        return self.nombres_juegos + self.ESCENARIOS

    @property
    def votacion_activa(self) -> bool:
        return self._votacion_activa.is_set()

    def encolar_voto(self, usuario: str, voto: str) -> bool:
        """Seguro desde el hilo TikTok. Nunca bloquea si llega demasiado chat."""
        if not self._votacion_activa.is_set():
            return False
        try:
            self._votos.put_nowait((usuario, voto))
            return True
        except queue.Full:
            return False

    # Los siguientes métodos los usa Tkinter: no modifica Pygame directamente.
    def cargar_datos(self, datos: dict[str, Any]) -> None:
        self._comandos.put(("configurar", datos))

    def iniciar_ronda(self) -> None:
        self._comandos.put(("iniciar", None))

    def cerrar_ronda(self) -> None:
        self._comandos.put(("cerrar", None))

    def siguiente_juego(self) -> None:
        self._comandos.put(("siguiente", None))

    def seleccionar_juego(self, nombre: str) -> None:
        """Cambia de escena en el hilo visual, nunca desde Tkinter."""
        if nombre in self._juegos:
            self._comandos.put(("seleccionar", {"nombre": nombre}))

    def seleccionar_contenido(self, nombre: str) -> None:
        if nombre in self._juegos or nombre in self.ESCENARIOS:
            self._comandos.put(("seleccionar_contenido", {"nombre": nombre}))

    def mostrar_instrucciones(self) -> None:
        if self._escenario_activo is None:
            self._comandos.put(("instrucciones", None))

    def mostrar_presentador(self, activo: bool) -> None:
        self._comandos.put(("presentador", {"activo": activo}))

    def seleccionar_microfono(self, indice: int | None) -> None:
        self._comandos.put(("microfono", {"indice": indice}))

    def enviar_pregunta_p8(self, usuario: str, texto: str) -> None:
        self._comandos.put(("p8_pregunta", {"usuario": usuario, "texto": texto}))

    def seleccionar_personaje_p8(self, nombre: str) -> None:
        self._comandos.put(("p8_personaje", {"nombre": nombre}))

    def comentarios_recientes_p8(self) -> list[tuple[str, str]]:
        """Lectura directa desde Tkinter: la Consola P8 la sondea cada 10 s."""
        juego = self._juegos.get("Platica con P8")
        metodo = getattr(juego, "comentarios_recientes", None)
        return metodo() if callable(metodo) else []

    def detener(self) -> None:
        self._cerrar.set()

    def _procesar_comandos(self) -> None:
        while True:
            try:
                comando, datos = self._comandos.get_nowait()
            except queue.Empty:
                return
            if comando == "configurar":
                self._votacion_activa.clear()
                self._juego_activo.configurar_datos(datos or {})
            elif comando == "iniciar":
                self._juego_activo.iniciar_ronda()
                if self._juego_activo.acepta_votos_tiktok:
                    self._votacion_activa.set()
                else:
                    self._votacion_activa.clear()
            elif comando == "cerrar":
                self._votacion_activa.clear()  # corta TikTok antes de calcular resultado
                self._juego_activo.cerrar_ronda()
            elif comando == "siguiente":
                self._votacion_activa.clear()
                self._juego_activo.configurar_datos({})
            elif comando == "seleccionar" and datos:
                nombre = str(datos["nombre"])
                self._votacion_activa.clear()
                # Cierra el juego que se deja atrás (p. ej. detiene música en loop de
                # Caja Musical); si no, sigue sonando aunque ya no esté en pantalla.
                self._juego_activo.cerrar_ronda()
                self._nombre_juego_activo = nombre
                self._juego_activo = self._juegos[nombre]
                self._juego_activo.configurar_datos({})
            elif comando == "seleccionar_contenido" and datos:
                nombre = str(datos["nombre"])
                self._votacion_activa.clear()
                self._mostrando_instrucciones = False
                # Cierra el juego/escenario que se deja atrás por la misma razón.
                self._juego_activo.cerrar_ronda()
                if nombre in self._juegos:
                    self._escenario_activo = None
                    self._nombre_juego_activo = nombre
                    self._juego_activo = self._juegos[nombre]
                    self._juego_activo.configurar_datos({})
                    if nombre == "Platica con P8":
                        self._cargar_fondo_personaje_p8(self._personaje_p8)
                    else:
                        self._cargar_fondo_juego(nombre)
                else:
                    self._escenario_activo = nombre
                    self._cargar_fondo_escenario(nombre)
            elif comando == "instrucciones":
                self._mostrando_instrucciones = True
                nombre = self._nombre_archivo(self._nombre_juego_activo)
                self._fondos.cargar(f"{nombre}_instrucciones.mp4", loop=False)
            elif comando == "presentador" and datos:
                self._presentador_activo = bool(datos["activo"])
                if self._presentador_activo:
                    self._cargar_presentador()
                    self._detector_voz.iniciar(self._microfono_seleccionado)
                else:
                    self._detector_voz.detener()
            elif comando == "microfono" and datos:
                indice = datos["indice"]
                self._microfono_seleccionado = indice if isinstance(indice, int) else None
                self._detector_voz.detener()
                if self._presentador_activo:
                    self._detector_voz.iniciar(self._microfono_seleccionado)
            elif comando == "p8_pregunta" and datos:
                juego = self._juegos.get("Platica con P8")
                metodo = getattr(juego, "encolar_pregunta", None)
                if callable(metodo):
                    metodo(str(datos["usuario"]), str(datos["texto"]))
            elif comando == "p8_personaje" and datos:
                self._personaje_p8 = str(datos["nombre"])
                juego = self._juegos.get("Platica con P8")
                metodo = getattr(juego, "cambiar_personaje", None)
                if callable(metodo):
                    metodo(self._personaje_p8)
                if self._escenario_activo is None and self._nombre_juego_activo == "Platica con P8":
                    self._cargar_fondo_personaje_p8(self._personaje_p8)

    def _cargar_presentador(self) -> None:
        """Carga sólo al activar: imágenes PNG transparentes, 380 px de alto (de diseño)."""
        alto_objetivo = tema.esc(380)

        def cargar(nombre: str) -> pygame.Surface | None:
            try:
                imagen = pygame.image.load(str(self.RECURSOS / nombre)).convert_alpha()
                ancho = max(1, int(imagen.get_width() * alto_objetivo / imagen.get_height()))
                return pygame.transform.smoothscale(imagen, (ancho, alto_objetivo))
            except (pygame.error, FileNotFoundError):
                return None

        self._presentador_cerrado = cargar("presentador_boca_cerrada.png")
        self._presentador_abierto = cargar("presentador_boca_abierta.png")
        # Ahorcado tiene el monito a la izquierda: limita el ancho para caber
        # desde x=280 hasta el borde derecho sin invadirlo ni salir de pantalla.
        ancho_maximo_ahorcado = tema.esc(250)
        self._presentador_ahorcado_cerrado = self._ajustar_ancho(self._presentador_cerrado, ancho_maximo_ahorcado)
        self._presentador_ahorcado_abierto = self._ajustar_ancho(self._presentador_abierto, ancho_maximo_ahorcado)

    @staticmethod
    def _ajustar_ancho(imagen: pygame.Surface | None, ancho_maximo: int) -> pygame.Surface | None:
        if imagen is None or imagen.get_width() <= ancho_maximo:
            return imagen
        alto = max(1, int(imagen.get_height() * ancho_maximo / imagen.get_width()))
        return pygame.transform.smoothscale(imagen, (ancho_maximo, alto))

    def _dibujar_presentador(self, superficie: pygame.Surface) -> None:
        if not self._presentador_activo:
            return
        if self._nombre_juego_activo == "Ahorcado":
            imagen = self._presentador_ahorcado_abierto if self._detector_voz.hablando.is_set() else self._presentador_ahorcado_cerrado
        else:
            imagen = self._presentador_abierto if self._detector_voz.hablando.is_set() else self._presentador_cerrado
        if imagen:
            posiciones = {
                # A la derecha del monito (x=55–275), terminando antes de las letras (y=555).
                "Ahorcado": (tema.esc(280), tema.esc(150)),
                # Bajo el tablero: las parejas que desaparecen revelan al personaje.
                "Memorama": (tema.esc(110), tema.esc(205)),
            }
            # Posición general elevada: deja la franja inferior para comentarios TikTok.
            posicion = posiciones.get(self._nombre_juego_activo, (tema.esc(20), tema.esc(300)))
            superficie.blit(imagen, posicion)

    @staticmethod
    def _nombre_archivo(nombre: str) -> str:
        return nombre.lower().replace(" ", "_")

    def _cargar_fondo_juego(self, nombre: str) -> None:
        base = self._nombre_archivo(nombre)
        self._fondos.cargar(f"{base}_fondo.mp4", f"{base}_musica.mp3")

    def _cargar_fondo_escenario(self, nombre: str) -> None:
        base = self._nombre_archivo(nombre)
        self._fondos.cargar(f"{base}_fondo.mp4", f"{base}_musica.mp3")

    def _cargar_fondo_personaje_p8(self, personaje: str) -> None:
        # El video de Platica con P8 depende del personaje elegido, no del nombre del juego.
        self._fondos.cargar(f"{personaje}_fondo.mp4", f"{personaje}_musica.mp3")

    def _procesar_votos(self, limite: int = 250) -> None:
        # Límite por frame: conserva 30 FPS aun con picos de mensajes.
        if not self._juego_activo.acepta_votos_tiktok:
            self._votacion_activa.clear()
            self._vaciar_votos()
            return
        for _ in range(limite):
            try:
                usuario, voto = self._votos.get_nowait()
            except queue.Empty:
                return
            self._juego_activo.procesar_voto(usuario, voto)
            if not self._juego_activo.acepta_votos_tiktok:
                # El juego ya recibió sus tres lugares: deja viva la conexión,
                # pero corta de inmediato la cola y el early return de TikTok.
                self._votacion_activa.clear()
                self._vaciar_votos()
                return

    def _vaciar_votos(self) -> None:
        while True:
            try:
                self._votos.get_nowait()
            except queue.Empty:
                return

    def ejecutar_pantalla(self) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass
        self._cargar_fondo_juego(self._nombre_juego_activo)
        # main.py ya calculó (ANCHO, ALTO) como la ventana 9:16 más grande que cabe
        # entera en la pantalla real del anfitrión (sin OBS, lo que se transmite es
        # literalmente lo que esta ventana muestra). NOFRAME evita gastar píxeles
        # verticales en la barra de título.
        pantalla = pygame.display.set_mode((self.ANCHO, self.ALTO), pygame.NOFRAME)
        pygame.display.set_caption("Pantalla del Show")
        reloj = pygame.time.Clock()
        try:
            while not self._cerrar.is_set():
                for evento in pygame.event.get():
                    if evento.type == pygame.QUIT:
                        self._cerrar.set()
                    else:
                        self._juego_activo.manejar_evento(evento)
                self._procesar_comandos()
                self._procesar_votos()
                self._fondos.dibujar(pantalla)
                if self._mostrando_instrucciones:
                    if self._fondos.termino:
                        self._mostrando_instrucciones = False
                        self._cargar_fondo_juego(self._nombre_juego_activo)
                elif self._escenario_activo is None and self._nombre_juego_activo == "Memorama":
                    # En Memorama el personaje es parte del fondo: queda oculto
                    # por las cartas, y las parejas acertadas lo dejan visible.
                    self._dibujar_presentador(pantalla)
                    self._juego_activo.dibujar(pantalla)
                elif self._escenario_activo is None:
                    self._juego_activo.dibujar(pantalla)
                if self._escenario_activo is not None or self._nombre_juego_activo != "Memorama":
                    self._dibujar_presentador(pantalla)
                pygame.display.flip()
                reloj.tick(self.FPS)
        finally:
            self._fondos.detener()
            self._detector_voz.detener()
            pygame.quit()
