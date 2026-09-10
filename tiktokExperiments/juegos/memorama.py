from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pygame

from . import tema
from .base import JuegoBase
from .tema import FUENTE, ROJO_TURNO, VERDE, VERDE_SUAVE, VERDE_OSCURO, BLANCO_VERDOSO, circulo_suave


class Memorama(JuegoBase):
    """Tablero local 5×6: se juega exclusivamente con clics en la ventana del show."""

    nombre = "Memorama"
    acepta_votos_tiktok = False
    COLUMNAS, FILAS = 5, 6
    COLUMNAS_VOCALES = "AEIOU"
    CARPETA_IMAGENES = Path(__file__).resolve().parents[1] / "Imagenes-memorama"
    EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

    def __init__(self) -> None:
        # Instancia, no clase: deben leer tema.ESCALA en el momento en que se
        # construye el juego (después de que main.py ya la ajustó a la pantalla
        # real), no en el momento en que se importa este módulo.
        # Zona segura para superposiciones de TikTok Live: arriba quedan los
        # controles, a la derecha los botones y abajo el chat.
        self.TAMANO_CARTA = (tema.esc(55), tema.esc(72))
        self.TABLERO_X, self.TABLERO_Y = tema.esc(95), tema.esc(160)
        self.SEPARACION = tema.esc(5)
        self.titulo = "MEMORAMA"
        self.cartas: list[pygame.Surface | None] = [None] * (self.COLUMNAS * self.FILAS)
        self._ids_pares: list[int | None] = [None] * (self.COLUMNAS * self.FILAS)
        self.reveladas: set[int] = set()
        self.encontradas: set[int] = set()
        self.seleccionadas: list[int] = []
        self._ocultar_en_ms: int | None = None
        self.numero_jugadores = 4
        self.tiempo_inicial = 60.0
        self.tiempos_restantes = [self.tiempo_inicial] * self.numero_jugadores
        self.pares_por_jugador = [0] * self.numero_jugadores
        self.jugador_actual = 0
        self.ronda_activa = False
        self._ultimo_tick_ms: int | None = None
        self._rectangulos: list[pygame.Rect] = []
        self._fuentes: dict[int, pygame.font.Font] = {}
        self._mensaje = "Añade imágenes a Imagenes-memorama y pulsa Cargar datos"

    def configurar_datos(self, datos: dict[str, Any]) -> None:
        self.titulo = str(datos.get("pregunta", "")).strip() or "MEMORAMA"
        self.numero_jugadores = self._entero_acotado(datos.get("numero_jugadores"), 4, 1, 4)
        self.tiempo_inicial = float(self._entero_acotado(datos.get("tiempo_por_jugador"), 60, 5, 3_600))
        self._reiniciar_jugadores()
        self._crear_tablero()

    def iniciar_ronda(self) -> None:
        # No abre TikTok: sólo reinicia el tablero local para una nueva partida.
        self._reiniciar_jugadores()
        self._crear_tablero()
        self.ronda_activa = True
        self._ultimo_tick_ms = pygame.time.get_ticks()

    def procesar_voto(self, usuario: str, voto: str) -> None:
        # Este juego no recibe votos ni comentarios de TikTok.
        return

    def cerrar_ronda(self) -> None:
        self.ronda_activa = False

    @staticmethod
    def _entero_acotado(valor: Any, predeterminado: int, minimo: int, maximo: int) -> int:
        try:
            return max(minimo, min(maximo, int(str(valor).strip())))
        except (TypeError, ValueError):
            return predeterminado

    def _reiniciar_jugadores(self) -> None:
        self.tiempos_restantes = [self.tiempo_inicial] * self.numero_jugadores
        self.pares_por_jugador = [0] * self.numero_jugadores
        self.jugador_actual = 0
        self.ronda_activa = False
        self._ultimo_tick_ms = None

    def _fuente(self, tamaño: int) -> pygame.font.Font:
        tamaño = int(round(tamaño))
        if tamaño not in self._fuentes:
            self._fuentes[tamaño] = pygame.font.SysFont(FUENTE, tamaño, bold=True)
        return self._fuentes[tamaño]

    def _crear_tablero(self) -> None:
        """Elige 15 imágenes y las duplica para obtener los 15 pares del tablero."""
        archivos = [ruta for ruta in self.CARPETA_IMAGENES.iterdir() if ruta.suffix.lower() in self.EXTENSIONES]
        if not archivos:
            self.cartas = [None] * (self.COLUMNAS * self.FILAS)
            self._ids_pares = [None] * (self.COLUMNAS * self.FILAS)
            self.reveladas.clear()
            self.encontradas.clear()
            self.seleccionadas.clear()
            self._ocultar_en_ms = None
            self._mensaje = "No hay imágenes: súbelas a Imagenes-memorama"
            return

        # Si aún hay menos de 15 archivos, algunos se reutilizan como pares.
        pares = random.sample(archivos, k=min(15, len(archivos)))
        while len(pares) < 15:
            pares.append(random.choice(archivos))
        # Cada entrada conserva su ID de pareja, incluso si se reutiliza una imagen.
        entradas = [(id_par, ruta) for id_par, ruta in enumerate(pares) for _ in range(2)]
        random.shuffle(entradas)
        # El escalado se hace una sola vez al cargar, no dentro del bucle de 30 FPS.
        cache: dict[Path, pygame.Surface | None] = {}
        self.cartas = []
        for _, ruta in entradas:
            if ruta not in cache:
                original = self._cargar_imagen(ruta)
                cache[ruta] = pygame.transform.smoothscale(original, self.TAMANO_CARTA) if original else None
            self.cartas.append(cache[ruta])
        self._ids_pares = [id_par for id_par, _ in entradas]
        self.reveladas.clear()
        self.encontradas.clear()
        self.seleccionadas.clear()
        self._ocultar_en_ms = None
        self._mensaje = "Haz clic en una carta para revelarla"

    @staticmethod
    def _cargar_imagen(ruta: Path) -> pygame.Surface | None:
        try:
            return pygame.image.load(str(ruta)).convert_alpha()
        except pygame.error:
            return None

    def manejar_evento(self, evento: Any) -> None:
        if evento.type != pygame.MOUSEBUTTONDOWN or evento.button != 1:
            return
        if not self.ronda_activa:
            self._mensaje = "Configura y pulsa Iniciar ronda"
            return
        # Mientras las dos cartas incorrectas están visibles, se ignoran clics.
        if self._ocultar_en_ms is not None:
            return
        for indice, rectangulo in enumerate(self._rectangulos):
            if rectangulo.collidepoint(evento.pos) and indice not in self.encontradas and indice not in self.seleccionadas:
                if self._ids_pares[indice] is None:
                    self._mensaje = "Añade imágenes válidas para jugar"
                    return
                self.seleccionadas.append(indice)
                if len(self.seleccionadas) == 1:
                    self._mensaje = f"Carta {self._coordenada(indice)} revelada: elige otra"
                else:
                    primera, segunda = self.seleccionadas
                    if self._ids_pares[primera] == self._ids_pares[segunda]:
                        # La pareja desaparece y deja ver el fondo/presentador.
                        self.encontradas.update(self.seleccionadas)
                        self.seleccionadas.clear()
                        self.pares_por_jugador[self.jugador_actual] += 1
                        self._mensaje = f"¡Pareja de P{self.jugador_actual + 1}! Juega otra vez"
                    else:
                        self._ocultar_en_ms = pygame.time.get_ticks() + 1_000
                        self._mensaje = "No son pareja… se ocultarán en un segundo"
                return

    def _actualizar_intento(self) -> None:
        """Se llama desde dibujar, por lo que nunca bloquea el bucle visual."""
        if self._ocultar_en_ms is not None and pygame.time.get_ticks() >= self._ocultar_en_ms:
            self.seleccionadas.clear()
            self._ocultar_en_ms = None
            self._pasar_turno("No fue pareja")

    def _pasar_turno(self, motivo: str) -> None:
        disponibles = [i for i, tiempo in enumerate(self.tiempos_restantes) if tiempo > 0]
        if not disponibles:
            self.ronda_activa = False
            self._mensaje = "Tiempo terminado"
            return
        for desplazamiento in range(1, self.numero_jugadores + 1):
            candidato = (self.jugador_actual + desplazamiento) % self.numero_jugadores
            if self.tiempos_restantes[candidato] > 0:
                self.jugador_actual = candidato
                self._mensaje = f"{motivo}. Turno de P{candidato + 1}"
                return

    def _actualizar_reloj(self) -> None:
        if not self.ronda_activa:
            return
        ahora = pygame.time.get_ticks()
        if self._ultimo_tick_ms is None:
            self._ultimo_tick_ms = ahora
            return
        transcurrido = (ahora - self._ultimo_tick_ms) / 1_000
        self._ultimo_tick_ms = ahora
        indice = self.jugador_actual
        self.tiempos_restantes[indice] = max(0.0, self.tiempos_restantes[indice] - transcurrido)
        if self.tiempos_restantes[indice] == 0.0:
            self.seleccionadas.clear()
            self._ocultar_en_ms = None
            self._pasar_turno(f"Se acabó el tiempo de P{indice + 1}")

    def _coordenada(self, indice: int) -> str:
        fila, columna = divmod(indice, self.COLUMNAS)
        # Columnas A-E-I-O-U, filas 1–6: A1 hasta U6.
        return f"{self.COLUMNAS_VOCALES[columna]}{fila + 1}"

    def dibujar(self, superficie: pygame.Surface) -> None:
        self._actualizar_reloj()
        self._actualizar_intento()
        encabezado = self._fuente(tema.esc(24)).render(self.titulo, True, VERDE)
        # El encabezado acompaña al tablero, sin invadir la zona superior de TikTok.
        superficie.blit(encabezado, encabezado.get_rect(center=(tema.esc(242), tema.esc(120))))

        margen_x, y_inicial, separacion = self.TABLERO_X, self.TABLERO_Y, self.SEPARACION
        ancho, alto = self.TAMANO_CARTA
        self._rectangulos = []
        for indice, carta in enumerate(self.cartas):
            fila, columna = divmod(indice, self.COLUMNAS)
            rectangulo = pygame.Rect(margen_x + columna * (ancho + separacion), y_inicial + fila * (alto + separacion), ancho, alto)
            self._rectangulos.append(rectangulo)
            if indice in self.encontradas:
                continue
            revelada = indice in self.seleccionadas
            pygame.draw.rect(superficie, (245, 255, 248) if revelada else VERDE_OSCURO, rectangulo, border_radius=tema.esc(10))
            pygame.draw.rect(superficie, VERDE, rectangulo, width=tema.esc(2), border_radius=tema.esc(10))
            if revelada and carta is not None:
                superficie.blit(carta, rectangulo)
            else:
                etiqueta = self._fuente(tema.esc(24)).render(self._coordenada(indice), True, BLANCO_VERDOSO)
                superficie.blit(etiqueta, etiqueta.get_rect(center=rectangulo.center))

        self._dibujar_participantes(superficie)
        self._dibujar_relojes(superficie)
        texto = self._fuente(tema.esc(15)).render(self._mensaje, True, BLANCO_VERDOSO)
        superficie.blit(texto, texto.get_rect(center=(tema.esc(242), tema.esc(750))))

    def _dibujar_participantes(self, superficie: pygame.Surface) -> None:
        # Círculos junto a A1, A6, E1 y E6, respectivamente.
        posiciones = ((tema.esc(60), tema.esc(196)), (tema.esc(60), tema.esc(581)), (tema.esc(425), tema.esc(196)), (tema.esc(425), tema.esc(581)))
        for indice in range(self.numero_jugadores):
            centro = posiciones[indice]
            activo = indice == self.jugador_actual and self.ronda_activa
            color = ROJO_TURNO if activo else VERDE_SUAVE
            circulo_suave(superficie, VERDE_OSCURO, centro, tema.esc(29))
            circulo_suave(superficie, color, centro, tema.esc(29), ancho=tema.esc(3))
            nombre = self._fuente(tema.esc(14)).render(f"P{indice + 1}", True, color)
            pares = self._fuente(tema.esc(16)).render(str(self.pares_por_jugador[indice]), True, BLANCO_VERDOSO)
            superficie.blit(nombre, nombre.get_rect(center=(centro[0], centro[1] - tema.esc(8))))
            superficie.blit(pares, pares.get_rect(center=(centro[0], centro[1] + tema.esc(9))))

    def _dibujar_relojes(self, superficie: pygame.Surface) -> None:
        for indice in range(self.numero_jugadores):
            x = tema.esc(75 + indice * 100)
            activo = indice == self.jugador_actual and self.ronda_activa
            color = VERDE if activo else BLANCO_VERDOSO
            etiqueta = self._fuente(tema.esc(15)).render(f"P{indice + 1}  {self.tiempos_restantes[indice]:04.1f}s", True, color)
            superficie.blit(etiqueta, etiqueta.get_rect(center=(x, tema.esc(700))))
