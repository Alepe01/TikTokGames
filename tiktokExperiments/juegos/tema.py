"""Tema visual compartido: terminal verde con zona segura para pantallas pequeñas."""

import math

import pygame
import pygame.gfxdraw as gfxdraw

FUENTE = "Cascadia Code"
VERDE = (0, 255, 130)
VERDE_SUAVE = (110, 255, 180)
VERDE_OSCURO = (12, 76, 50)
NEGRO_PANEL = (5, 22, 15)
BLANCO_VERDOSO = (220, 255, 232)
ROJO_TURNO = (255, 65, 65)

# El diseño original de cada juego está pensado para un lienzo de 540x960; ESCALA
# multiplica cada coordenada/tamaño de fuente en el sitio donde se usa, para que el
# diff sea auto-verificable. main.py la ajusta en vivo según la pantalla real del
# anfitrión (puede terminar siendo un float, p. ej. 1.04), así que este valor por
# defecto sólo aplica si el módulo se usa suelto (pruebas, etc.) sin pasar por
# main.py. margen_lateral()/ancho_seguro() son funciones -no constantes- porque
# deben leer ESCALA en el momento en que se llaman, ya que main.py la cambia
# después de que este módulo se importó.
ESCALA = 2


def esc(valor: float) -> int:
    """Escala un número de diseño (pensado para 540x960) al lienzo real vigente.
    Siempre entero: pygame.Rect/draw exigen int, y ESCALA puede ser un float
    (p. ej. pantalla de 1000px de alto -> ESCALA ≈ 1.04)."""
    return int(round(valor * ESCALA))


def margen_lateral() -> int:
    return esc(70)


def ancho_seguro() -> int:
    return esc(400)


def circulo_suave(superficie, color, centro, radio, ancho=0):
    """Círculo con antialiasing (pygame.draw.circle no lo tiene)."""
    x, y, radio = int(centro[0]), int(centro[1]), int(radio)
    if ancho <= 0:
        gfxdraw.filled_circle(superficie, x, y, radio, color)
        gfxdraw.aacircle(superficie, x, y, radio, color)
        return
    # Anillo: se dibuja relleno en una capa aparte y se recorta el centro, en vez
    # de apilar aacircle concéntricos (eso deja un rayado visible por el blending).
    radio_interior = max(0, radio - int(ancho))
    lado = radio * 2 + 2
    capa = pygame.Surface((lado, lado), pygame.SRCALPHA)
    cx = cy = lado // 2
    gfxdraw.filled_circle(capa, cx, cy, radio, color)
    gfxdraw.aacircle(capa, cx, cy, radio, color)
    if radio_interior > 0:
        pygame.draw.circle(capa, (0, 0, 0, 0), (cx, cy), radio_interior)
    superficie.blit(capa, (x - cx, y - cy))


def linea_suave(superficie, color, inicio, fin, grosor):
    """Segmento grueso con tapas redondeadas, antialiased (pygame.draw.line no lo tiene)."""
    x1, y1 = inicio
    x2, y2 = fin
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / largo * (grosor / 2), dx / largo * (grosor / 2)
    puntos = [
        (int(x1 + nx), int(y1 + ny)),
        (int(x2 + nx), int(y2 + ny)),
        (int(x2 - nx), int(y2 - ny)),
        (int(x1 - nx), int(y1 - ny)),
    ]
    gfxdraw.filled_polygon(superficie, puntos, color)
    gfxdraw.aapolygon(superficie, puntos, color)
    radio_tapa = max(1, int(grosor / 2))
    circulo_suave(superficie, color, inicio, radio_tapa)
    circulo_suave(superficie, color, fin, radio_tapa)
