"""Render geometric figure specs to PNG images using matplotlib.

Supported shape types
---------------------
circle        — circle with centre, radius, chords, arcs, angle arcs
triangle      — triangle with labelled vertices, sides, angles (right_angle_at supported)
angle         — standalone angle formed by two rays
quadrilateral — rectangle, square, parallelogram, trapezoid, rhombus, general quad
polygon       — any closed polygon with labelled vertices and sides
number_line   — number line with tick marks, highlighted points, span arrows
"""
from __future__ import annotations

import math
import os
import tempfile

import matplotlib
matplotlib.use('Agg')                    # non-interactive, must precede pyplot import
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import Arc

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Figure dimensions (inches)
_FIG_W = 3.4
_FIG_H = 2.6
_NL_W  = 5.0      # number line — wider, shorter
_NL_H  = 1.8
_DPI   = 150


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_figure(figure: dict) -> str | None:
    """Render *figure* dict to a temporary PNG file.

    Returns the temp file path (caller must delete it), or ``None`` on failure.
    Supports both the old ``"type"`` key (circle-only schema) and the new
    ``"shape"`` key (all shapes).
    """
    if not figure:
        return None

    shape = figure.get('shape') or figure.get('type', '')
    renderer_fn = _RENDERERS.get(shape)
    if renderer_fn is None:
        logger.debug('No renderer for figure shape=%r', shape)
        return None

    w, h = (_NL_W, _NL_H) if shape == 'number_line' else (_FIG_W, _FIG_H)
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    try:
        renderer_fn(ax, figure)
    except Exception:
        logger.exception('Figure render error: shape=%r', shape)
        plt.close(fig)
        return None

    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp.close()
    try:
        fig.savefig(tmp.name, dpi=_DPI, bbox_inches='tight',
                    pad_inches=0.12, facecolor='white')
    except Exception:
        logger.exception('Figure save error')
        os.unlink(tmp.name)
        return None
    finally:
        plt.close(fig)

    return tmp.name


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

def _unit(src: tuple, dst: tuple) -> tuple[float, float]:
    """Return the unit vector from *src* to *dst* (or (1,0) if coincident)."""
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-12 else (1.0, 0.0)


def _auto_bounds(ax, pts: list[tuple], pad: float = 0.28) -> None:
    """Set axis limits with proportional padding around *pts*."""
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    xr = max(xs) - min(xs) or 1.0
    yr = max(ys) - min(ys) or 1.0
    ax.set_xlim(min(xs) - xr * pad, max(xs) + xr * pad)
    ax.set_ylim(min(ys) - yr * pad, max(ys) + yr * pad)


def _centroid(pts: list[tuple]) -> tuple[float, float]:
    return (sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts))


def _point_dot_label(ax, px: float, py: float, label: str,
                     all_pts: list[tuple], fontsize: int = 9,
                     is_center: bool = False) -> None:
    """Draw a filled dot and an outward-offset bold label at *(px, py)*."""
    ax.plot(px, py, 'ko', markersize=3, zorder=5)
    if not label:
        return
    cx, cy = _centroid(all_pts)
    dx, dy = px - cx, py - cy
    d = math.hypot(dx, dy)
    span = max((math.hypot(p[0] - cx, p[1] - cy) for p in all_pts), default=1.0)
    off = span * 0.20
    if is_center or d < 1e-9:
        nx, ny = 0.07, -0.07
    else:
        nx, ny = dx / d, dy / d
    ax.text(px + nx * off, py + ny * off, label,
            fontsize=fontsize, fontweight='bold',
            ha='center', va='center', zorder=6)


def _segment_label(ax, x1: float, y1: float, x2: float, y2: float,
                   text: str, fontsize: int = 8) -> None:
    """Label a segment at its midpoint with a white background box."""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    nx, ny = (-dy / d * 0.13, dx / d * 0.13) if d > 1e-9 else (0.0, 0.13)
    ax.text(mx + nx, my + ny, text, fontsize=fontsize,
            ha='center', va='center',
            bbox={'boxstyle': 'square,pad=0.06', 'fc': 'white', 'ec': 'none'})


