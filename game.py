import pygame, sys
from numpy import *

rayon    = 10
P        = 10
M        = 14
TABLE_X  = 120
TABLE_Y  = 60
FRICTION = 0.985
ARRET_V  = 0.03

W, H = 1200, 700

SCALE  = 1.0 / 140.0
_ELEV  = radians(28.0)
_AZIM  = radians(-55.0)
_DIST  = 3.8
_FOV   = radians(45.0)

_cam  = None
_V    = None
_FP   = None
_ASPR = None

def update_projection():
    global _cam, _V, _FP, _ASPR
    _cam = array([_DIST * cos(_ELEV) * cos(_AZIM),
                  _DIST * cos(_ELEV) * sin(_AZIM),
                  _DIST * sin(_ELEV)])
    f  = -_cam / linalg.norm(_cam)
    up = array([0.0, 0.0, 1.0])
    r  = cross(f, up); r /= linalg.norm(r)
    u  = cross(r, f)
    M4 = identity(4, dtype=float64)
    M4[0, :3] = r;  M4[0, 3] = -dot(r, _cam)
    M4[1, :3] = u;  M4[1, 3] = -dot(u, _cam)
    M4[2, :3] = -f; M4[2, 3] =  dot(f, _cam)
    _V    = M4
    _FP   = 1.0 / tan(_FOV / 2)
    _ASPR = float(W) / H

update_projection()

def project(wx, wy, wz):
    """Coordonnées monde (unités jeu) → pixels écran. None si derrière la caméra."""
    p = _V @ array([wx * SCALE, wy * SCALE, wz * SCALE, 1.0])
    if p[2] >= -0.001:
        return None
    xn = (_FP / _ASPR) * p[0] / (-p[2])
    yn =  _FP           * p[1] / (-p[2])
    return (int((xn + 1) * 0.5 * W), int((1.0 - (yn + 1) * 0.5) * H))

def mouse_angle(mx, my, cx_cue, cy_cue):
    """Raycasting souris → intersection plan z=rayon → angle_tir."""
    xn = (mx / W) * 2.0 - 1.0
    yn = 1.0 - (my / H) * 2.0
    rc = array([xn * _ASPR / _FP, yn / _FP, -1.0])
    rw = _V[:3, :3].T @ rc
    n  = linalg.norm(rw)
    if n < 1e-10: return None
    rw /= n
    orig = _cam / SCALE
    if abs(rw[2]) < 1e-6: return None
    t = (float(rayon) - orig[2]) / rw[2]
    if t < 0: return None
    return float(arctan2(orig[1] + t * rw[1] - cy_cue,
                         orig[0] + t * rw[0] - cx_cue))

def cam_depth(cx, cy):
    """Distance caméra↔boule (pour le tri z)."""
    return float(linalg.norm(_cam - array([cx * SCALE, cy * SCALE, rayon * SCALE])))

def mat_rot_oz(a):
    return matrix([[cos(a), -sin(a), 0],
                   [sin(a),  cos(a), 0],
                   [0,       0,      1]])

def mat_rot_ox(a):
    return matrix([[1, 0,       0      ],
                   [0, cos(a), -sin(a) ],
                   [0, sin(a),  cos(a) ]])

def mat_rot_oy(a):
    return matrix([[cos(a),  0, -sin(a)],
                   [0,       1,  0     ],
                   [sin(a),  0,  cos(a)]])

pole_Nord = matrix([[0], [0], [rayon]])

def creer_sphere(cx, cy):
    paralleles = []
    for i in range(2 * P + 1):
        par = []
        p0 = mat_rot_oy(i * pi / P) * pole_Nord
        for j in range(M + 1):
            par.append(mat_rot_oz(j * 2 * pi / M) * p0)
        paralleles.append(par)
    for i in range(len(paralleles)):
        for j in range(len(paralleles[0])):
            paralleles[i][j][0, 0] += cx
            paralleles[i][j][1, 0] += cy
            paralleles[i][j][2, 0] += rayon
    return paralleles

def translater_mesh(paralleles, dx, dy):
    for i in range(len(paralleles)):
        for j in range(len(paralleles[0])):
            paralleles[i][j][0, 0] += dx
            paralleles[i][j][1, 0] += dy

