from __future__ import annotations

from typing import Any

import pygame

from . import tema
from .base import JuegoBase
from .tema import FUENTE, ROJO_TURNO, VERDE, VERDE_SUAVE, VERDE_OSCURO, BLANCO_VERDOSO, circulo_suave, linea_suave


class Ahorcado(JuegoBase):
    """Ahorcado cooperativo con reloj individual por jugador y seis fallos."""

    nombre = "Ahorcado"
    MAX_FALLOS = 6

    def __init__(self) -> None:
        self.palabra = "QUISCALUS CIRCUS"
        self.letras: set[str] = set()
        self.fallidas: set[str] = set()
        self.fallos = 0
        self.ronda_activa = False
        self.finalizado = False
        self.numero_jugadores = 4
        self.tiempo_inicial = 60.0
        self.tiempos_restantes = [self.tiempo_inicial] * self.numero_jugadores
        self.jugador_actual = 0
        self._ultimo_tick_ms: int | None = None
        self._mensaje = "Configura la palabra y pulsa Iniciar ronda"
        self.ganadores_tiktok: list[str] = []
        self._usuarios_ganadores: set[str] = set()
        self.mostrar_ganadores_tiktok = False
        self.acepta_votos_tiktok = True
        self.modo_automatico = False
        self._fuentes: dict[int, pygame.font.Font] = {}

    def configurar_datos(self, datos: dict[str, Any]) -> None:
        # Conserva espacios interiores; sólo elimina espacios accidentales al inicio/final.
        propuesta = str(datos.get("pregunta", "")).strip().upper()
        self.palabra = propuesta or "QUISCALUS CIRCUS"
        self.numero_jugadores = self._entero_acotado(datos.get("numero_jugadores"), 4, 1, 4)
        self.tiempo_inicial = float(self._entero_acotado(datos.get("tiempo_por_jugador"), 60, 5, 3_600))
        self.modo_automatico = bool(datos.get("modo_automatico", False))
        self._reiniciar_partida()

    def iniciar_ronda(self) -> None:
        self._reiniciar_partida()
        self.ronda_activa = True
        self._ultimo_tick_ms = pygame.time.get_ticks()
        self._mensaje = "Turno de P1: escribe una letra"

    def procesar_voto(self, usuario: str, voto: str) -> None:
        # Los tres primeros que escriban la palabra completa ganan el incentivo.
        # casefold ignora mayúsculas/minúsculas y la normalización tolera espacios extra.
        if self.ronda_activa and self._normalizar(voto) == self._normalizar(self.palabra):
            clave_usuario = usuario.casefold().strip()
            if clave_usuario not in self._usuarios_ganadores and len(self.ganadores_tiktok) < 3:
                self._usuarios_ganadores.add(clave_usuario)
                self.ganadores_tiktok.append(usuario.strip() or "Espectador")
                # El podio se actualiza en vivo; no es necesario revelar la palabra.
                self.mostrar_ganadores_tiktok = True
                if len(self.ganadores_tiktok) == 3:
                    self.acepta_votos_tiktok = False
            # No se modifica la pantalla hasta que el anfitrión pulse M.
            return
        # En manual el anfitrión captura letras con su teclado; en automático
        # el chat también puede enviar una letra por comentario.
        if self.modo_automatico:
            self._intentar_letra(voto)

    def cerrar_ronda(self) -> None:
        self.ronda_activa = False
        self.finalizado = True

    def manejar_evento(self, evento: Any) -> None:
        if evento.type == pygame.KEYDOWN:
            if evento.key == pygame.K_m:
                self.mostrar_ganadores_tiktok = True
                self._mensaje = "Ganadores de TikTok revelados"
                return
            self._intentar_letra(evento.unicode)

    @staticmethod
    def _normalizar(texto: str) -> str:
        return " ".join(texto.strip().casefold().split())

    @staticmethod
    def _entero_acotado(valor: Any, predeterminado: int, minimo: int, maximo: int) -> int:
        try:
            return max(minimo, min(maximo, int(str(valor).strip())))
        except (TypeError, ValueError):
            return predeterminado

    def _reiniciar_partida(self) -> None:
        self.letras.clear()
        self.fallidas.clear()
        self.fallos = 0
        self.ronda_activa = False
        self.finalizado = False
        self.tiempos_restantes = [self.tiempo_inicial] * self.numero_jugadores
        self.jugador_actual = 0
        self._ultimo_tick_ms = None
        self.ganadores_tiktok.clear()
        self._usuarios_ganadores.clear()
        self.mostrar_ganadores_tiktok = False
        self.acepta_votos_tiktok = True

    def _intentar_letra(self, entrada: str) -> None:
        if not self.ronda_activa:
            return
        letra = entrada.strip().upper()
        if len(letra) != 1 or not letra.isalpha():
            return
        if letra in self.letras or letra in self.fallidas:
            self._mensaje = f"{letra} ya fue usada"
            return
        if letra in self.palabra:
            self.letras.add(letra)
            if self._palabra_completa():
                self.ronda_activa = False
                self.finalizado = True
                self._mensaje = "¡El equipo ganó!"
            else:
                self._mensaje = f"¡Correcto, P{self.jugador_actual + 1}! Sigue tu turno"
            return

        self.fallidas.add(letra)
        self.fallos += 1
        if self.fallos >= self.MAX_FALLOS:
            self.ronda_activa = False
            self.finalizado = True
            self._mensaje = f"Se acabaron las oportunidades: {self.palabra}"
        else:
            self._pasar_turno(f"{letra} no está en la palabra")

    def _palabra_completa(self) -> bool:
        return all(not caracter.isalpha() or caracter in self.letras for caracter in self.palabra)

    def _pasar_turno(self, motivo: str) -> None:
        disponibles = [i for i, tiempo in enumerate(self.tiempos_restantes) if tiempo > 0]
        if not disponibles:
            self.ronda_activa = False
            self.finalizado = True
            self._mensaje = "El equipo se quedó sin tiempo"
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
            self._pasar_turno(f"Tiempo de P{indice + 1} agotado")

    def _fuente(self, tamaño: int) -> pygame.font.Font:
        tamaño = int(round(tamaño))
        if tamaño not in self._fuentes:
            self._fuentes[tamaño] = pygame.font.SysFont(FUENTE, tamaño, bold=True)
        return self._fuentes[tamaño]

    def _texto_centrado(self, superficie: pygame.Surface, texto: str, y: int, tamaño: int, color: tuple[int, int, int]) -> None:
        imagen = self._fuente(tamaño).render(texto, True, color)
        superficie.blit(imagen, imagen.get_rect(center=(tema.esc(270), y)))

    def _dibujar_monito(self, superficie: pygame.Surface) -> None:
        color, grosor = VERDE, tema.esc(5)
        # Horca.
        linea_suave(superficie, color, (tema.esc(55), tema.esc(600)), (tema.esc(55), tema.esc(180)), grosor)
        linea_suave(superficie, color, (tema.esc(55), tema.esc(180)), (tema.esc(225), tema.esc(180)), grosor)
        linea_suave(superficie, color, (tema.esc(225), tema.esc(180)), (tema.esc(225), tema.esc(235)), grosor)
        linea_suave(superficie, color, (tema.esc(25), tema.esc(600)), (tema.esc(145), tema.esc(600)), grosor)
        # Monito por etapas: cabeza, cuerpo, brazos y piernas.
        if self.fallos >= 1:
            circulo_suave(superficie, color, (tema.esc(225), tema.esc(270)), tema.esc(34), ancho=grosor)
        if self.fallos >= 2:
            linea_suave(superficie, color, (tema.esc(225), tema.esc(304)), (tema.esc(225), tema.esc(415)), grosor)
        if self.fallos >= 3:
            linea_suave(superficie, color, (tema.esc(225), tema.esc(335)), (tema.esc(175), tema.esc(375)), grosor)
        if self.fallos >= 4:
            linea_suave(superficie, color, (tema.esc(225), tema.esc(335)), (tema.esc(275), tema.esc(375)), grosor)
        if self.fallos >= 5:
            linea_suave(superficie, color, (tema.esc(225), tema.esc(415)), (tema.esc(180), tema.esc(485)), grosor)
        if self.fallos >= 6:
            linea_suave(superficie, color, (tema.esc(225), tema.esc(415)), (tema.esc(270), tema.esc(485)), grosor)

    def _palabra_visible(self) -> str:
        # Los espacios originales se preservan y crean la separación entre palabras.
        return " ".join(caracter if (not caracter.isalpha() or caracter in self.letras) else "_" for caracter in self.palabra)

    def _dibujar_jugadores(self, superficie: pygame.Surface) -> None:
        for indice in range(self.numero_jugadores):
            x = tema.esc(80 + indice * 125)
            activo = self.ronda_activa and indice == self.jugador_actual
            color = ROJO_TURNO if activo else VERDE_SUAVE
            circulo = (x, tema.esc(745))
            circulo_suave(superficie, VERDE_OSCURO, circulo, tema.esc(29))
            circulo_suave(superficie, color, circulo, tema.esc(29), ancho=tema.esc(3))
            etiqueta = self._fuente(tema.esc(14)).render(f"P{indice + 1}", True, color)
            reloj = self._fuente(tema.esc(13)).render(f"{self.tiempos_restantes[indice]:.0f}s", True, BLANCO_VERDOSO)
            superficie.blit(etiqueta, etiqueta.get_rect(center=(x, tema.esc(737))))
            superficie.blit(reloj, reloj.get_rect(center=(x, tema.esc(754))))

    def _dibujar_ganadores_tiktok(self, superficie: pygame.Surface) -> None:
        if not self.mostrar_ganadores_tiktok:
            return
        titulo = self._fuente(tema.esc(17)).render("GANADORES TIKTOK", True, VERDE)
        superficie.blit(titulo, titulo.get_rect(center=(tema.esc(270), tema.esc(815))))
        if self.ganadores_tiktok:
            for indice, usuario in enumerate(self.ganadores_tiktok):
                texto = self._fuente(tema.esc(18)).render(f"{indice + 1}. {usuario[:24]}", True, BLANCO_VERDOSO)
                superficie.blit(texto, texto.get_rect(center=(tema.esc(270), tema.esc(845 + indice * 28))))
        else:
            texto = self._fuente(tema.esc(17)).render("Aún no hay ganadores", True, (210, 225, 245))
            superficie.blit(texto, texto.get_rect(center=(tema.esc(270), tema.esc(850))))

    def dibujar(self, superficie: pygame.Surface) -> None:
        self._actualizar_reloj()
        self._texto_centrado(superficie, "AHORCADO", tema.esc(70), tema.esc(32), VERDE)
        self._dibujar_monito(superficie)
        self._texto_centrado(superficie, self._palabra_visible(), tema.esc(555), tema.esc(27), BLANCO_VERDOSO)
        usadas = " ".join(sorted(self.fallidas)) or "—"
        self._texto_centrado(superficie, f"Fallos ({self.fallos}/{self.MAX_FALLOS}): {usadas}", tema.esc(630), tema.esc(19), VERDE_SUAVE)
        self._texto_centrado(superficie, self._mensaje, tema.esc(685), tema.esc(17), BLANCO_VERDOSO)
        modo = "AUTOMÁTICO: letras del chat" if self.modo_automatico else "MANUAL: letras del anfitrión"
        self._texto_centrado(superficie, modo, tema.esc(115), tema.esc(14), VERDE_SUAVE)
        self._dibujar_jugadores(superficie)
        self._dibujar_ganadores_tiktok(superficie)
