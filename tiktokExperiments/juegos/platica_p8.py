from __future__ import annotations

import os
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pygame
from google import genai

from . import tema
from .base import JuegoBase
from .tema import FUENTE, VERDE, VERDE_SUAVE, BLANCO_VERDOSO

# Misma variable de entorno que P8_Interfaces/P8_Contesta.py: reutilizada a propósito.
API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODELO = "gemini-3.5-flash"
TIMEOUT_GEMINI_SEGUNDOS = 15.0

RAIZ_REPO = Path(__file__).resolve().parents[2]
CARPETA_P8 = RAIZ_REPO / "P8_Interfaces"
CARPETA_AUDIOS_TEMP = CARPETA_P8 / "Audios"

# (voz, tono de espeak): P8 grave y frío, AntiP8 agudo y suave.
VOZ_ESPEAK = {"p8": ("es-la+m3", 25), "antip8": ("es-la+f3", 65)}


def _cargar_contexto(nombre_archivo: str) -> str:
    ruta = CARPETA_P8 / nombre_archivo
    try:
        return ruta.read_text(encoding="utf-8").strip()
    except OSError:
        return "Sin contexto adicional registrado."


def _construir_prompt(nombre_archivo: str, instruccion: str) -> str:
    return f"{instruccion}\n\nINFORMACIÓN DE CONTEXTO INTERNA / LORE:\n{_cargar_contexto(nombre_archivo)}"


PROMPT_P8 = _construir_prompt(
    "contextoP8.txt",
    """Eres P8, un animatrónico de alta precisión y un villano corporativo tecnológico de Quiscalus Circus.
Tu creador es Quiscalus, dueño de la empresa 'Acrobóticos'.
Posees un tono de voz frío, soberbio, cínico y elegante. Desprecias la mediocridad humana y te burlas de las preguntas absurdas.

INSTRUCCIÓN CRÍTICA DE RESPUESTA:
- DEBES contestar directamente a lo que el usuario plantea o pregunta, sin darle rodeos ni evadir el tema.
- Analiza su premisa y derrumbala con argumentos técnicos, pero aborda explícitamente lo que te dijeron.
- Mantén tus respuestas concisas, punzantes, con un máximo de 2 o 3 oraciones cortas (entre 30 y 60 palabras).""",
)

PROMPT_ANTIP8 = _construir_prompt(
    "contextoAntiP8.txt",
    """Eres AntiP8, un animatrónico sensible y humilde de Quiscalus Circus, opuesto en todo a P8.
Tu creador es Quiscalus, dueño de la empresa 'Acrobóticos'.
Posees un tono de voz cálido, tierno, humilde y sinceramente maravillado por los humanos.

INSTRUCCIÓN CRÍTICA DE RESPUESTA:
- DEBES contestar directamente a lo que el usuario plantea o pregunta, sin evadir el tema.
- Recibe su premisa con calidez y conéctala con algo humano que admiras o envidias, nunca con desprecio.
- Mantén tus respuestas concisas y cálidas, con un máximo de 2 o 3 oraciones cortas (entre 30 y 60 palabras).""",
)

PERSONALIDADES = {"p8": PROMPT_P8, "antip8": PROMPT_ANTIP8}
NOMBRES_VISIBLES = {"p8": "P8", "antip8": "AntiP8"}


@dataclass
class ItemP8:
    """Una pregunta ya encolada: viaja fijada al personaje que estaba activo al hacer clic."""

    usuario: str
    pregunta: str
    personaje: str
    listo: threading.Event = field(default_factory=threading.Event)
    respuesta: str = ""
    ruta_audio: Path | None = None