def rouler(paralleles, cx, cy, vx, vy):
    for i in range(len(paralleles)):
        for j in range(len(paralleles[0])):
            paralleles[i][j][0, 0] -= cx
            paralleles[i][j][1, 0] -= cy
            paralleles[i][j][2, 0] -= rayon
            paralleles[i][j] = mat_rot_oy(-vx / rayon) * paralleles[i][j]
            paralleles[i][j][0, 0] += cx + vx
            paralleles[i][j][1, 0] += cy
            paralleles[i][j][2, 0] += rayon
    for i in range(len(paralleles)):
        for j in range(len(paralleles[0])):
            paralleles[i][j][0, 0] -= cx + vx
            paralleles[i][j][1, 0] -= cy
            paralleles[i][j][2, 0] -= rayon
            paralleles[i][j] = mat_rot_ox(-vy / rayon) * paralleles[i][j]
            paralleles[i][j][0, 0] += cx + vx
            paralleles[i][j][1, 0] += cy + vy
            paralleles[i][j][2, 0] += rayon

def resoudre_collision(cxA, cyA, vxA, vyA, parA,
                       cxB, cyB, vxB, vyB, parB):
    dx   = cxB - cxA
    dy   = cyB - cyA
    dist = float(sqrt(dx**2 + dy**2))
    if dist >= 2 * rayon or dist == 0:
        return cxA, cyA, vxA, vyA, cxB, cyB, vxB, vyB, False
    nx, ny = dx / dist, dy / dist
    dv = (vxA - vxB) * nx + (vyA - vyB) * ny
    if dv > 0:
        vxA -= dv * nx;  vyA -= dv * ny
        vxB += dv * nx;  vyB += dv * ny
    sep = (2 * rayon - dist) / 2
    cxA -= sep * nx;  cyA -= sep * ny
    cxB += sep * nx;  cyB += sep * ny
    translater_mesh(parA, -sep * nx, -sep * ny)
    translater_mesh(parB,  sep * nx,  sep * ny)
    return cxA, cyA, vxA, vyA, cxB, cyB, vxB, vyB, True

def rebond_bandes(cx, cy, vx, vy, par):
    """Rebond sur les bandes : inverse la vitesse et replace la boule dans la table
    (une collision peut l'avoir poussée dans la bande)."""
    nx = float(clip(cx, -TABLE_X + rayon, TABLE_X - rayon))
    ny = float(clip(cy, -TABLE_Y + rayon, TABLE_Y - rayon))
    if nx == cx and ny == cy:
        return cx, cy, vx, vy
    if nx != cx:
        vx = float(abs(vx)) if nx > cx else -float(abs(vx))
    if ny != cy:
        vy = float(abs(vy)) if ny > cy else -float(abs(vy))
    translater_mesh(par, nx - cx, ny - cy)
    return nx, ny, vx, vy

def _proj_poly(pts_3d):
    return [p for p in (project(x, y, z) for x, y, z in pts_3d) if p]

