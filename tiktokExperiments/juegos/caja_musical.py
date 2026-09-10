from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame

from . import tema
from .base import JuegoBase
from .tema import FUENTE, VERDE, VERDE_SUAVE, VERDE_OSCURO, BLANCO_VERDOSO


class CajaMusical(JuegoBase):
    """Reto local de preguntas Sí/No con cuenta regresiva y penalización por silencio."""

    nombre = "Caja Musical"
    CARPETA_MATERIALES = Path(__file__).resolve().parents[1] / "Materiales-caja-musical"
    CARPETA_ESCENARIOS = Path(__file__).resolve().parents[1] / "esenarios y utileria"
    UMBRAL_MUSICA_SEGUNDOS = 180  # A los tres minutos comienza la caja musical.
    VOLUMEN_CAJA = 0.15  # Bajito: acompaña sin taparle la voz al anfitrión.

    def __init__(self) -> None:
        self.palabra = "SECRETO"
        self.tiempo_inicial = 600.0
        self.limite_sin_respuesta = 30.0
        self.tiempo_reducido = 180.0
        self.tiempo_restante = self.tiempo_inicial
        self.ronda_activa = False
        self.terminado = False
        self.revelar_palabra = False
        self._ultimo_tick_ms: int | None = None
        self._ultima_respuesta_ms: int | None = None
        self._penalizacion_aplicada = False
        self._musica_iniciada = False
        self._mensaje = "Configura la palabra y pulsa Iniciar ronda"
        self._respuesta = ""
        self._fuentes: dict[int, pygame.font.Font] = {}
        self._imagen_caja_cerrada: pygame.Surface | None = None
        self._imagen_caja_abierta: pygame.Surface | None = None
        self._imagen_screamer: pygame.Surface | None = None
        self._audio_caja: pygame.mixer.Sound | None = None
        self._audio_screamer: pygame.mixer.Sound | None = None
        self.ganadores_tiktok: list[str] = []
        self._usuarios_ganadores: set[str] = set()
        self.mostrar_ganadores_tiktok = False
        self.acepta_votos_tiktok = True

    def configurar_datos(self, datos: dict[str, Any]) -> None:
        self.palabra = str(datos.get("pregunta", "")).strip().upper() or "SECRETO"
        self.tiempo_inicial = float(self._numero(datos.get("tiempo_inicial_minutos"), 10, 1, 120)) * 60
        self.limite_sin_respuesta = float(self._numero(datos.get("tiempo_sin_respuesta_segundos"), 30, 1, 3_600))
        self.tiempo_reducido = float(self._numero(datos.get("tiempo_reducido_minutos"), 3, 1, 60)) * 60
        self._cargar_materiales()
        self._reiniciar()

    def iniciar_ronda(self) -> None:
        self._reiniciar()
        self.ronda_activa = True
        ahora = pygame.time.get_ticks()
        self._ultimo_tick_ms = ahora
        self._ultima_respuesta_ms = ahora
        self._mensaje = "Haz preguntas. El anfitrión responde S o N"

    def procesar_voto(self, usuario: str, voto: str) -> None:
        # Sólo la frase secreta completa cuenta; S/N siguen siendo controles locales.
        if not self.ronda_activa or self._normalizar(voto) != self._normalizar(self.palabra):
            return
        clave_usuario = usuario.casefold().strip()
        if clave_usuario not in self._usuarios_ganadores and len(self.ganadores_tiktok) < 3:
            self._usuarios_ganadores.add(clave_usuario)
            self.ganadores_tiktok.append(usuario.strip() or "Espectador")
            # Los lugares aparecen conforme se consiguen; M sólo revela la palabra.
            self.mostrar_ganadores_tiktok = True
            if len(self.ganadores_tiktok) == 3:
                self.acepta_votos_tiktok = False

    def cerrar_ronda(self) -> None:
        self.ronda_activa = False
        self._detener_musica()

    def manejar_evento(self, evento: Any) -> None:
        if getattr(evento, "type", None) != pygame.KEYDOWN:
            return
        tecla = evento.unicode.lower()
        if tecla == "s":
            self._responder("Si")
        elif tecla == "n":
            self._responder("No")
        elif tecla == "m" and self.ronda_activa:
            self.revelar_palabra = True
            self.mostrar_ganadores_tiktok = True
            self._mensaje = "Palabra revelada"

    @staticmethod
    def _normalizar(texto: str) -> str:
        return " ".join(texto.strip().casefold().split())

    @staticmethod
    def _numero(valor: Any, predeterminado: int, minimo: int, maximo: int) -> int:
        try:
            return max(minimo, min(maximo, int(str(valor).strip())))
        except (TypeError, ValueError):
            return predeterminado

    def _reiniciar(self) -> None:
        self.tiempo_restante = self.tiempo_inicial
        self.ronda_activa = False
        self.terminado = False
        self.revelar_palabra = False
        self._ultimo_tick_ms = self._ultima_respuesta_ms = None
        self._penalizacion_aplicada = self._musica_iniciada = False
        self._respuesta = ""
        self.ganadores_tiktok.clear()
        self._usuarios_ganadores.clear()
        self.mostrar_ganadores_tiktok = False
        self.acepta_votos_tiktok = True
        self._detener_musica()

    def _responder(self, respuesta: str) -> None:
        if not self.ronda_activa:
            return
        self._respuesta = respuesta
        self._mensaje = f"Respuesta: {respuesta}"
        self._ultima_respuesta_ms = pygame.time.get_ticks()

    def _cargar_materiales(self) -> None:
        # Si ya había un audio en loop, se detiene antes de perder su referencia:
        # de lo contrario sigue sonando para siempre, sin forma de pararlo después.
        if self._audio_caja:
            self._audio_caja.stop()
        tamaño_caja = (tema.esc(260), tema.esc(260))
        self._imagen_caja_cerrada = self._cargar_imagen("caja_cerrada.png", tamaño_caja, self.CARPETA_ESCENARIOS)
        self._imagen_caja_abierta = self._cargar_imagen("caja_abierta.png", tamaño_caja, self.CARPETA_ESCENARIOS)
        self._imagen_screamer = self._cargar_imagen("screamer.png", (tema.esc(540), tema.esc(960)))
        self._audio_caja = self._cargar_audio("caja_musical.wav")
        if self._audio_caja:
            self._audio_caja.set_volume(self.VOLUMEN_CAJA)
        self._audio_screamer = self._cargar_audio("screamer.mp3")

    def _cargar_imagen(self, nombre: str, tamaño: tuple[int, int], carpeta: Path | None = None) -> pygame.Surface | None:
        try:
            imagen = pygame.image.load(str((carpeta or self.CARPETA_MATERIALES) / nombre)).convert_alpha()
            return pygame.transform.smoothscale(imagen, tamaño)
        except (pygame.error, FileNotFoundError):
            return None

    def _cargar_audio(self, nombre: str) -> pygame.mixer.Sound | None:
        try:
            return pygame.mixer.Sound(str(self.CARPETA_MATERIALES / nombre))
        except (pygame.error, FileNotFoundError):
            return None

    def _detener_musica(self) -> None:
        if self._audio_caja:
            self._audio_caja.stop()

    def _actualizar(self) -> None:
        if not self.ronda_activa:
            return
        ahora = pygame.time.get_ticks()
        if self._ultimo_tick_ms is None:
            self._ultimo_tick_ms = ahora
            return
        self.tiempo_restante = max(0.0, self.tiempo_restante - (ahora - self._ultimo_tick_ms) / 1_000)
        self._ultimo_tick_ms = ahora
        if not self._penalizacion_aplicada and self._ultima_respuesta_ms is not None:
            if ahora - self._ultima_respuesta_ms >= self.limite_sin_respuesta * 1_000:
                self._penalizacion_aplicada = True
                if self.tiempo_restante > self.tiempo_reducido:
                    self.tiempo_restante = self.tiempo_reducido
                    self._mensaje = "Sin respuesta: el tiempo se redujo"
        if self.tiempo_restante <= self.UMBRAL_MUSICA_SEGUNDOS and not self._musica_iniciada:
            self._musica_iniciada = True
            if self._audio_caja:
                self._audio_caja.play(loops=-1)
        if self.tiempo_restante <= 0:
            self.ronda_activa = False
            self.terminado = True
            self._detener_musica()
            if self._audio_screamer:
                self._audio_screamer.play()

    def _fuente(self, tamaño: int) -> pygame.font.Font:
        tamaño = int(round(tamaño))
        if tamaño not in self._fuentes:
            self._fuentes[tamaño] = pygame.font.SysFont(FUENTE, tamaño, bold=True)
        return self._fuentes[tamaño]

    def _formato_tiempo(self) -> str:
        total = max(0, int(self.tiempo_restante + 0.999))
        return f"{total // 60:02}:{total % 60:02}"

    def dibujar(self, superficie: pygame.Surface) -> None:
        self._actualizar()
        if self.terminado:
            if self._imagen_screamer:
                superficie.blit(self._imagen_screamer, (0, 0))
            else:
                superficie.fill((0, 0, 0))
                texto = self._fuente(tema.esc(42)).render("TIEMPO TERMINADO", True, VERDE)
                superficie.blit(texto, texto.get_rect(center=(tema.esc(270), tema.esc(480))))
            return

        titulo = self._fuente(tema.esc(30)).render("CAJA MISTERIOSA", True, VERDE)
        superficie.blit(titulo, titulo.get_rect(center=(tema.esc(270), tema.esc(105))))
        reloj = self._fuente(tema.esc(64)).render(self._formato_tiempo(), True, BLANCO_VERDOSO)
        superficie.blit(reloj, reloj.get_rect(center=(tema.esc(270), tema.esc(205))))
        # Cerrada mientras el misterio sigue en pie; se abre justo cuando se revela la palabra.
        imagen_caja = self._imagen_caja_abierta if self.revelar_palabra else self._imagen_caja_cerrada
        if imagen_caja:
            superficie.blit(imagen_caja, imagen_caja.get_rect(center=(tema.esc(270), tema.esc(450))))
        else:
            caja = pygame.Rect(tema.esc(155), tema.esc(320), tema.esc(230), tema.esc(230))
            pygame.draw.rect(superficie, VERDE_OSCURO, caja, border_radius=tema.esc(18))
            pygame.draw.rect(superficie, VERDE, caja, width=tema.esc(4), border_radius=tema.esc(18))
            texto = self._fuente(tema.esc(24)).render("JACKBOX", True, BLANCO_VERDOSO)
            superficie.blit(texto, texto.get_rect(center=caja.center))
        respuesta = self._respuesta or "…"
        color = VERDE if respuesta == "Si" else VERDE_SUAVE if respuesta == "No" else BLANCO_VERDOSO
        texto_respuesta = self._fuente(tema.esc(48)).render(respuesta, True, color)
        superficie.blit(texto_respuesta, texto_respuesta.get_rect(center=(tema.esc(270), tema.esc(690))))
        if self.revelar_palabra:
            secreto = self._fuente(tema.esc(24)).render(f"PALABRA: {self.palabra}", True, VERDE)
            superficie.blit(secreto, secreto.get_rect(center=(tema.esc(270), tema.esc(750))))
        if self.mostrar_ganadores_tiktok:
            titulo_ganadores = self._fuente(tema.esc(16)).render("GANADORES TIKTOK", True, VERDE)
            superficie.blit(titulo_ganadores, titulo_ganadores.get_rect(center=(tema.esc(270), tema.esc(795))))
            if self.ganadores_tiktok:
                for indice, usuario in enumerate(self.ganadores_tiktok):
                    ganador = self._fuente(tema.esc(17)).render(f"{indice + 1}. {usuario[:24]}", True, BLANCO_VERDOSO)
                    superficie.blit(ganador, ganador.get_rect(center=(tema.esc(270), tema.esc(822 + indice * 26))))
            else:
                sin_ganadores = self._fuente(tema.esc(16)).render("Aún no hay ganadores", True, BLANCO_VERDOSO)
                superficie.blit(sin_ganadores, sin_ganadores.get_rect(center=(tema.esc(270), tema.esc(826))))
        mensaje = self._fuente(tema.esc(16)).render(self._mensaje, True, BLANCO_VERDOSO)
        superficie.blit(mensaje, mensaje.get_rect(center=(tema.esc(270), tema.esc(925))))