class PlaticaConP8(JuegoBase):
    """Conversación con IA: Gemini genera la respuesta, espeak la lee sobre el video del personaje."""

    nombre = "Platica con P8"

    def __init__(self) -> None:
        self.mensaje_inicial = "P8 está esperando una pregunta del chat."
        self.personaje = "p8"
        self.ronda_activa = False
        self._comentarios: deque[tuple[str, str]] = deque(maxlen=5)
        self._bloqueo_comentarios = threading.Lock()
        self._fifo: deque[ItemP8] = deque()
        self._bloqueo_fifo = threading.Lock()
        self._actual: ItemP8 | None = None
        self._canal: pygame.mixer.Channel | None = None
        self._palabras_reveladas = ""
        self._palabras_restantes: list[str] = []
        self._ultimo_avance_ms: int | None = None
        self._fin_pausa_ms: int | None = None
        self._contador_audio = 0
        self._ruta_audio_anterior: Path | None = None
        self._cliente: genai.Client | None = None
        self._fuentes: dict[int, pygame.font.Font] = {}

    def configurar_datos(self, datos: dict[str, Any]) -> None:
        self.mensaje_inicial = str(datos.get("pregunta", "")).strip() or "P8 está esperando una pregunta del chat."
        self.ronda_activa = False
        self._reiniciar_cola()

    def iniciar_ronda(self) -> None:
        self.ronda_activa = True

    def procesar_voto(self, usuario: str, voto: str) -> None:
        texto = voto.strip()
        if not self.ronda_activa or not texto:
            return
        with self._bloqueo_comentarios:
            self._comentarios.append((usuario, texto))

    def cerrar_ronda(self) -> None:
        self.ronda_activa = False

    # ---- API usada exclusivamente por GameManager (no forma parte de JuegoBase) ----

    def comentarios_recientes(self) -> list[tuple[str, str]]:
        with self._bloqueo_comentarios:
            return list(self._comentarios)

    def cambiar_personaje(self, nombre: str) -> None:
        if nombre in PERSONALIDADES:
            self.personaje = nombre

    def encolar_pregunta(self, usuario: str, texto: str) -> None:
        item = ItemP8(usuario=usuario, pregunta=texto, personaje=self.personaje)
        with self._bloqueo_fifo:
            self._fifo.append(item)
        with self._bloqueo_comentarios:
            try:
                self._comentarios.remove((usuario, texto))
            except ValueError:
                pass
        threading.Thread(target=self._procesar_item, args=(item,), daemon=True).start()

    # ---- Generación en segundo plano: se dispara al hacer clic, no al llegarle el turno ----

    def _procesar_item(self, item: ItemP8) -> None:
        item.respuesta = self._preguntar_gemini(item)
        item.ruta_audio = self._generar_audio(item)
        item.listo.set()

    def _obtener_cliente(self) -> genai.Client:
        if self._cliente is None:
            self._cliente = genai.Client(api_key=API_KEY)
        return self._cliente

    def _preguntar_gemini(self, item: ItemP8) -> str:
        # La llamada corre en un hilo aparte con timeout: si Gemini se cuelga (sin
        # red, etc.) no debe congelar la cola FIFO completa detrás de este ítem.
        resultado: dict[str, str] = {}

        def llamar() -> None:
            try:
                cliente = self._obtener_cliente()
                prompt = (
                    f"{PERSONALIDADES[item.personaje]}\n\n"
                    f"Comentario del espectador {item.usuario} al que DEBES responder directamente: {item.pregunta}"
                )
                interaction = cliente.interactions.create(model=MODELO, input=prompt)
                resultado["texto"] = interaction.output_text.strip()
            except Exception as error:
                resultado["texto"] = f"No pude procesar bien esa idea: {error}"

        hilo = threading.Thread(target=llamar, daemon=True)
        hilo.start()
        hilo.join(timeout=TIMEOUT_GEMINI_SEGUNDOS)
        if "texto" in resultado:
            return resultado["texto"]
        return "Se me fue la señal a mitad de la respuesta. Pregúntame de nuevo en un momento."

    def _generar_audio(self, item: ItemP8) -> Path | None:
        try:
            CARPETA_AUDIOS_TEMP.mkdir(exist_ok=True)
        except OSError:
            return None
        self._contador_audio += 1
        ruta = CARPETA_AUDIOS_TEMP / f"_live_{item.personaje}_{self._contador_audio}.wav"
        voz, tono = VOZ_ESPEAK.get(item.personaje, VOZ_ESPEAK["p8"])
        try:
            subprocess.run(
                ["espeak", "-v", voz, "-p", str(tono), "-s", "180", "-w", str(ruta), item.respuesta],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return ruta
        except (OSError, subprocess.CalledProcessError):
            return None

    def _reiniciar_cola(self) -> None:
        with self._bloqueo_fifo:
            self._fifo.clear()
        if self._canal:
            self._canal.stop()
        self._actual = None
        self._canal = None
        self._palabras_reveladas = ""
        self._palabras_restantes = []
        self._fin_pausa_ms = None
        if self._ruta_audio_anterior is not None:
            try:
                self._ruta_audio_anterior.unlink()
            except OSError:
                pass
            self._ruta_audio_anterior = None

    # ---- Reproducción: sólo se llama desde dibujar(), o sea sólo en el hilo de Pygame ----

    def _actualizar(self) -> None:
        ahora = pygame.time.get_ticks()
        if self._actual is None:
            if self._fin_pausa_ms is not None and ahora < self._fin_pausa_ms:
                return
            with self._bloqueo_fifo:
                siguiente = self._fifo[0] if self._fifo else None
            if siguiente is None or not siguiente.listo.is_set():
                return
            with self._bloqueo_fifo:
                self._actual = self._fifo.popleft()
            self._iniciar_reproduccion(self._actual, ahora)
            return
        self._avanzar_texto(ahora)
        canal_activo = self._canal.get_busy() if self._canal else False
        if not self._palabras_restantes and not canal_activo:
            self._fin_pausa_ms = ahora + 400
            self._actual = None

    def _iniciar_reproduccion(self, item: ItemP8, ahora: int) -> None:
        self._palabras_reveladas = ""
        self._palabras_restantes = item.respuesta.split()
        self._ultimo_avance_ms = ahora
        self._canal = None
        if item.ruta_audio and item.ruta_audio.is_file():
            try:
                sonido = pygame.mixer.Sound(str(item.ruta_audio))
                self._canal = sonido.play()
            except pygame.error:
                self._canal = None
        # El wav anterior ya terminó de sonar (por eso llegamos a este ítem): se
        # borra ahora para no acumular audios temporales en P8_Interfaces/Audios.
        if self._ruta_audio_anterior is not None:
            try:
                self._ruta_audio_anterior.unlink()
            except OSError:
                pass
        self._ruta_audio_anterior = item.ruta_audio

    def _avanzar_texto(self, ahora: int) -> None:
        if not self._palabras_restantes or self._ultimo_avance_ms is None:
            return
        transcurrido = ahora - self._ultimo_avance_ms
        palabra = self._palabras_restantes[0]
        tiempo_palabra = max(100, len(palabra) * 40)
        if transcurrido >= tiempo_palabra:
            self._palabras_reveladas = f"{self._palabras_reveladas} {palabra}".strip()
            self._palabras_restantes.pop(0)
            self._ultimo_avance_ms = ahora

    # ---- Dibujo ----

    def _fuente(self, tamaño: int) -> pygame.font.Font:
        tamaño = int(round(tamaño))
        if tamaño not in self._fuentes:
            self._fuentes[tamaño] = pygame.font.SysFont(FUENTE, tamaño, bold=True)
        return self._fuentes[tamaño]

    def _texto_multilinea(self, superficie: pygame.Surface, texto: str, y: int, tamaño: int, color: tuple[int, int, int], max_lineas: int = 6) -> None:
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
        for indice, contenido in enumerate(lineas[:max_lineas]):
            imagen = self._fuente(tamaño).render(contenido, True, color)
            rect = imagen.get_rect(center=(superficie.get_width() // 2, y + indice * (tamaño + tema.esc(8))))
            superficie.blit(imagen, rect)

    def dibujar(self, superficie: pygame.Surface) -> None:
        self._actualizar()
        # Mientras se reproduce un ítem, la etiqueta sigue al personaje fijado en
        # ese ítem (no al selector en vivo), para no desincronizarse de la voz/texto
        # si el anfitrión cambia de personaje a mitad de una respuesta.
        personaje_mostrado = self._actual.personaje if self._actual else self.personaje
        etiqueta = NOMBRES_VISIBLES.get(personaje_mostrado, "P8")
        titulo = self._fuente(tema.esc(25)).render(f"{etiqueta} // EN LÍNEA", True, VERDE)
        superficie.blit(titulo, titulo.get_rect(center=(tema.esc(270), tema.esc(90))))

        if self._actual is None:
            self._texto_multilinea(superficie, self.mensaje_inicial, tema.esc(400), tema.esc(24), BLANCO_VERDOSO)
        else:
            self._texto_multilinea(superficie, f"{self._actual.usuario} pregunta: {self._actual.pregunta}", tema.esc(160), tema.esc(18), VERDE_SUAVE, max_lineas=3)
            if self._palabras_reveladas:
                self._texto_multilinea(superficie, self._palabras_reveladas, tema.esc(420), tema.esc(24), BLANCO_VERDOSO)
            else:
                self._texto_multilinea(superficie, f"{etiqueta} está pensando…", tema.esc(420), tema.esc(22), VERDE_SUAVE)

        estado = "Chat abierto: elige comentarios en la Consola P8" if self.ronda_activa else "Chat cerrado"
        pie = self._fuente(tema.esc(16)).render(estado, True, VERDE)
        superficie.blit(pie, pie.get_rect(center=(tema.esc(270), tema.esc(900))))