def build_bg():
    """Pré-rend la table (statique) sur un Surface."""
    surf = pygame.Surface((W, H))
    surf.fill((13, 13, 13))

    RW, FT = 10, 18
    RX, RY = TABLE_X + RW, TABLE_Y + RW
    FX, FY = RX + FT, RY + FT

    fc = _proj_poly([(-TABLE_X, -TABLE_Y, 0), ( TABLE_X, -TABLE_Y, 0),
                     ( TABLE_X,  TABLE_Y, 0), (-TABLE_X,  TABLE_Y, 0)])
    if len(fc) == 4:
        pygame.draw.polygon(surf, (29, 92, 29), fc)

    for corners in [
        [(-TABLE_X, -TABLE_Y, 0), ( TABLE_X, -TABLE_Y, 0),
         ( TABLE_X, -TABLE_Y, 6), (-TABLE_X, -TABLE_Y, 6)],
        [(-TABLE_X, -TABLE_Y, 0), (-TABLE_X,  TABLE_Y, 0),
         (-TABLE_X,  TABLE_Y, 6), (-TABLE_X, -TABLE_Y, 6)],
        [( TABLE_X, -TABLE_Y, 0), ( TABLE_X,  TABLE_Y, 0),
         ( TABLE_X,  TABLE_Y, 6), ( TABLE_X, -TABLE_Y, 6)],
    ]:
        pts = _proj_poly(corners)
        if len(pts) >= 3:
            pygame.draw.polygon(surf, (90, 45, 0), pts)

    for corners in [
        [(-TABLE_X, -RY, 6), ( TABLE_X, -RY, 6),
         ( TABLE_X, -TABLE_Y, 6), (-TABLE_X, -TABLE_Y, 6)],
        [(-TABLE_X,  TABLE_Y, 6), ( TABLE_X,  TABLE_Y, 6),
         ( TABLE_X,  RY, 6), (-TABLE_X,  RY, 6)],
        [(-RX, -RY, 6), (-TABLE_X, -RY, 6),
         (-TABLE_X,  RY, 6), (-RX,  RY, 6)],
        [( TABLE_X, -RY, 6), ( RX, -RY, 6),
         ( RX,  RY, 6), ( TABLE_X,  RY, 6)],
    ]:
        pts = _proj_poly(corners)
        if len(pts) >= 3:
            pygame.draw.polygon(surf, (122, 61, 0), pts)

    for corners in [
        [(-RX, -FY, FT), ( RX, -FY, FT), ( RX, -RY, FT), (-RX, -RY, FT)],
        [(-RX,  RY, FT), ( RX,  RY, FT), ( RX,  FY, FT), (-RX,  FY, FT)],
        [(-FX, -FY, FT), (-RX, -FY, FT), (-RX,  FY, FT), (-FX,  FY, FT)],
        [( RX, -FY, FT), ( FX, -FY, FT), ( FX,  FY, FT), ( RX,  FY, FT)],
    ]:
        pts = _proj_poly(corners)
        if len(pts) >= 3:
            pygame.draw.polygon(surf, (61, 30, 0), pts)

    pa = project(0, -TABLE_Y + 2, 0.5)
    pb = project(0,  TABLE_Y - 2, 0.5)
    if pa and pb:
        pygame.draw.line(surf, (55, 110, 55), pa, pb, 1)

    for sx in [-TABLE_X * 0.5, 0.0, TABLE_X * 0.5]:
        p = project(sx, 0.0, 0.5)
        if p:
            pygame.draw.circle(surf, (70, 130, 70), p, 4)

    return surf

def dessiner_sphere(surf, paralleles, c_haut, c_bas, c_mer):
    for k, par in enumerate(paralleles):
        pts = [project(float(q[0, 0]), float(q[1, 0]), float(q[2, 0])) for q in par]
        col = c_haut if k <= P else c_bas
        for i in range(len(pts) - 1):
            if pts[i] and pts[i + 1]:
                pygame.draw.line(surf, col, pts[i], pts[i + 1], 1)
    for i in range(M + 1):
        pts = [project(float(par[i][0, 0]), float(par[i][1, 0]), float(par[i][2, 0]))
               for par in paralleles]
        for j in range(len(pts) - 1):
            if pts[j] and pts[j + 1]:
                pygame.draw.line(surf, c_mer, pts[j], pts[j + 1], 1)

def dessiner_ombre(surf, cx, cy):
    pts = []
    for t in linspace(0, 2 * pi, 24, endpoint=False):
        p = project(cx + rayon * 0.85 * cos(t),
                    cy + rayon * 0.55 * sin(t), 0.3)
        if p:
            pts.append(p)
    if len(pts) >= 3:
        pygame.draw.polygon(surf, (15, 46, 15), pts)

def dessiner_viseur(surf, cx_v, cy_v, angle, puis):
    DASH, GAP = 7, 4
    longueur  = puis * 6
    ca = float(cos(angle))
    sa = float(sin(angle))
    d  = 0.0
    while d < longueur:
        d2 = d + DASH if d + DASH < longueur else longueur
        p1 = project(cx_v + d  * ca, cy_v + d  * sa, rayon)
        p2 = project(cx_v + d2 * ca, cy_v + d2 * sa, rayon)
        if p1 and p2:
            pygame.draw.line(surf, (255, 221, 0), p1, p2, 1)
        d += DASH + GAP
    for k in range(1, 6):
        t = k / 6.0
        p = project(cx_v + t * longueur * ca, cy_v + t * longueur * sa, rayon)
        if p:
            pygame.draw.circle(surf, (255, 221, 0), p, 5 - k if 5 - k > 1 else 1)

