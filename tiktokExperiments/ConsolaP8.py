from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from TikTokGames.tiktokExperiments.GameManager import GameManager

VERDE = "#00FF82"
NEGRO_PANEL = "#05160F"
BLANCO_VERDOSO = "#DCFFE8"


class ConsolaP8(tk.Toplevel):
    """Ventana flotante estilo terminal: elige personaje y envía comentarios a la cola FIFO."""

    def __init__(self, master: tk.Misc, manager: GameManager) -> None:
        super().__init__(master)
        self.manager = manager
        self.title("Consola P8 — Últimos comentarios")
        self.geometry("420x460")
        self.configure(bg=NEGRO_PANEL)
        self._filas: list[tk.Frame] = []
        self._id_programado: str | None = None
        self._crear_interfaz()
        self._refrescar()

    def _crear_interfaz(self) -> None:
        tk.Label(
            self, text="CONSOLA P8", font=("Consolas", 16, "bold"), bg=NEGRO_PANEL, fg=VERDE
        ).pack(pady=(14, 4))
        tk.Label(
            self,
            text="El personaje (P8/AntiP8) se elige en el Panel de Control.",
            font=("Consolas", 9),
            bg=NEGRO_PANEL,
            fg=BLANCO_VERDOSO,
        ).pack(pady=(0, 10))

        tk.Label(
            self,
            text="Últimos 5 comentarios (se actualiza cada 10 s):",
            font=("Consolas", 10, "bold"),
            bg=NEGRO_PANEL,
            fg=BLANCO_VERDOSO,
        ).pack(anchor="w", padx=14)

        self.marco_lista = tk.Frame(self, bg=NEGRO_PANEL)
        self.marco_lista.pack(fill="both", expand=True, padx=14, pady=10)

        self.estado = tk.Label(
            self, text="Esperando comentarios…", font=("Consolas", 9), bg=NEGRO_PANEL, fg=VERDE, wraplength=380
        )
        self.estado.pack(side="bottom", pady=10)

    def _refrescar(self) -> None:
        for fila in self._filas:
            fila.destroy()
        self._filas.clear()

        comentarios = self.manager.comentarios_recientes_p8()
        if not comentarios:
            self.estado.config(text="Sin comentarios nuevos todavía.")
        else:
            self.estado.config(text=f"{len(comentarios)} comentario(s) disponible(s) para responder.")
        for usuario, texto in comentarios:
            fila = tk.Frame(self.marco_lista, bg=NEGRO_PANEL)
            fila.pack(fill="x", pady=3)
            etiqueta = tk.Label(
                fila,
                text=f"{usuario}: {texto}",
                font=("Consolas", 10),
                bg=NEGRO_PANEL,
                fg=BLANCO_VERDOSO,
                wraplength=280,
                justify="left",
                anchor="w",
            )
            etiqueta.pack(side="left", fill="x", expand=True)
            ttk.Button(
                fila,
                text="Responder",
                command=lambda u=usuario, t=texto: self._enviar(u, t),
            ).pack(side="right")
            self._filas.append(fila)

        self._id_programado = self.after(10_000, self._refrescar)

    def _enviar(self, usuario: str, texto: str) -> None:
        self.manager.enviar_pregunta_p8(usuario, texto)
        # No esperamos al próximo refresco de 10 s para quitarlo de la vista;
        # cancelamos el programado para no acumular llamadas duplicadas.
        if self._id_programado is not None:
            self.after_cancel(self._id_programado)
        self._refrescar()
        self.estado.config(text=f"Enviado a la cola: {usuario}: {texto[:60]}")
