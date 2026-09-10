from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

try:
    import sounddevice as sd
except ImportError:
    sd = None

from TikTokGames.tiktokExperiments.ConsolaP8 import ConsolaP8
from TikTokGames.tiktokExperiments.GameManager import GameManager


class PanelControl:
    """Ventana fija 9:16; sus controles se traducen al contrato JuegoBase."""

    def __init__(self, root: tk.Tk, manager: GameManager, conectar_tiktok: Callable[[], bool]) -> None:
        self.manager = manager
        self.conectar_tiktok = conectar_tiktok
        self.root = root
        self.root.title("Panel de Control — Anfitrión")
        self.root.geometry("540x960")
        self.root.minsize(360, 640)
        # Mantiene 9:16 al redimensionar y conserva la barra nativa para moverla.
        self.root.wm_aspect(9, 16, 9, 16)
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.campos: dict[str, ttk.Entry] = {}
        self.etiquetas_campos: dict[str, ttk.Label] = {}
        self._consola_p8: ConsolaP8 | None = None
        self._crear_interfaz()

    def _crear_interfaz(self) -> None:
        contenedor = ttk.Frame(self.root)
        contenedor.pack(fill="both", expand=True)
        self.canvas_desplazable = tk.Canvas(contenedor, highlightthickness=0)
        barra = ttk.Scrollbar(contenedor, orient="vertical", command=self.canvas_desplazable.yview)
        self.canvas_desplazable.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.canvas_desplazable.pack(side="left", fill="both", expand=True)
        marco = ttk.Frame(self.canvas_desplazable, padding=24)
        self._ventana_canvas = self.canvas_desplazable.create_window((0, 0), window=marco, anchor="nw")
        marco.bind("<Configure>", self._actualizar_area_desplazable)
        self.canvas_desplazable.bind("<Configure>", self._ajustar_ancho_contenido)
        # bind_all permite desplazar aun cuando el cursor esté sobre una entrada o botón.
        self.root.bind_all("<MouseWheel>", self._desplazar_con_rueda)
        ttk.Label(marco, text="PANEL DEL SHOW", font=("Arial", 20, "bold")).pack(pady=(0, 26))
        self.juego_seleccionado = tk.StringVar(value="Trivia")
        ttk.Label(marco, text="Juego o escenario activo").pack(anchor="w")
        selector = ttk.Combobox(
            marco,
            textvariable=self.juego_seleccionado,
            values=self.manager.opciones_escena,
            state="readonly",
        )
        selector.pack(fill="x", pady=(3, 10), ipady=5)
        selector.bind("<<ComboboxSelected>>", self._seleccionar_juego)
        self.seccion_datos = ttk.Frame(marco)
        self.seccion_datos.pack(fill="x")
        self.filas_campos: dict[str, ttk.Frame] = {}
        for clave, etiqueta in (("pregunta", "Pregunta"), ("opcion_a", "Opción A"), ("opcion_b", "Opción B"), ("respuesta_correcta", "Respuesta correcta (A/B)")):
            fila = ttk.Frame(self.seccion_datos)
            fila.pack(fill="x")
            self.filas_campos[clave] = fila
            etiqueta_widget = ttk.Label(fila, text=etiqueta)
            etiqueta_widget.pack(anchor="w", pady=(10, 3))
            self.etiquetas_campos[clave] = etiqueta_widget
            entrada = ttk.Entry(fila, font=("Arial", 13))
            entrada.pack(fill="x", ipady=7)
            self.campos[clave] = entrada
        self.campos["respuesta_correcta"].insert(0, "A")
        self.config_jugadores = ttk.Frame(marco)
        ttk.Separator(self.config_jugadores).pack(fill="x", pady=(18, 8))
        ttk.Label(self.config_jugadores, text="CONFIGURACIÓN DE JUGADORES", font=("Arial", 10, "bold")).pack(anchor="w")
        for clave, etiqueta, valor in (
            ("numero_jugadores", "Número de jugadores (1–4)", "4"),
            ("tiempo_por_jugador", "Tiempo por jugador (segundos)", "60"),
        ):
            ttk.Label(self.config_jugadores, text=etiqueta).pack(anchor="w", pady=(8, 3))
            entrada = ttk.Entry(self.config_jugadores, font=("Arial", 13))
            entrada.insert(0, valor)
            entrada.pack(fill="x", ipady=5)
            self.campos[clave] = entrada
        self.config_caja = ttk.Frame(marco)
        ttk.Separator(self.config_caja).pack(fill="x", pady=(14, 8))
        ttk.Label(self.config_caja, text="CONFIGURACIÓN DE CAJA MUSICAL", font=("Arial", 10, "bold")).pack(anchor="w")
        for clave, etiqueta, valor in (
            ("tiempo_inicial_minutos", "Tiempo inicial (minutos)", "10"),
            ("tiempo_sin_respuesta_segundos", "Sin respuesta tras (segundos)", "30"),
            ("tiempo_reducido_minutos", "Tiempo reducido (minutos)", "3"),
        ):
            ttk.Label(self.config_caja, text=etiqueta).pack(anchor="w", pady=(7, 2))
            entrada = ttk.Entry(self.config_caja, font=("Arial", 12))
            entrada.insert(0, valor)
            entrada.pack(fill="x", ipady=4)
            self.campos[clave] = entrada
        self.config_ahorcado = ttk.Frame(marco)
        ttk.Separator(self.config_ahorcado).pack(fill="x", pady=(14, 8))
        ttk.Label(self.config_ahorcado, text="MODO DE AHORCADO", font=("Arial", 10, "bold")).pack(anchor="w")
        self.modo_automatico_ahorcado = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.config_ahorcado,
            text="Automático: aceptar letras individuales del chat (desmarcado = manual)",
            variable=self.modo_automatico_ahorcado,
        ).pack(anchor="w", pady=(6, 2))
        self.config_p8 = ttk.Frame(marco)
        ttk.Separator(self.config_p8).pack(fill="x", pady=(14, 8))
        ttk.Label(self.config_p8, text="PERSONAJE DE PLATICA CON P8", font=("Arial", 10, "bold")).pack(anchor="w")
        self.personaje_p8 = tk.StringVar(value="p8")
        marco_personaje_p8 = ttk.Frame(self.config_p8)
        marco_personaje_p8.pack(anchor="w", pady=(6, 2))
        for valor, etiqueta in (("p8", "P8"), ("antip8", "AntiP8")):
            ttk.Radiobutton(
                marco_personaje_p8,
                text=etiqueta,
                value=valor,
                variable=self.personaje_p8,
                command=self._cambiar_personaje_p8,
            ).pack(side="left", padx=(0, 16))
        self.boton_consola_p8 = ttk.Button(self.config_p8, text="Abrir consola P8", command=self._abrir_consola_p8)
        self.boton_consola_p8.pack(fill="x", pady=(6, 2), ipady=8)
        ttk.Separator(marco).pack(fill="x", pady=(20, 8))
        self.etiqueta_acciones = ttk.Label(marco, text="CONTROLES DEL JUEGO", font=("Arial", 10, "bold"))
        self.etiqueta_acciones.pack(anchor="w")
        self.boton_cargar = ttk.Button(marco, text="Guardar configuración", command=self._cargar)
        self.boton_cargar.pack(fill="x", pady=(35, 8), ipady=10)
        self.boton_iniciar = ttk.Button(marco, text="Iniciar juego", command=self.manager.iniciar_ronda)
        self.boton_iniciar.pack(fill="x", pady=8, ipady=10)
        self.boton_finalizar = ttk.Button(marco, text="Finalizar juego", command=self.manager.cerrar_ronda)
        self.boton_finalizar.pack(fill="x", pady=8, ipady=10)
        self.boton_instrucciones = ttk.Button(marco, text="Mostrar video de instrucciones", command=self._mostrar_instrucciones)
        self.boton_instrucciones.pack(fill="x", pady=8, ipady=10)
        self.presentador_visible = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            marco,
            text="Mostrar presentador virtual (usa el micrófono predeterminado)",
            variable=self.presentador_visible,
            command=self._cambiar_presentador,
        ).pack(anchor="w", pady=(12, 4))
        ttk.Label(marco, text="Micrófono del presentador").pack(anchor="w", pady=(5, 2))
        self.microfonos: dict[str, int | None] = {"Predeterminado del sistema": None}
        if sd is not None:
            try:
                for indice, info in enumerate(sd.query_devices()):
                    if int(info["max_input_channels"]) > 0:
                        self.microfonos[f"{indice}: {info['name']}"] = indice
            except Exception:
                pass
        self.microfono_seleccionado = tk.StringVar(value="Predeterminado del sistema")
        self.selector_microfono = ttk.Combobox(
            marco,
            textvariable=self.microfono_seleccionado,
            values=tuple(self.microfonos),
            state="readonly",
        )
        self.selector_microfono.pack(fill="x", pady=(0, 8))
        self.selector_microfono.bind("<<ComboboxSelected>>", self._seleccionar_microfono)
        self.boton_tiktok = ttk.Button(marco, text="Conectar TikTok Live", command=self._conectar_tiktok)
        self.boton_tiktok.pack(fill="x", pady=(20, 8), ipady=10)
        self.estado = ttk.Label(marco, text="Listo. El chat se ignora hasta iniciar la ronda.", wraplength=450)
        self.estado.pack(pady=25)
        self._actualizar_campos_juego()

    def _actualizar_area_desplazable(self, _evento: tk.Event) -> None:
        self.canvas_desplazable.configure(scrollregion=self.canvas_desplazable.bbox("all"))

    def _ajustar_ancho_contenido(self, evento: tk.Event) -> None:
        self.canvas_desplazable.itemconfigure(self._ventana_canvas, width=evento.width)

    def _desplazar_con_rueda(self, evento: tk.Event) -> None:
        # Windows entrega múltiplos de 120 por cada paso de rueda.
        self.canvas_desplazable.yview_scroll(-int(evento.delta / 120), "units")

    def _seleccionar_juego(self, _evento: object) -> None:
        self.manager.seleccionar_contenido(self.juego_seleccionado.get())
        self._actualizar_campos_juego()
        self.estado.config(text=f"Activo: {self.juego_seleccionado.get()}.")

    def _actualizar_campos_juego(self) -> None:
        """La ventana conserva su diseño; sólo adapta los datos al minijuego."""
        juego = self.juego_seleccionado.get()
        es_escenario = juego in self.manager.ESCENARIOS
        if es_escenario:
            for fila in self.filas_campos.values():
                fila.pack_forget()
            self.config_jugadores.pack_forget()
            self.config_caja.pack_forget()
            self.config_ahorcado.pack_forget()
            self.config_p8.pack_forget()
            self.boton_cargar.state(["disabled"])
            self.boton_iniciar.state(["disabled"])
            self.boton_finalizar.state(["disabled"])
            self.boton_instrucciones.state(["disabled"])
            self.etiqueta_acciones.config(text="CONTROLES DEL ESCENARIO")
            return
        self.boton_cargar.state(["!disabled"])
        self.boton_iniciar.state(["!disabled"])
        self.boton_finalizar.state(["!disabled"])
        self.boton_instrucciones.state(["!disabled"])
        self.etiqueta_acciones.config(text="CONTROLES DEL JUEGO")
        campos_visibles = {
            "Trivia": ("pregunta", "opcion_a", "opcion_b", "respuesta_correcta"),
            "Ahorcado": ("pregunta",),
            "Caja Musical": ("pregunta",),
            "Memorama": ("pregunta",),
            "Platica con P8": ("pregunta",),
        }
        for fila in self.filas_campos.values():
            fila.pack_forget()
        for clave in campos_visibles[juego]:
            self.filas_campos[clave].pack(fill="x")
        self.config_jugadores.pack_forget()
        self.config_caja.pack_forget()
        self.config_ahorcado.pack_forget()
        self.config_p8.pack_forget()
        if juego in {"Memorama", "Ahorcado"}:
            self.config_jugadores.pack(fill="x", before=self.boton_cargar)
        if juego == "Ahorcado":
            self.config_ahorcado.pack(fill="x", before=self.boton_cargar)
        elif juego == "Caja Musical":
            self.config_caja.pack(fill="x", before=self.boton_cargar)
        elif juego == "Platica con P8":
            self.config_p8.pack(fill="x", before=self.boton_cargar)
        etiquetas = {
            "Trivia": ("Pregunta", "Opción A", "Opción B", "Respuesta correcta (A/B)"),
            "Ahorcado": ("Palabra secreta (sin espacios)", "Dato reservado", "Dato reservado", "Dato reservado"),
            "Caja Musical": ("Palabra secreta (sólo para anfitrión)", "Dato reservado", "Dato reservado", "Dato reservado"),
            "Memorama": ("Título del tablero", "Imágenes: carpeta Imagenes-memorama", "Imágenes: se forman pares automáticamente", "Dato reservado"),
            "Platica con P8": ("Mensaje inicial de P8", "Dato reservado", "Dato reservado", "Dato reservado"),
        }
        for clave, texto in zip(self.etiquetas_campos, etiquetas[juego]):
            self.etiquetas_campos[clave].config(text=texto)
        # Ahorcado y P8 sólo requieren su campo principal.
        solo_palabra = juego in {"Ahorcado", "Caja Musical", "Memorama", "Platica con P8"}
        solo_titulo = juego == "Memorama"
        for clave in ("opcion_a", "opcion_b", "respuesta_correcta"):
            desactivar = solo_palabra or (solo_titulo and clave == "respuesta_correcta")
            self.campos[clave].state(["disabled"] if desactivar else ["!disabled"])
        # Estos ajustes se aplican a los juegos locales por turnos.
        for clave in ("numero_jugadores", "tiempo_por_jugador"):
            self.campos[clave].state(["!disabled"] if juego in {"Memorama", "Ahorcado"} else ["disabled"])
        for clave in ("tiempo_inicial_minutos", "tiempo_sin_respuesta_segundos", "tiempo_reducido_minutos"):
            self.campos[clave].state(["!disabled"] if juego == "Caja Musical" else ["disabled"])
        self._actualizar_botones(juego)

    def _actualizar_botones(self, juego: str) -> None:
        """El panel sigue siendo único, pero nombra cada acción según el minijuego."""
        textos = {
            "Trivia": ("Guardar pregunta y opciones", "Abrir votación", "Cerrar votación y mostrar resultado"),
            "Ahorcado": ("Guardar palabra y jugadores", "Iniciar ahorcado", "Finalizar ahorcado"),
            "Caja Musical": ("Guardar palabra y cronómetro", "Iniciar cronómetro", "Terminar Caja Misteriosa"),
            "Memorama": ("Preparar tablero e imágenes", "Mezclar e iniciar partida", "Detener partida"),
            "Platica con P8": ("Guardar mensaje inicial", "Abrir conversación", "Cerrar conversación"),
        }
        guardar, iniciar, finalizar = textos[juego]
        self.boton_cargar.config(text=guardar)
        self.boton_iniciar.config(text=iniciar)
        self.boton_finalizar.config(text=finalizar)

    def _mostrar_instrucciones(self) -> None:
        self.manager.mostrar_instrucciones()
        self.estado.config(text="Reproduciendo instrucciones (si existe el video).")

    def _abrir_consola_p8(self) -> None:
        if self._consola_p8 is not None and self._consola_p8.winfo_exists():
            self._consola_p8.deiconify()
            self._consola_p8.lift()
            self._consola_p8.focus_force()
            return
        self._consola_p8 = ConsolaP8(self.root, self.manager)

    def _cambiar_presentador(self) -> None:
        self.manager.mostrar_presentador(self.presentador_visible.get())

    def _cambiar_personaje_p8(self) -> None:
        self.manager.seleccionar_personaje_p8(self.personaje_p8.get())
        self.estado.config(text=f"Personaje activo: {self.personaje_p8.get().upper()}")

    def _seleccionar_microfono(self, _evento: object) -> None:
        nombre = self.microfono_seleccionado.get()
        self.manager.seleccionar_microfono(self.microfonos.get(nombre))
        self.estado.config(text=f"Micrófono seleccionado: {nombre}")

    def _conectar_tiktok(self) -> None:
        if self.conectar_tiktok():
            self.boton_tiktok.state(["disabled"])
            self.boton_tiktok.config(text="Conectando…")
            self.estado.config(text="Conectando a TikTok Live…")

    def mostrar_estado_tiktok(self, mensaje: str) -> None:
        """Tkinter sólo se actualiza desde su hilo principal."""
        def actualizar() -> None:
            self.estado.config(text=mensaje)
            if mensaje.startswith("Conectado correctamente"):
                self.boton_tiktok.config(text="Conectado")
                self.boton_tiktok.state(["disabled"])
            elif mensaje.startswith("No se pudo"):
                self.boton_tiktok.config(text="No se pudo conectar (reintentar)")
                self.boton_tiktok.state(["!disabled"])

        self.root.after(0, actualizar)

    def _cargar(self) -> None:
        datos: dict[str, Any] = {clave: entrada.get() for clave, entrada in self.campos.items()}
        datos["modo_automatico"] = self.modo_automatico_ahorcado.get()
        # Mapea el botón genérico al método configurar_datos de JuegoBase.
        self.manager.cargar_datos(datos)
        self.estado.config(text="Datos enviados a la pantalla.")

    def _al_cerrar(self) -> None:
        self.manager.detener()
        self.root.destroy()

    def ejecutar(self) -> None:
        self.root.mainloop()