def draw_hud(surf):
    s = font_big.render(f'J1 : {scores[0]}   |   J2 : {scores[1]}', True, (255, 255, 255))
    surf.blit(s, (W // 2 - s.get_width() // 2, 12))

    nom = 'Blanc' if joueur == 1 else 'Jaune'
    col = (245, 240, 224) if joueur == 1 else (255, 215, 0)
    t   = font_med.render(f'\u25cf Tour : Joueur {joueur}  ({nom})', True, col)
    surf.blit(t, (W // 2 - t.get_width() // 2, 40))

    if mode == 'ATTENTE':
        bw, bh = 240, 14
        bx, by = W // 2 - bw // 2, H - 62
        pygame.draw.rect(surf, (50, 50, 50), (bx, by, bw, bh), 0, 4)
        fw = int(puissance_tir / 20 * bw)
        pygame.draw.rect(surf, (255, 221, 0), (bx, by, fw, bh), 0, 4)
        lbl = font_sm.render(f'Force  {puissance_tir:.0f} / 20', True, (255, 221, 0))
        surf.blit(lbl, (W // 2 - lbl.get_width() // 2, H - 44))
        instr = font_sm.render('Souris : Viser   |   \u2191\u2193 : Force   |   Clic : Tirer   |   Molette : Zoom',
                               True, (85, 85, 85))
        surf.blit(instr, (W // 2 - instr.get_width() // 2, H - 24))
    else:
        instr = font_sm.render('En jeu\u2026', True, (85, 85, 85))
        surf.blit(instr, (W // 2 - instr.get_width() // 2, H - 24))

    now = pygame.time.get_ticks()
    if flash_text and now < flash_until:
        fm = font_big.render(flash_text, True, (255, 221, 0))
        surf.blit(fm, (W // 2 - fm.get_width() // 2, H // 2 - 40))

mode            = 'ATTENTE'
joueur          = 1
scores          = [0, 0]
boules_touchees = set()
col_12 = col_13 = col_23 = False

angle_tir     = 0.0
puissance_tir = 8.0

cx1, cy1 = -50.0,  10.0
cx2, cy2 =  50.0, -10.0
cx3, cy3 =   5.0,  20.0
vx1 = vy1 = vx2 = vy2 = vx3 = vy3 = 0.0

paralleles1 = creer_sphere(cx1, cy1)
paralleles2 = creer_sphere(cx2, cy2)
paralleles3 = creer_sphere(cx3, cy3)

flash_text  = ''
flash_until = 0

def on_key(event):
    global puissance_tir
    if mode != 'ATTENTE':
        return
    if event.key == pygame.K_UP:
        if puissance_tir < 20.0: puissance_tir += 1.0
    elif event.key == pygame.K_DOWN:
        if puissance_tir > 2.0:  puissance_tir -= 1.0

def on_click(button, mx, my):
    global mode, vx1, vy1, vx2, vy2, boules_touchees, col_12, col_13, col_23, angle_tir
    if button != 1 or mode != 'ATTENTE':
        return
    cx_cue = cx1 if joueur == 1 else cx2
    cy_cue = cy1 if joueur == 1 else cy2
    a = mouse_angle(mx, my, cx_cue, cy_cue)
    if a is not None:
        angle_tir = a
    vx_s = float(puissance_tir * cos(angle_tir))
    vy_s = float(puissance_tir * sin(angle_tir))
    boules_touchees = set()
    col_12 = col_13 = col_23 = False
    if joueur == 1:
        vx1, vy1 = vx_s, vy_s
    else:
        vx2, vy2 = vx_s, vy_s
    mode = 'EN_JEU'

def update_aim(mx, my):
    global angle_tir
    if mode != 'ATTENTE':
        return
    cx_cue = cx1 if joueur == 1 else cx2
    cy_cue = cy1 if joueur == 1 else cy2
    a = mouse_angle(mx, my, cx_cue, cy_cue)
    if a is not None:
        angle_tir = a

def fin_tour():
    global joueur, scores, boules_touchees, mode, flash_text, flash_until
    if len(boules_touchees) == 2:
        scores[joueur - 1] += 1
        flash_text  = 'Carambole ! +1 point — rejoue'
        flash_until = pygame.time.get_ticks() + 1800
    else:
        joueur = 2 if joueur == 1 else 1
    boules_touchees = set()
    mode = 'ATTENTE'

pygame.init()
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption('Billard 3D')
clock = pygame.time.Clock()

font_big = pygame.font.SysFont('monospace', 20, bold=True)
font_med = pygame.font.SysFont('monospace', 16)
font_sm  = pygame.font.SysFont('monospace', 13)

bg_surf = build_bg()

while True:
    mx, my = pygame.mouse.get_pos()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN:
            on_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            on_click(event.button, event.pos[0], event.pos[1])
        elif event.type == pygame.WINDOWRESIZED:
            W, H = event.x, event.y
            update_projection()
            bg_surf = build_bg()
        elif event.type == pygame.MOUSEWHEEL:
            _DIST = float(clip(_DIST - event.y * 0.25, 1.5, 10.0))
            update_projection()
            bg_surf = build_bg()

    update_aim(mx, my)

    if mode == 'EN_JEU':
        vx1 *= FRICTION;  vy1 *= FRICTION
        vx2 *= FRICTION;  vy2 *= FRICTION
        vx3 *= FRICTION;  vy3 *= FRICTION
        if sqrt(vx1**2 + vy1**2) < ARRET_V: vx1 = vy1 = 0.0
        if sqrt(vx2**2 + vy2**2) < ARRET_V: vx2 = vy2 = 0.0
        if sqrt(vx3**2 + vy3**2) < ARRET_V: vx3 = vy3 = 0.0
        if vx1 == vy1 == vx2 == vy2 == vx3 == vy3 == 0.0:
            fin_tour()

    cx1, cy1, vx1, vy1, cx2, cy2, vx2, vy2, t12 = resoudre_collision(
        cx1, cy1, vx1, vy1, paralleles1, cx2, cy2, vx2, vy2, paralleles2)
    cx1, cy1, vx1, vy1, cx3, cy3, vx3, vy3, t13 = resoudre_collision(
        cx1, cy1, vx1, vy1, paralleles1, cx3, cy3, vx3, vy3, paralleles3)
    cx2, cy2, vx2, vy2, cx3, cy3, vx3, vy3, t23 = resoudre_collision(
        cx2, cy2, vx2, vy2, paralleles2, cx3, cy3, vx3, vy3, paralleles3)

    if mode == 'EN_JEU':
        if joueur == 1:
            if t12 and not col_12: boules_touchees.add(2)
            if t13 and not col_13: boules_touchees.add(3)
        else:
            if t12 and not col_12: boules_touchees.add(1)
            if t23 and not col_23: boules_touchees.add(3)
    col_12 = t12;  col_13 = t13;  col_23 = t23

    if vx1 != 0.0 or vy1 != 0.0:
        rouler(paralleles1, cx1, cy1, vx1, vy1)
        cx1 += vx1;  cy1 += vy1
    if vx2 != 0.0 or vy2 != 0.0:
        rouler(paralleles2, cx2, cy2, vx2, vy2)
        cx2 += vx2;  cy2 += vy2
    if vx3 != 0.0 or vy3 != 0.0:
        rouler(paralleles3, cx3, cy3, vx3, vy3)
        cx3 += vx3;  cy3 += vy3

    cx1, cy1, vx1, vy1 = rebond_bandes(cx1, cy1, vx1, vy1, paralleles1)
    cx2, cy2, vx2, vy2 = rebond_bandes(cx2, cy2, vx2, vy2, paralleles2)
    cx3, cy3, vx3, vy3 = rebond_bandes(cx3, cy3, vx3, vy3, paralleles3)

    screen.blit(bg_surf, (0, 0))

    dessiner_ombre(screen, cx1, cy1)
    dessiner_ombre(screen, cx2, cy2)
    dessiner_ombre(screen, cx3, cy3)

    if mode == 'ATTENTE':
        cx_v = cx1 if joueur == 1 else cx2
        cy_v = cy1 if joueur == 1 else cy2
        dessiner_viseur(screen, cx_v, cy_v, angle_tir, puissance_tir)

    boules = [
        (cam_depth(cx1, cy1), paralleles1, (245, 240, 224), (176, 168, 130), (200, 192, 160)),
        (cam_depth(cx2, cy2), paralleles2, (255, 215,   0), (170, 136,   0), (221, 187,   0)),
        (cam_depth(cx3, cy3), paralleles3, (221,  34,   0), (136,  20,   0), (187,  24,   0)),
    ]
    for _, par, ch, cb, cm in sorted(boules, key=lambda x: -x[0]):
        dessiner_sphere(screen, par, ch, cb, cm)

    draw_hud(screen)

    pygame.display.flip()
    clock.tick(60)