def _angle_arc(ax, vertex: tuple, p1: tuple, p2: tuple,
               arc_r: float, label: str = '', fontsize: int = 7) -> None:
    """Draw a small angle arc at *vertex* between directions to *p1* and *p2*."""
    vx, vy = vertex
    a1 = math.degrees(math.atan2(p1[1] - vy, p1[0] - vx))
    a2 = math.degrees(math.atan2(p2[1] - vy, p2[0] - vx))
    diff = (a2 - a1) % 360
    if diff > 180:                          # always sweep the shorter arc
        a1, a2, diff = a2, a1 + 360, 360 - diff
    else:
        a2 = a1 + diff
    ax.add_patch(Arc((vx, vy), 2 * arc_r, 2 * arc_r,
                     angle=0, theta1=a1, theta2=a2,
                     color='#444', linewidth=0.9))
    if label:
        mid = math.radians((a1 + a2) / 2)
        lx = vx + arc_r * 1.60 * math.cos(mid)
        ly = vy + arc_r * 1.60 * math.sin(mid)
        ax.text(lx, ly, label, fontsize=fontsize,
                ha='center', va='center', color='#222')


def _right_angle_sq(ax, vertex: tuple, p1: tuple, p2: tuple,
                    size: float) -> None:
    """Draw a small right-angle square marker at *vertex*."""
    vx, vy = vertex
    d1 = _unit(vertex, p1)
    d2 = _unit(vertex, p2)
    sq = mpatches.Polygon([
        (vx + d1[0] * size,               vy + d1[1] * size),
        (vx + d1[0] * size + d2[0] * size, vy + d1[1] * size + d2[1] * size),
        (vx + d2[0] * size,               vy + d2[1] * size),
    ], closed=False, fill=False, edgecolor='black', linewidth=0.8)
    ax.add_patch(sq)


def _adj_side_len(coords: dict, label: str, ordered_labels: list) -> float:
    """Shortest side adjacent to *label* in an ordered polygon."""
    idx = ordered_labels.index(label)
    p_prev = coords[ordered_labels[(idx - 1) % len(ordered_labels)]]
    p_next = coords[ordered_labels[(idx + 1) % len(ordered_labels)]]
    vx, vy = coords[label]
    return min(
        math.hypot(vx - p_prev[0], vy - p_prev[1]),
        math.hypot(vx - p_next[0], vy - p_next[1]),
    )


# ---------------------------------------------------------------------------
# Circle renderer
# ---------------------------------------------------------------------------

def _render_circle(ax, spec: dict) -> None:
    center_label = spec.get('center', 'O')
    coords: dict[str, tuple[float, float]] = {center_label: (0.0, 0.0)}

    for pt in spec.get('points', []):
        a = math.radians(pt.get('angle_deg', 0))
        coords[pt['label']] = (math.cos(a), math.sin(a))

    ax.add_patch(plt.Circle((0.0, 0.0), 1.0,
                             fill=False, color='black', linewidth=1.5))

    for seg in spec.get('segments', []):
        if len(seg) == 2 and seg[0] in coords and seg[1] in coords:
            x1, y1 = coords[seg[0]]
            x2, y2 = coords[seg[1]]
            ax.plot([x1, x2], [y1, y2], 'k-', linewidth=1.2, zorder=2)

    # Support both single angle_arc dict and angle_arcs list
    arc_list: list[dict] = list(spec.get('angle_arcs') or [])
    if spec.get('angle_arc'):
        arc_list.insert(0, spec['angle_arc'])
    for ai in arc_list:
        v = ai.get('vertex', '')
        fp = ai.get('from_point', '')
        tp = ai.get('to_point', '')
        if all(k in coords for k in (v, fp, tp)):
            _angle_arc(ax, coords[v], coords[fp], coords[tp],
                       0.25, ai.get('label', ''))

    for sl in spec.get('segment_labels', []):
        on, text = sl.get('on', []), sl.get('text', '')
        if len(on) == 2 and all(p in coords for p in on) and text:
            _segment_label(ax, *coords[on[0]], *coords[on[1]], text)

    all_pts = list(coords.values())
    for lbl, (px, py) in coords.items():
        _point_dot_label(ax, px, py, lbl, all_pts,
                         is_center=(lbl == center_label))

    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.55, 1.55)


# ---------------------------------------------------------------------------
# Triangle renderer  (AI supplies vertex x/y)
# ---------------------------------------------------------------------------

