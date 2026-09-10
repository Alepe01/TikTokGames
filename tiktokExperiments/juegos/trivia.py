from __future__ import annotations

from collections import Counter
from typing import Any

import pygame

from . import tema
from .base import JuegoBase
from .tema import FUENTE, NEGRO_PANEL, VERDE, VERDE_OSCURO, VERDE_SUAVE, BLANCO_VERDOSO


class Trivia(JuegoBase):
    """Trivia de dos opciones. Un usuario sólo puede tener un voto vigente."""

    nombre = "Trivia"

    def __init__(self) -> None:
        self.pregunta = "Escribe una pregunta y pulsa Cargar datos"
        self.opciones = {"A": "Opción A", "B": "Opción B"}
        self.respuesta_correcta = "A"
        self.votos_por_usuario: dict[str, str] = {}
        self.ronda_activa = False
        self.resultado_visible = False
        self._fuentes: dict[int, pygame.font.Font] = {}

    def configurar_datos(self, datos: dict[str, Any]) -> None:
        self.pregunta = str(datos.get("pregunta", self.pregunta)).strip() or self.pregunta
        self.opciones["A"] = str(datos.get("opcion_a", self.opciones["A"])).strip() or "Opción A"
        self.opciones["B"] = str(datos.get("opcion_b", self.opciones["B"])).strip() or "Opción B"
        respuesta = str(datos.get("respuesta_correcta", "A")).strip().upper()
        self.respuesta_correcta = respuesta if respuesta in self.opciones else "A"
        self.votos_por_usuario.clear()
        self.ronda_activa = False
        self.resultado_visible = False

    def iniciar_ronda(self) -> None:
        self.votos_por_usuario.clear()
        self.ronda_activa = True
        self.resultado_visible = False

    def procesar_voto(self, usuario: str, voto: str) -> None:
        if not self.ronda_activa:
            return
        voto_normalizado = voto.strip().upper()
        if voto_normalizado in self.opciones:
            self.votos_por_usuario[usuario] = voto_normalizado

    def cerrar_ronda(self) -> None:
        self.ronda_activa = False
        self.resultado_visible = True

    def _fuente(self, tamaño: int) -> pygame.font.Font:
        tamaño = int(round(tamaño))
        if tamaño not in self._fuentes:
            self._fuentes[tamaño] = pygame.font.SysFont(FUENTE, tamaño, bold=True)
        return self._fuentes[tamaño]

    def _texto_centrado(self, superficie: pygame.Surface, texto: str, y: int, tamaño: int, color: tuple[int, int, int]) -> None:
        # Divide textos largos de forma simple para no crear superficies cada frame innecesariamente.
        palabras, linea, lineas = texto.split(), "", []
        for palabra in palabras:
            candidata = f"{linea} {palabra}".strip()
            if self._fuente(tamaño).size(candidata)[0] > tema.ancho_seguro() and linea:
                lineas.append(linea)
                linea = palabra
            else:
                linea = candidata
        if linea:
            lineas.append(linea)
        for indice, contenido in enumerate(lineas):
            imagen = self._fuente(tamaño).render(contenido, True, color)
            rect = imagen.get_rect(center=(superficie.get_width() // 2, y + indice * (tamaño + tema.esc(8))))
            superficie.blit(imagen, rect)

    def dibujar(self, superficie: pygame.Surface) -> None:
        ancho = superficie.get_width()
        self._texto_centrado(superficie, "TRIVIA EN VIVO", tema.esc(70), tema.esc(32), VERDE)
        self._texto_centrado(superficie, self.pregunta, tema.esc(175), tema.esc(28), BLANCO_VERDOSO)

        for letra, y, color in (("A", tema.esc(410), VERDE_OSCURO), ("B", tema.esc(590), (16, 112, 70))):
            rect = pygame.Rect(tema.margen_lateral(), y, tema.ancho_seguro(), tema.esc(125))
            pygame.draw.rect(superficie, color, rect, border_radius=tema.esc(18))
            pygame.draw.rect(superficie, VERDE, rect, width=tema.esc(2), border_radius=tema.esc(18))
            self._texto_centrado(superficie, f"{letra}: {self.opciones[letra]}", y + tema.esc(39), tema.esc(25), BLANCO_VERDOSO)

        if self.ronda_activa:
            self._texto_centrado(superficie, "¡VOTA A o B EN EL CHAT!", tema.esc(820), tema.esc(25), VERDE)
        elif self.resultado_visible:
            conteo = Counter(self.votos_por_usuario.values())
            ganador = max(conteo, key=conteo.get) if conteo else "—"
            mensaje = f"RESPUESTA: {self.respuesta_correcta}   |   MÁS VOTADA: {ganador}"
            self._texto_centrado(superficie, mensaje, tema.esc(815), tema.esc(21), VERDE)
            self._texto_centrado(superficie, f"Votos: A {conteo['A']}  ·  B {conteo['B']}", tema.esc(865), tema.esc(21), BLANCO_VERDOSO)
        else:
            self._texto_centrado(superficie, "ESPERANDO AL ANFITRIÓN", tema.esc(835), tema.esc(22), VERDE_SUAVE)
