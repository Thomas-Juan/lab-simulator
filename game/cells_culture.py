# -*- coding: utf-8 -*-
"""Cell culture and aseptic technique."""
import math
import random
import pygame
import audio
import gfx
import render as R
import real
from stage import Stage, register, TOP, BOTTOM
from core import (W, H, INK, INK_SOFT, MUTED, CARD, SAND, PEACH, CORAL, CORAL_D, SKY, TURQ, LAV, VIOLET, NIGHT,
                  WHITE, GREEN, RED, YELLOW, clamp, mix, draw_text, draw_wrapped)
from cells_common import ell_pts, scope_mask, scope_card, field_bg, adherent, rounded, masked_field, PHASE_BG

MEDIUM = (236, 120, 130)      # phenol red at pH 7.4
ACID = (232, 196, 90)         # phenol red turns yellow when acidic


@register("culture_hood")
class CultureHood(Stage):
    title = "Keep it sterile"
    instr = ("Microbes drift into the hood from the room. Click them to spray 70 % ethanol before they reach "
             "the open flask. Don't put your hands on the front grille: blocking it breaks the air curtain. "
             "Spraying at nothing disturbs the airflow too.")
    limit = 30

    def setup(self):
        self.mouth = (604, 336)
        self.grille = pygame.Rect(40, 432, 880, 24)
        self.mic = []
        self.next_spawn = 40
        self.zapped = self.contam = self.blocks = self.caught = self.spawned = 0
        self.spd = self.lv(0.75, 1.0, 1.3)
        self.reach = self.lv(60, 52, 44)
        self.curtain_p = self.lv(0.7, 0.55, 0.4)
        self.penalty = self.lv(20, 25, 30)
        self.wasted = 0
        self.free_sprays = self.lv(14, 10, 7)
        self.block_t = 0
        self.cloud = 0.0
        self.sprays = []
        self.hint = "Click microbes to spray them. Keep your hands off the front grille."

    def spawn(self):
        side = self.rng.random()
        if side < 0.6:
            x, y = self.rng.uniform(60, W - 60), H + 10
        elif side < 0.8:
            x, y = -10, self.rng.uniform(300, 520)
        else:
            x, y = W + 10, self.rng.uniform(300, 520)
        kind = self.rng.choice(["rod", "rod", "cocci", "spore"])
        prog = self.t / (60.0 * self.limit)
        # on the Expert bench a mould spore sometimes arrives as a puff of three
        n = 3 if (kind == "spore" and self.level == 2 and self.rng.random() < 0.5) else 1
        for k in range(n):
            self.spawned += 1
            self.mic.append({"x": x + k * 16, "y": y + k * 10, "k": kind,
                             "sp": self.rng.uniform(0.8, 1.2) * (0.9 + 0.9 * prog) * self.spd,
                             "ph": self.rng.uniform(0, 6.3), "curtain": None, "ang": self.rng.uniform(0, 6.3)})

    def tick(self, inp):
        if self.left() <= 0.05:
            extra = max(0, self.wasted - self.free_sprays)
            sc = 100 - self.penalty * self.contam - 10 * self.blocks - 3 * extra
            self.ctx.culture_contam = self.contam
            fb = ["The flask stayed clean." if not self.contam else
                  "%d microbe%s reached the flask: the medium would turn cloudy and yellow within days." % (self.contam, "s" if self.contam > 1 else ""),
                  "You sprayed %d, the air curtain caught %d, %d got through." % (self.zapped, self.caught, self.contam)]
            if self.blocks:
                fb.append("Blocking the front grille breaks the air curtain that keeps room air away from the work.")
            if extra:
                fb.append("%d sprays hit nothing. Constant spraying and arm movement disturb the downflow." % self.wasted)
            audio.sfx("good" if sc >= 75 else "bad")
            self.finish(sc, *fb)
            return
        if self.block_t:
            self.block_t -= 1
        self.next_spawn -= 1
        if self.next_spawn <= 0:
            self.spawn()
            prog = self.t / (60.0 * self.limit)
            self.next_spawn = int((55 - 32 * prog) / self.spd + self.rng.randint(-8, 8))
        mx, my = self.mouth
        for m in self.mic:
            dx, dy = mx - m["x"], my - m["y"]
            d = math.hypot(dx, dy) or 1
            m["ph"] += 0.08
            m["x"] += dx / d * m["sp"] + math.sin(m["ph"]) * 0.6
            m["y"] += dy / d * m["sp"] + math.cos(m["ph"] * 0.7) * 0.4
            m["ang"] += 0.03
            if m["curtain"] is None and self.grille.collidepoint(m["x"], m["y"]):
                m["curtain"] = (not self.block_t) and self.rng.random() < self.curtain_p
                if m["curtain"]:
                    self.caught += 1
            if m["curtain"] and m["y"] < self.grille.bottom + 4:
                m["y"] += 6           # pulled down into the grille by the inflow
                m["sp"] = 0
                if m["y"] > self.grille.bottom:
                    m["dead"] = True
            if d < 18:
                m["dead"] = True
                self.contam += 1
                self.cloud = min(1.0, self.cloud + 0.3)
                self.shake = 18
                audio.sfx("buzz")
                self.floaters.add(mx, my - 40, "Contaminated!", RED, 22)
        self.mic = [m for m in self.mic if not m.get("dead")]
        for sp in self.sprays:
            sp[2] -= 1
        self.sprays = [sp for sp in self.sprays if sp[2] > 0]
        if inp.click:
            x, y = inp.mouse
            near = any(math.hypot(m["x"] - x, m["y"] - y) < self.reach for m in self.mic)
            if self.grille.collidepoint(x, y) and not near:
                self.blocks += 1
                self.block_t = 150
                self.shake = 8
                audio.sfx("bad")
                self.floaters.add(x, y - 30, "Grille blocked!", RED, 20)
                return
            self.sprays.append([x, y, 24])
            audio.sfx("whoosh")
            hit = [m for m in self.mic if math.hypot(m["x"] - x, m["y"] - y) < self.reach]
            for m in hit:
                m["dead"] = True
            if not hit:
                self.wasted += 1
                if self.wasted > self.free_sprays:
                    self.floaters.add(x, y - 20, "wasted spray", MUTED, 14)
            if hit:
                self.zapped += len(hit)
                self.particles.burst(x, y, 10, cols=(SKY, WHITE, TURQ), speed=3)
                self.floaters.add(x, y - 20, "+%d" % len(hit), GREEN, 20)
            self.mic = [m for m in self.mic if not m.get("dead")]

    def partial(self):
        self.ctx.culture_contam = self.contam
        return max(0, 100 - self.penalty * self.contam - 10 * self.blocks - 3 * max(0, self.wasted - self.free_sprays))

    def autoplay(self):
        self.ctx.culture_contam = 0
        self.finish(95, "The flask stayed clean.")

    def draw_microbe(self, s, m):
        """Airborne microbes, drawn magnified and soft-shaded (a game convention: in reality they are invisible)."""
        x, y = m["x"], m["y"]
        gfx.alpha_circle(s, (255, 255, 255), (x, y), 15, 46)
        if m["k"] == "rod":          # rod-shaped bacterium with a flagellum
            ca, sa = math.cos(m["ang"]), math.sin(m["ang"])
            tail = [(x - ca * (10 + k * 3) + math.sin(m["ph"] * 2 + k) * 2.5 * -sa, y - sa * (10 + k * 3) + math.sin(m["ph"] * 2 + k) * 2.5 * ca) for k in range(5)]
            pygame.draw.aalines(s, (96, 120, 84), False, tail)
            pts = ell_pts(x, y, 10, 4.5, m["ang"], 18)
            R.aa_poly(s, (150, 196, 120), pts, 1, (70, 110, 60))
            gfx.line(s, (214, 240, 196), (x - ca * 5 - sa * 1.4, y - sa * 5 + ca * 1.4), (x + ca * 4 - sa * 1.4, y + sa * 4 + ca * 1.4), 2)
        elif m["k"] == "cocci":      # a grape-like cluster of cocci
            for i in range(5):
                a = m["ang"] + i * 1.3
                gfx.circle(s, (196, 160, 214), (x + math.cos(a) * 5, y + math.sin(a) * 5), 4.5, 1, (120, 90, 140))
        else:                        # mould spore with sprouting hyphae
            for i in range(7):
                a = m["ang"] + i * math.tau / 7
                gfx.line(s, (128, 140, 100), (x, y), (x + math.cos(a) * 13, y + math.sin(a) * 13), 1)
            gfx.circle(s, (184, 196, 140), (x, y), 6.5, 1, (110, 120, 80))

    def render(self, s):
        s.blit(_hood_bg(), (0, 0))
        # downflow of filtered air: faint streaks under the light panel
        for i, x in enumerate(range(170, 820, 92)):
            yy = TOP + 60 + (self.t * 1.4 + i * 37) % 130
            gfx.alpha_rect(s, (x - 1, yy, 2, 30), (255, 255, 255), 55, 1)
        if self.block_t:
            gfx.alpha_rect(s, self.grille.inflate(4, 4), (230, 90, 70), 110, 6)
            gfx.tag(s, self.grille.centerx, self.grille.y - 30, "air curtain broken", (250, 210, 200), 13, center=True)
        # T75 flask lying on the steel, cap off, with its reflection in the steel
        med = mix(MEDIUM, ACID, self.cloud)
        fl = _flask_sprite(med, int(self.cloud * 4))
        s.blit(_flask_reflection(med, int(self.cloud * 4)), (372, 288 + 96 - 6))
        sh = real.contact_shadow(210, 12, 90)
        s.blit(sh, (392 - 12, 372 - 6))
        s.blit(fl, (372, 288))
        s.blit(_cap_sprite(), (632, 350))
        for m in self.mic:
            self.draw_microbe(s, m)
        for x, y, life in self.sprays:       # ethanol mist spreading out
            k = 1 - life / 24.0
            for j in range(7):
                a = j * 0.9 + x * 0.01
                gfx.alpha_circle(s, (226, 240, 246), (x + math.cos(a) * 28 * k, y + math.sin(a) * 28 * k),
                                 int((8 + 28 * k) / 4) * 4, int(life * 3.5) // 12 * 12)
        s.blit(_sash(), (0, 0))
        gfx.tag(s, 40, H - 66, "Sprayed: %d" % self.zapped, (220, 236, 226), 15)
        gfx.tag(s, 170, H - 66, "Contaminations: %d" % self.contam, (250, 220, 212) if self.contam else CARD, 15)


_HOOD = {}


def _persp(img, src, quad):
    """Blit a rectangular texture `src` into the quadrilateral `quad` (approximate: masks a
    stretched copy), used for the steel walls and floor of the cabinet."""
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    box = pygame.Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
    tex = pygame.transform.smoothscale(src, box.size)
    m = pygame.Surface(box.size, pygame.SRCALPHA)
    R.aa_poly(m, (255, 255, 255), [(x - box.x, y - box.y) for x, y in quad], 0, None)
    t2 = pygame.Surface(box.size, pygame.SRCALPHA)
    t2.blit(tex, (0, 0))
    t2.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    img.blit(t2, box.topleft)


def _hood_bg():
    """A class II biosafety cabinet seen from the operator's chair: light panel above, perforated
    stainless back wall, side walls and work surface in brushed steel, the front grille and the
    white painted cabinet front below."""
    if "bg" in _HOOD:
        return _HOOD["bg"]
    b = pygame.Surface((W, H))
    gfx.bench(b, (200, 210, 214))
    o = pygame.Rect(30, TOP + 2, W - 60, 434 - TOP - 2)            # front opening
    back = pygame.Rect(150, TOP + 56, W - 300, 146)                 # back wall
    floor_y = o.bottom
    # white powder-coated cabinet body around the opening
    gfx.plastic_rect(b, (10, TOP - 12, W - 20, H - TOP + 30), (238, 238, 234), 14, 0.15)
    # light panel (ceiling) glowing, then the side walls in steel
    ceil = [o.topleft, o.topright, back.topright, back.topleft]
    lp = pygame.Surface((o.w, back.y - o.y))
    lp.blit(R.vgrad(lp.get_size(), (252, 252, 248), (226, 230, 232)), (0, 0))
    _persp(b, lp, ceil)
    steel_l = real.steel(200, 300, 0, (176, 182, 188))
    steel_r = real.steel(200, 300, 0, (156, 162, 170))
    _persp(b, steel_l, [o.topleft, back.topleft, back.bottomleft, (o.x, floor_y)])
    _persp(b, steel_r, [o.topright, back.topright, back.bottomright, (o.right, floor_y)])
    # perforated back wall
    b.blit(real.steel(back.w, back.h, 0, (200, 205, 210)), back.topleft)
    for yy in range(back.y + 10, back.bottom - 4, 11):
        for xx in range(back.x + 10 + (yy // 11 % 2) * 5, back.right - 6, 11):
            pygame.draw.circle(b, (110, 116, 124), (xx, yy), 2)
            pygame.draw.circle(b, (236, 238, 240), (xx - 1, yy - 1), 1)
    # work surface: brighter steel, lit from above, with a soft light pool
    surf = [back.bottomleft, back.bottomright, (o.right, floor_y), (o.x, floor_y)]
    _persp(b, real.steel(400, 160, 0, (214, 218, 222)), surf)
    b.blit(R.soft_shadow(440, 110, 55, (255, 255, 255), 34, 24), (260 - 48, back.bottom + 40 - 48))
    # edges where the panels meet (thin, darker metal, no ink)
    for a, c in ((o.topleft, back.topleft), (o.topright, back.topright), ((o.x, floor_y), back.bottomleft), ((o.right, floor_y), back.bottomright)):
        gfx.line(b, (120, 126, 134), a, c, 2)
    gfx.rrect(b, back, None, (120, 126, 134), 1, 0)
    pygame.draw.line(b, (110, 116, 124), back.bottomleft, back.bottomright, 2)
    # 70 % ethanol spray bottle at the back left
    _spray_bottle(b, 190, 184)
    # front grille: perforated stainless strip sloping down to the operator
    g = pygame.Rect(40, 432, 880, 24)
    b.blit(real.steel(g.w, g.h, 3, (150, 156, 164)), g.topleft)
    for x in range(g.x + 6, g.right - 2, 9):
        for yy in (g.y + 7, g.y + 16):
            R.gd.filled_circle(b, x, yy, 2, (36, 38, 44))
    # cabinet front panel and a control strip
    front = pygame.Rect(30, g.bottom + 2, W - 60, H - g.bottom - 2)
    b.blit(R.vgrad(front.size, (230, 230, 226), (196, 196, 192)), front.topleft)
    gfx.screen_rect(b, (W - 260, front.y + 14, 120, 28), (20, 40, 34), 4)
    draw_text(b, "0.45 m/s", (W - 200, front.y + 21), 13, (120, 240, 160), center=True, bold=True, mono=True)
    gfx.led(b, (W - 110, front.y + 28), GREEN, True, 5)
    gfx.led(b, (W - 86, front.y + 28), (240, 180, 60), False, 5)
    _HOOD["bg"] = b
    return b


def _spray_bottle(b, x, y):
    body = pygame.Rect(x, y + 18, 32, 54)
    m = pygame.Surface(body.size, pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=8)
    b.blit(real.shaded_mask(m, (236, 238, 236), real.cyl_profile(body.w)), body.topleft)
    b.blit(real.soft_edge(m, (150, 154, 156), 1), body.topleft)
    lab = pygame.Rect(x + 4, y + 34, 24, 22)
    pygame.draw.rect(b, (250, 250, 246), lab)
    draw_text(b, "70%", (lab.centerx, lab.y + 2), 10, (40, 80, 160), center=True, bold=True)
    draw_text(b, "EtOH", (lab.centerx, lab.y + 11), 9, (60, 60, 70), center=True, bold=True)
    head = pygame.Rect(x + 6, y, 20, 20)
    hm = pygame.Surface(head.size, pygame.SRCALPHA)
    pygame.draw.rect(hm, (255, 255, 255, 255), hm.get_rect(), border_radius=4)
    b.blit(real.shaded_mask(hm, (50, 110, 190), real.cyl_profile(head.w)), head.topleft)
    pygame.draw.rect(b, (40, 90, 160), (x + 24, y + 4, 12, 5), border_radius=2)


def _sash():
    """The raised glass sash across the top of the opening, with its aluminium frame bar."""
    if "sash" in _HOOD:
        return _HOOD["sash"]
    sf = pygame.Surface((W, H), pygame.SRCALPHA)
    gl = pygame.Rect(30, TOP + 2, W - 60, 118)
    sf.blit(real.glass(gl.w, gl.h, (210, 232, 238), 46, 0), gl.topleft)
    for i in range(3):
        x = 140 + i * 300
        pygame.draw.polygon(sf, (255, 255, 255, 46), [(x, gl.bottom - 4), (x + 34, gl.bottom - 4), (x + 114, gl.y + 4), (x + 80, gl.y + 4)])
        pygame.draw.polygon(sf, (255, 255, 255, 26), [(x + 42, gl.bottom - 4), (x + 50, gl.bottom - 4), (x + 130, gl.y + 4), (x + 122, gl.y + 4)])
    bar = pygame.Rect(26, gl.bottom - 2, W - 52, 14)
    sf.blit(real.steel(bar.w, bar.h, 4, (196, 200, 206)), bar.topleft)
    lab = pygame.Rect(W // 2 - 70, gl.y + 8, 140, 18)
    pygame.draw.rect(sf, (250, 250, 246, 230), lab, border_radius=2)
    draw_text(sf, "CLASS II  ·  HEPA", lab.center, 10, (60, 60, 70), center=True, bold=True, vcenter=True)
    _HOOD["sash"] = sf
    return sf


_FLASK = {}


def _flask_sprite(med, cloud):
    """Vented T75 flask lying flat, seen from the side: clear polystyrene body, canted neck
    (cap removed), pink DMEM, a printed writing area. No ink lines: edges from shading."""
    key = (med, cloud)
    if key in _FLASK:
        return _FLASK[key]
    sf = pygame.Surface((240, 96), pygame.SRCALPHA)
    body = pygame.Rect(8, 10, 190, 78)
    neck = [(196, 32), (230, 38), (230, 60), (196, 68)]
    R.aa_poly(sf, (222, 232, 236, 120), neck, 0, None)
    sf.blit(real.glass(body.w, body.h, (222, 232, 236), 60, 8), body.topleft)
    liq = pygame.Rect(body.x + 3, body.y + 40, body.w - 6, body.h - 43)
    tex = gfx.texture(liq.w, liq.h, med, 16, 5, 81, 2)
    m = R.rrect_surf(liq.w, liq.h, (255, 255, 255, 215), None, 0, 6, 0, False)
    t2 = pygame.Surface(liq.size, pygame.SRCALPHA)
    t2.blit(tex, (0, 0))
    t2.blit(R.vgrad(liq.size, (255, 255, 255), (200, 200, 200)), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    t2.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    sf.blit(t2, liq.topleft)
    pygame.draw.line(sf, R.lighten(med, 0.45) + (220,), (liq.x + 2, liq.y), (liq.right - 3, liq.y), 2)
    if cloud:
        rnd = random.Random(cloud)
        gfx.alpha_rect(sf, liq, (250, 248, 232), 36 * cloud, 6)
        for _ in range(14 * cloud):
            gfx.alpha_circle(sf, (250, 250, 230), (rnd.uniform(liq.x + 4, liq.right - 4), rnd.uniform(liq.y + 4, liq.bottom - 4)), 2.5, 110)
    for i in range(1, 6):                    # moulded graduation marks
        x = body.x + 22 + i * 26
        pygame.draw.line(sf, (160, 170, 176, 180), (x, body.y + 6), (x, body.y + 13), 1)
    wa = pygame.Rect(body.x + 18, body.y + 18, 76, 15)        # frosted writing area with a marker label
    pygame.draw.rect(sf, (246, 248, 246, 220), wa, border_radius=2)
    draw_text(sf, "HeLa p12", (wa.centerx, wa.y + 1), 10, (40, 50, 120), center=True, bold=True)
    pygame.draw.line(sf, (255, 255, 255, 200), (body.x + 6, body.y + 4), (body.right - 10, body.y + 4), 2)
    pygame.draw.line(sf, (255, 255, 255, 160), (200, 38), (226, 43), 2)
    pygame.draw.ellipse(sf, (190, 200, 206, 200), (224, 39, 12, 20), 2)        # open neck
    _FLASK[key] = sf
    return sf


def _flask_reflection(med, cloud):
    key = ("refl", med, cloud)
    if key not in _FLASK:
        fl = _flask_sprite(med, cloud)
        rf = pygame.transform.flip(fl, False, True).copy()
        fade = R.vgrad(rf.get_size(), (90, 90, 90), (0, 0, 0))
        mask = pygame.Surface(rf.get_size(), pygame.SRCALPHA)
        mask.blit(fade, (0, 0))
        a = pygame.Surface(rf.get_size(), pygame.SRCALPHA)
        a.fill((255, 255, 255, 255))
        rf.blit(a, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        rf.set_alpha(60)
        sq = pygame.transform.smoothscale(rf, (rf.get_width(), rf.get_height() // 2))
        _FLASK[key] = sq
    return _FLASK[key]


def _cap_sprite():
    """The vented flask cap lying upside down: blue polypropylene with ribs and a white filter."""
    if "cap" in _FLASK:
        return _FLASK["cap"]
    sf = pygame.Surface((44, 40), pygame.SRCALPHA)
    sh = real.contact_shadow(38, 8, 80)
    sf.blit(sh, (2, 20))
    body = pygame.Rect(6, 6, 32, 24)
    m = pygame.Surface(body.size, pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=5)
    sf.blit(real.shaded_mask(m, (52, 112, 196), real.cyl_profile(body.w, 0.3, 0.1, 0.4, 0.7)), body.topleft)
    for i in range(5):
        pygame.draw.line(sf, (34, 80, 150), (body.x + 4 + i * 6, body.y + 4), (body.x + 4 + i * 6, body.bottom - 4), 1)
    pygame.draw.ellipse(sf, (240, 240, 236), (body.x + 6, body.y - 3, 20, 7))
    _FLASK["cap"] = sf
    return sf

# ------------------------------------------------------------------ confluency
CONF = [(30, "About 30 % confluent: leave them to grow"), (60, "About 60 % confluent: give them another day"),
        (85, "About 85 % confluent: split them now"), (100, "100 %, overgrown: split straight away and note it")]


def _confluency_q(rng):
    k = rng.randrange(4)
    target = CONF[k][0]
    seed = rng.randrange(10 ** 6)

    def pic(s, rect):
        import render as RR
        s.blit(RR.rrect_surf(rect.w, rect.h, (16, 16, 20), None, 0, 8, 0, False), rect.topleft)
        c = (rect.centerx, rect.centery - 10)
        R = min(rect.w, rect.h - 24) // 2 - 10

        def cells(f, cc):
            r = random.Random(seed)
            field_bg(f, cc, R, PHASE_BG, seed % 5)
            a, b = 0.135 * R, 0.085 * R
            frac = (math.pi * a * b) / (math.pi * R * R)
            cover = min(target, 97) / 100.0
            n = int(-math.log(1 - cover) / frac)
            if target == 100:
                n = int(n * 1.5)
                a, b = a * 0.8, b * 0.9
            for _ in range(n):
                ang = r.uniform(0, math.tau)
                d = R * math.sqrt(r.random()) * 1.05
                adherent(f, cc[0] + math.cos(ang) * d, cc[1] + math.sin(ang) * d, a * r.uniform(0.8, 1.2), b * r.uniform(0.9, 1.15),
                         r.uniform(0, math.tau), seed=r.randrange(4))
            if target == 100:
                for _ in range(25):
                    ang = r.uniform(0, math.tau)
                    d = R * math.sqrt(r.random())
                    rounded(f, cc[0] + math.cos(ang) * d, cc[1] + math.sin(ang) * d, 5, kind="live")
        masked_field(s, c, R, cells)
        draw_text(s, "10x objective, phase contrast", (rect.centerx, rect.bottom - 16), 12, (170, 172, 180), center=True)
    why = ("Adherent cells are split at about 70-90 % confluence, while they are still dividing. Overgrown cells stop dividing, "
           "acidify the medium (yellow) and can change their behaviour.")
    return dict(q="Your cells look like this. How confluent are they, and what do you do?",
                options=[o for _, o in CONF], answer=k, why=why, pic=pic, keep_order=True)


def _contam_lead(rng):
    """If microbes reached the flask in the hood step, the next morning's flask shows it."""
    from cells_common import ctx_get
    n = ctx_get("culture_contam", 0) or 0
    if n <= 0:
        return None
    seed = rng.randrange(10 ** 6)
    heavy = n >= 2

    def pic(s, rect):
        import render as RR
        s.blit(RR.rrect_surf(rect.w, rect.h, (16, 16, 20), None, 0, 8, 0, False), rect.topleft)
        c = (rect.centerx, rect.centery - 10)
        R = min(rect.w, rect.h - 24) // 2 - 10

        def cells(f, cc):
            r = random.Random(seed)
            field_bg(f, cc, R, (166, 164, 140) if heavy else (156, 158, 144), seed % 5)
            for _ in range(38):
                ang = r.uniform(0, math.tau)
                d = R * math.sqrt(r.random())
                if r.random() < 0.35:
                    rounded(f, cc[0] + math.cos(ang) * d, cc[1] + math.sin(ang) * d, 6, kind="live")
                else:
                    adherent(f, cc[0] + math.cos(ang) * d, cc[1] + math.sin(ang) * d, 0.12 * R, 0.08 * R, r.uniform(0, math.tau), seed=r.randrange(4))
            for _ in range(900 if heavy else 450):       # bacteria: tiny dark rods everywhere between the cells
                ang = r.uniform(0, math.tau)
                d = R * math.sqrt(r.random())
                x, y = cc[0] + math.cos(ang) * d, cc[1] + math.sin(ang) * d
                a = r.uniform(0, math.pi)
                pygame.draw.line(f, (52, 54, 46), (x, y), (x + math.cos(a) * 2.5, y + math.sin(a) * 2.5), 1)
        masked_field(s, c, R, cells)
        draw_text(s, "20x phase contrast, the morning after", (rect.centerx, rect.bottom - 16), 12, (170, 172, 180), center=True)
    return dict(q="The morning after your hood session, the medium is cloudy and %s. Under the microscope you see this. What do you do?"
                  % ("yellow" if heavy else "orange"),
                options=["Bacterial contamination: discard the flask and clean the hood and incubator",
                         "Add more antibiotics and carry on", "Split the cells to dilute the bacteria",
                         "Nothing: the dots are cell debris"],
                answer=0, pic=pic,
                why="Swarms of tiny moving dots and cloudy, acidic (yellow) medium mean bacteria. Antibiotics do not rescue a "
                    "contaminated culture; discard it so the contamination does not spread.")


# ------------------------------------------------------------------ trypsin
def _trypsin_scene(st, s, v):
    gfx.bench(s, PEACH)
    if not hasattr(st, "_cells"):
        r = random.Random(7)
        st._cells = [(r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0, math.pi), r.random(), r.uniform(0, 6.3)) for _ in range(140)]
        st._cells = [c for c in st._cells if c[0] ** 2 + c[1] ** 2 < 0.95][:70]
    c, R = (300, 290), 200
    scope_card(s, c, R)
    round_f = clamp(v / 0.5, 0, 1)

    def field(f, cc):
        field_bg(f, cc, R, PHASE_BG, 1)
        for x, y, ang, th, ph in st._cells:
            cx, cy = cc[0] + x * R, cc[1] + y * R
            detached = v > 0.3 + th * 0.4
            if detached:
                cx += math.sin(st.t * 0.03 + ph) * 6 * (v - 0.3)
                cy += math.cos(st.t * 0.025 + ph) * 6 * (v - 0.3)
            if v > 0.93 and th < (v - 0.93) * 4:     # only a few cells lyse, and only late
                for k in range(5):     # lysed: a pale ghost and debris
                    gfx.alpha_circle(f, (96, 100, 92), (cx + math.cos(ph + k * 1.3) * 7, cy + math.sin(ph + k * 1.3) * 6), 2 + k % 2, 180)
                gfx.alpha_circle(f, (200, 204, 196), (cx, cy), 8, 50)
                continue
            if round_f < 1 and not detached:
                adherent(f, cx, cy, 26 * (1 - round_f) + 10 * round_f, 9, ang, seed=int(ph))
            else:
                rounded(f, cx, cy, 9, kind="live" if detached else "flat")
                if v > 0.88:     # long exposure: some cells bleb
                    for k in range(3):
                        gfx.alpha_circle(f, (236, 240, 228), (cx + math.cos(ph + k * 2) * 10, cy + math.sin(ph + k * 2) * 10), 3, 150)
    masked_field(s, c, R, field, blur=1.0)
    draw_text(s, "20x phase contrast", (c[0], c[1] + R - 3), 11, (170, 172, 180), center=True)
    p = pygame.Rect(570, TOP + 100, 360, 300)
    gfx.card(s, p, CARD)
    det = int(100 * clamp((v - 0.3) / 0.4, 0, 1))
    draw_text(s, "Trypsin-EDTA at 37 °C", (p.x + 16, p.y + 14), 17, INK, bold=True)
    draw_text(s, "Cells detached: %d %%" % det, (p.x + 16, p.y + 48), 16, INK)
    gfx.bar(s, (p.x + 16, p.y + 76, p.w - 32, 18), det / 100.0, TURQ)
    health = 1 - clamp((v - 0.78) / 0.22, 0, 1)
    draw_text(s, "Cell health", (p.x + 16, p.y + 108), 16, INK)
    gfx.bar(s, (p.x + 16, p.y + 136, p.w - 32, 18), health, GREEN if health > 0.6 else CORAL)
    draw_wrapped(s, "Stop (add medium with serum) when most cells float free but before they start to suffer. "
                    "Serum contains trypsin inhibitors.", (p.x + 16, p.y + 170), 14, p.w - 32, INK_SOFT)


# ------------------------------------------------------------------ split maths
def _split_pic(vol, ratio, final):
    def pic(s, rect):
        x, y = rect.x + 30, rect.y + 40
        gfx.tube(s, x, y, 46, 120, (236, 150, 150), 0.75, TURQ)
        draw_text(s, "%d mL cells" % vol, (x + 23, y + 130), 14, INK, center=True, bold=True)
        ax = x + 90
        gfx.line(s, INK, (ax, y + 60), (ax + 112, y + 60), 3)
        gfx.poly(s, INK, [(ax + 110, y + 52), (ax + 124, y + 60), (ax + 110, y + 68)], 0)
        draw_text(s, "1:%d" % ratio, (ax + 55, y + 34), 18, CORAL_D, center=True, bold=True)
        fx = ax + 150
        s.blit(_flask_sprite(MEDIUM, 0), (fx - 20, y + 20))
        draw_text(s, "new flask, %d mL total" % final, (fx + 58, y + 130), 14, INK, center=True, bold=True)
    return pic


def _split_q(rng):
    ratio = rng.choice([3, 4, 5, 8, 10])
    vol = rng.choice([5, 6, 10])
    final = rng.choice([12, 15, 20])
    return dict(text="After trypsinisation you resuspend the cells in %d mL of medium. You split them 1:%d into a new flask "
                     "that should hold %d mL in total. How many mL of cell suspension go into the new flask?" % (vol, ratio, final),
                answer=vol / ratio, unit="mL of cell suspension", tol=0.03, pic=_split_pic(vol, ratio, final),
                why="A 1:%d split takes one part in %d of the cells: %d mL / %d = %.2g mL." % (ratio, ratio, vol, ratio, vol / ratio))


def _medium_q(rng):
    ratio = rng.choice([4, 5, 10])
    vol = 10
    final = rng.choice([12, 15, 20])
    sus = vol / ratio
    return dict(text="You split 1:%d from %d mL of suspension into a flask that should hold %d mL. How many mL of fresh medium "
                     "do you add next to the cells?" % (ratio, vol, final),
                answer=final - sus, unit="mL of fresh medium", tol=0.02, pic=_split_pic(vol, ratio, final),
                why="Cells: %d / %d = %.2g mL. Medium: %d - %.2g = %.3g mL." % (vol, ratio, sus, final, sus, final - sus))


def _double_q(rng):
    days = rng.choice([2, 3, 4])
    seed = rng.choice([0.5, 1, 2])
    return dict(text="Your cells double every 24 hours. You seed %g million cells. Roughly how many million cells will "
                     "the flask hold after %d days, if they keep growing at that rate?" % (seed, days),
                answer=seed * 2 ** days, unit="million cells", tol=0.02,
                why="%d doublings: %g × 2^%d = %g million. In practice growth slows as the flask fills." % (days, seed, days, seed * 2 ** days))


QUIZ = [
    dict(q="Why does cell culture medium contain phenol red?", options=["It is a pH indicator", "It feeds the cells",
         "It kills bacteria", "It stops cells sticking to the plastic"], answer=0,
         why="Phenol red is red at pH 7.4, turns yellow when the medium acidifies (overgrowth or bacteria) and purple when it becomes alkaline."),
    dict(q="Which contamination cannot be seen in the light microscope and does not cloud the medium?",
         options=["Mycoplasma", "Yeast", "Mould", "E. coli"], answer=0,
         why="Mycoplasma are tiny bacteria without a cell wall. Labs test for them by PCR or DNA staining."),
    dict(q="Why do you add medium with serum after trypsinisation?", options=["Serum contains trypsin inhibitors",
         "Serum makes cells divide faster", "Serum turns the medium red", "Serum dissolves EDTA"], answer=0,
         why="Proteins in serum such as alpha-1-antitrypsin inhibit trypsin, so the digestion stops."),
    dict(q="Why is the air in a class II safety cabinet drawn in at the front grille?",
         options=["It forms an air curtain that protects the culture and the worker", "It cools the motor",
                  "It keeps the cabinet dry", "It removes ethanol fumes only"], answer=0,
         why="Room air is pulled into the front grille instead of crossing the work surface, and filtered air flows down over the work."),
]

TECH = dict(
    key="culture", name="Cell culture", full="Cell culture and aseptic technique", wing="Cells & embryos", icon="culture",
    blurb="Growing cells outside the body, in flasks of medium at 37 °C, without letting bacteria or fungi in.",
    facts=[
        "HeLa cells, taken in 1951 from Henrietta Lacks without her knowledge, were the first human cells to grow indefinitely in culture.",
        "Ross Harrison grew frog nerve fibres in a hanging drop of lymph in 1907, often counted as the start of tissue culture.",
        "Most mammalian cells grow at 37 °C in 5 % CO2. The CO2 and the bicarbonate in the medium together keep the pH near 7.4.",
        "Phenol red in the medium is a pH indicator: yellow medium means acid, often from overgrown cells or bacteria.",
        "Mycoplasma contamination is invisible in the light microscope and does not cloud the medium; it is found by PCR or DNA staining.",
        "In the 1960s Stanley Gartler showed that many supposedly different human cell lines were in fact HeLa. Cell line authentication is still needed today.",
        "Trypsin is a digestive protease from the pancreas. It cuts the proteins that hold cells to the plastic.",
        "A class II safety cabinet protects both sides: filtered air flows down over the work and room air is drawn into the front grille.",
    ],
    quiz=QUIZ,
    music=dict(name="Laminar Flow Lullaby", bpm=84, beats=3, root=53, mode="lyd", prog=[0, 1, 4, 0, 5, 1, 3, 4],
               lead="vibes", comp="waltz", drums="none", swing=0.0,
               motif=[(4, 2), (5, 1), (6, 1), (7, 2), (6, 4), (4, 2)]),
    stages=[
        ("culture_hood", {}),
        ("cells_quiz", dict(title="Time to split?", questions=[_confluency_q, _confluency_q, _confluency_q], n=3, tint=PEACH,
                            lead=_contam_lead,
                      instr="Look at the flask in the microscope and decide what to do.")),
        ("stop", dict(title="Trypsin", instr="Trypsin is loosening the cells. Click (or press Space) when most cells float free, before they get damaged.",
                      scene=_trypsin_scene, dur=7.0, ideal=0.66, window=(0.52, 0.84), ease=1.0, jitter=0.1,
                      readout=lambda v: "%.1f min" % (v * 12.0),
                      early_msg="Too early: many cells were still attached and would be lost.",
                      late_msg="A bit long: over-trypsinised cells lose surface proteins and recover slowly.",
                      over_msg="Far too long: over-trypsinised cells lose surface proteins, reattach poorly and some die.",
                      good_msg="Most cells detached and they are still healthy.")),
        ("calc", dict(title="Split the cells", problems=[_split_q, _medium_q, _double_q], n=2, tint=PEACH)),
    ],
)
TECHS = [TECH]