def _render_triangle(ax, spec: dict) -> None:
    vdata = spec.get('vertices', [])
    if len(vdata) < 3:
        return

    coords: dict[str, tuple[float, float]] = {
        v['label']: (float(v.get('x', 0)), float(v.get('y', 0)))
        for v in vdata
    }
    labels = [v['label'] for v in vdata]
    pts = [coords[l] for l in labels]

    ax.add_patch(plt.Polygon(pts, closed=True,
                              fill=False, edgecolor='black', linewidth=1.5))

    right_at = spec.get('right_angle_at')
    if right_at and right_at in coords:
        others = [l for l in labels if l != right_at]
        vx, vy = coords[right_at]
        side_len = min(
            math.hypot(vx - coords[others[0]][0], vy - coords[others[0]][1]),
            math.hypot(vx - coords[others[1]][0], vy - coords[others[1]][1]),
        )
        _right_angle_sq(ax, coords[right_at],
                        coords[others[0]], coords[others[1]],
                        size=max(side_len * 0.10, 0.15))

    for al in spec.get('angle_labels', []):
        v, text = al.get('at'), al.get('label', '')
        if v in coords and text and v != right_at:
            others = [l for l in labels if l != v]
            vx, vy = coords[v]
            side_len = min(
                math.hypot(vx - coords[others[0]][0], vy - coords[others[0]][1]),
                math.hypot(vx - coords[others[1]][0], vy - coords[others[1]][1]),
            )
            _angle_arc(ax, coords[v],
                       coords[others[0]], coords[others[1]],
                       max(side_len * 0.15, 0.18), text, fontsize=7)

    for side in spec.get('sides', []):
        f, t, text = side.get('from'), side.get('to'), side.get('label', '')
        if f in coords and t in coords and text:
            _segment_label(ax, *coords[f], *coords[t], text)

    for lbl, (px, py) in coords.items():
        _point_dot_label(ax, px, py, lbl, pts)

    _auto_bounds(ax, pts)


# ---------------------------------------------------------------------------
# Angle renderer  (standalone angle — two rays from a vertex)
# ---------------------------------------------------------------------------

def _render_angle(ax, spec: dict) -> None:
    vx, vy = 0.0, 0.0
    ray_len = 2.4
    a1_deg = float(spec.get('ray1_deg', 0))
    a2_deg = float(spec.get('ray2_deg', 90))
    a1, a2 = math.radians(a1_deg), math.radians(a2_deg)
    p1 = (vx + ray_len * math.cos(a1), vy + ray_len * math.sin(a1))
    p2 = (vx + ray_len * math.cos(a2), vy + ray_len * math.sin(a2))

    ap = {'arrowstyle': '->', 'color': 'black', 'lw': 1.2}
    ax.annotate('', xy=p1, xytext=(vx, vy), arrowprops=ap)
    ax.annotate('', xy=p2, xytext=(vx, vy), arrowprops=ap)

    _angle_arc(ax, (vx, vy), p1, p2, 0.65,
               spec.get('label', ''), fontsize=9)

    if spec.get('point1_label'):
        d = _unit((vx, vy), p1)
        ax.text(p1[0] + d[0] * 0.2, p1[1] + d[1] * 0.2,
                spec['point1_label'], fontsize=9, fontweight='bold',
                ha='center', va='center')
    if spec.get('point2_label'):
        d = _unit((vx, vy), p2)
        ax.text(p2[0] + d[0] * 0.2, p2[1] + d[1] * 0.2,
                spec['point2_label'], fontsize=9, fontweight='bold',
                ha='center', va='center')
    ax.text(vx - 0.18, vy - 0.18, spec.get('vertex', 'O'),
            fontsize=9, fontweight='bold', ha='right', va='top')
    ax.plot(vx, vy, 'ko', markersize=3)
    _auto_bounds(ax, [(vx, vy), p1, p2], pad=0.30)


# ---------------------------------------------------------------------------
# Polygon / Quadrilateral renderer  (AI supplies vertex x/y)
# ---------------------------------------------------------------------------

def _poly_adj(labels: list, coords: dict, label: str) -> tuple:
    """Return (prev_coord, next_coord) for *label* in closed polygon."""
    idx = labels.index(label)
    return (coords[labels[(idx - 1) % len(labels)]],
            coords[labels[(idx + 1) % len(labels)]])


def _poly_right_angle_markers(ax, spec: dict, coords: dict, labels: list) -> list:
    """Draw right-angle squares; return the list of vertices that have them."""
    right_list = spec.get('right_angles_at', [])
    for rlbl in right_list:
        if rlbl in coords:
            size = max(_adj_side_len(coords, rlbl, labels) * 0.08, 0.1)
            p_prev, p_next = _poly_adj(labels, coords, rlbl)
            _right_angle_sq(ax, coords[rlbl], p_prev, p_next, size)
    return right_list


def _poly_angle_labels(ax, spec: dict, coords: dict, labels: list,
                       skip: list) -> None:
    """Draw angle arcs with labels at polygon vertices (skipping *skip*)."""
    for al in spec.get('angle_labels', []):
        v, text = al.get('at'), al.get('label', '')
        if v in coords and text and v not in skip:
            p1, p2 = _poly_adj(labels, coords, v)
            arc_r = max(_adj_side_len(coords, v, labels) * 0.15, 0.15)
            _angle_arc(ax, coords[v], p1, p2, arc_r, text)


def _render_polygon(ax, spec: dict) -> None:
    vdata = spec.get('vertices', [])
    if len(vdata) < 3:
        return

    coords: dict[str, tuple[float, float]] = {
        v['label']: (float(v.get('x', 0)), float(v.get('y', 0)))
        for v in vdata
    }
    labels = [v['label'] for v in vdata]
    pts = [coords[l] for l in labels]

    ax.add_patch(plt.Polygon(pts, closed=True,
                              fill=False, edgecolor='black', linewidth=1.5))

    for diag in spec.get('diagonals', []):
        f, t = diag.get('from'), diag.get('to')
        if f in coords and t in coords:
            ax.plot([coords[f][0], coords[t][0]],
                    [coords[f][1], coords[t][1]], 'k--', lw=0.8)
            if diag.get('label'):
                _segment_label(ax, *coords[f], *coords[t], diag['label'])

    right_list = _poly_right_angle_markers(ax, spec, coords, labels)
    _poly_angle_labels(ax, spec, coords, labels, skip=right_list)

    for side in spec.get('sides', []):
        f, t, text = side.get('from'), side.get('to'), side.get('label', '')
        if f in coords and t in coords and text:
            _segment_label(ax, *coords[f], *coords[t], text)

    for lbl, (px, py) in coords.items():
        _point_dot_label(ax, px, py, lbl, pts)

    _auto_bounds(ax, pts)


def _render_quadrilateral(ax, spec: dict) -> None:
    _render_polygon(ax, spec)


# ---------------------------------------------------------------------------
# Number line renderer
# ---------------------------------------------------------------------------

def _render_number_line(ax, spec: dict) -> None:
    mn = float(spec.get('min', 0))
    mx = float(spec.get('max', 10))
    span = mx - mn or 1.0
    pad = span * 0.12

    ax.annotate('', xy=(mx + pad, 0), xytext=(mn - pad, 0),
                arrowprops={'arrowstyle': '->', 'color': 'black', 'lw': 1.5})

    tick_iv = float(spec.get('tick_interval', 1))
    v = mn
    while v <= mx + 1e-9:
        ax.plot([v, v], [-0.18, 0.18], 'k-', lw=1.0)
        lbl = str(int(v)) if v == int(v) else str(round(v, 2))
        ax.text(v, -0.40, lbl, fontsize=8, ha='center', va='top')
        v = round(v + tick_iv, 10)

    for mp in spec.get('marked_points', []):
        mv = float(mp.get('value', 0))
        mlbl = mp.get('label', '')
        col = mp.get('color', '#1565c0')
        ax.plot(mv, 0, 'o', color=col, markersize=8, zorder=5)
        if mlbl:
            ax.text(mv, 0.42, mlbl, fontsize=9, ha='center', va='bottom',
                    color=col, fontweight='bold')

    seg = spec.get('segment')
    if seg:
        sf = float(seg.get('from', mn))
        st = float(seg.get('to', mx))
        slbl = seg.get('label', '')
        ax.annotate('', xy=(st, 0.65), xytext=(sf, 0.65),
                    arrowprops={'arrowstyle': '<->', 'color': '#c62828', 'lw': 1.2})
        if slbl:
            ax.text((sf + st) / 2, 0.88, slbl, fontsize=8,
                    ha='center', va='bottom', color='#c62828')

    ax.set_xlim(mn - pad * 1.6, mx + pad * 1.6)
    ax.set_ylim(-1.0, 1.5)
    ax.set_aspect('auto')   # override equal-aspect for wide layout


# ---------------------------------------------------------------------------
# Renderer dispatch
# ---------------------------------------------------------------------------

_RENDERERS = {
    'circle':        _render_circle,
    'triangle':      _render_triangle,
    'right_triangle': _render_triangle,   # alias — same renderer, right_angle_at field handles the marker
    'angle':         _render_angle,
    'quadrilateral': _render_quadrilateral,
    'polygon':       _render_polygon,
    'number_line':   _render_number_line,
}
