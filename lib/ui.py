"""
ui.py — all screen drawing for the climate monitor.

Layout (landscape 320x240):
  - Top: clock + date
  - Middle: mode title (Indoor/Outdoor) + source tag (AHT20 / Open-Meteo)
  - Bottom: temperature card (left) + humidity card (right)
  - Tiny dots: which page is active

Themes:
  - Sunny  => blue sky + yellow sun
  - Raining => gray sky + rain streaks (NO sun)
  Rain theme is shared: Indoor and Outdoor use the same background when raining.

Drawing strategy:
  Full SPI redraws are slow, so we only redraw what changed when possible.
"""
import gc


def _c(st7789, r, g, b):
    """Helper: pack an RGB888 color into the display's RGB565 format."""
    return st7789.color565(r, g, b)


MODE_INDOOR = 0
MODE_OUTDOOR = 1
MODE_NAMES = ("Indoor", "Outdoor")


class ClimateUI:
    # Logical drawing size after rotation=1
    W = 320
    H = 240

    def __init__(self, display, st7789, font_big, font_small):
        self.d = display
        self.st = st7789
        self.font_big = font_big      # ~16x32 digits / clock
        self.font_small = font_small  # ~8x16 labels

        # Cache of what was last drawn — used to skip unchanged redraws.
        self._ready = False
        self._last_t = None
        self._last_h = None
        self._last_mode = None
        self._last_clock = ""
        self._last_rain = None

        self.mode = MODE_INDOOR
        self.raining = False

        # Palette
        self.WHITE = st7789.WHITE
        self.SKY = _c(st7789, 95, 165, 230)       # sunny top
        self.SKY2 = _c(st7789, 120, 175, 225)     # sunny bottom
        self.RAIN1 = _c(st7789, 88, 96, 108)      # gray rainy top
        self.RAIN2 = _c(st7789, 70, 78, 90)       # gray rainy bottom
        self.RAIN_DROP = _c(st7789, 170, 190, 210)
        self.CARD_T = _c(st7789, 175, 150, 235)   # purple temp card
        self.CARD_H = _c(st7789, 245, 165, 125)   # orange humidity card
        self.YELLOW = _c(st7789, 255, 220, 40)    # Indoor title
        self.ACCENT_OUT = _c(st7789, 255, 180, 80)
        self.DIM = _c(st7789, 160, 185, 210)
        self.SUN = _c(st7789, 255, 210, 70)

    def bg_top(self):
        """Top sky color depends only on rain (same for Indoor + Outdoor)."""
        return self.RAIN1 if self.raining else self.SKY

    def bg_bot(self):
        """Bottom sky color depends only on rain."""
        return self.RAIN2 if self.raining else self.SKY2

    def t8(self, s, x, y, fg, bg):
        """Draw small text (labels / date)."""
        self.d.text(self.font_small, s, x, y, fg, bg)

    def t16(self, s, x, y, fg, bg):
        """Draw large text (clock / big numbers)."""
        self.d.text(self.font_big, s, x, y, fg, bg)
        gc.collect()

    def _sym_deg(self, x, y, fg, bg):
        """Draw a small ° ring — custom font has no reliable degree glyph."""
        d = self.d
        d.fill_rect(x + 1, y, 4, 1, fg)
        d.fill_rect(x, y + 1, 1, 3, fg)
        d.fill_rect(x + 5, y + 1, 1, 3, fg)
        d.fill_rect(x + 1, y + 4, 4, 1, fg)
        d.fill_rect(x + 2, y + 2, 2, 1, bg)

    def logo_thermo(self, x, y, c):
        """Simple thermometer icon made from rectangles."""
        d = self.d
        d.fill_rect(x + 5, y, 6, 16, c)
        d.fill_rect(x + 7, y + 2, 2, 12, self.CARD_T)
        d.fill_rect(x + 7, y + 8, 2, 8, c)
        d.fill_rect(x + 3, y + 14, 10, 8, c)
        d.fill_rect(x + 12, y + 4, 3, 2, c)
        d.fill_rect(x + 12, y + 8, 3, 2, c)

    def logo_drop(self, x, y, c):
        """Simple water-drop icon made from rectangles."""
        d = self.d
        d.fill_rect(x + 5, y, 4, 3, c)
        d.fill_rect(x + 3, y + 2, 8, 4, c)
        d.fill_rect(x + 1, y + 5, 12, 6, c)
        d.fill_rect(x + 3, y + 10, 8, 4, c)

    def _draw_rain(self):
        """
        Paint evenly spaced diagonal rain streaks across the whole screen.
        Odd rows are shifted so the pattern looks more natural than a plain grid.
        """
        d = self.d
        c = self.RAIN_DROP
        row = 0
        y = 6
        while y < self.H - 14:
            x = 6 + (14 if (row & 1) else 0)
            while x < self.W - 6:
                d.fill_rect(x, y, 2, 8, c)
                d.fill_rect(x + 2, y + 8, 2, 6, c)
                x += 28
            y += 24
            row += 1

    def draw_shell(self):
        """
        Step: paint the background only.
          raining  -> gray bands + rain streaks (no sun)
          sunny    -> blue bands + sun square
        """
        top = self.bg_top()
        bot = self.bg_bot()
        self.d.fill_rect(0, 0, self.W, 110, top)
        self.d.fill_rect(0, 110, self.W, 130, bot)
        if self.raining:
            self._draw_rain()
        else:
            self.d.fill_rect(270, 24, 32, 32, self.SUN)

    def set_raining(self, raining):
        """
        Update rain theme flag.
        Returns True only when the value actually changed (so caller can redraw).
        """
        raining = bool(raining)
        if raining == self.raining:
            return False
        self.raining = raining
        return True

    def draw_clock(self, force=False):
        """Step: draw HH:MM + date. Skips work if the minute text did not change."""
        try:
            from machine import RTC

            y, mo, d, w, hh, mm, ss, _ = RTC().datetime()
            names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
            clock = "{:02d}:{:02d}".format(hh, mm)
            date = "{:04d}/{:02d}/{:02d} {}".format(y, mo, d, names[w % 7])
        except Exception:
            clock = "--:--"
            date = "----/--/-- ---"

        if not force and clock == self._last_clock:
            return
        self._last_clock = clock
        bg = self.bg_top()
        self.d.fill_rect(8, 4, 250, 52, bg)
        self.t16(clock, 12, 6, self.WHITE, bg)
        self.t8(date, 14, 42, self.WHITE, bg)

    def draw_mode(self):
        """Step: draw Indoor/Outdoor title, source tag, and page-indicator dots."""
        name = MODE_NAMES[self.mode]
        accent = self.YELLOW if self.mode == MODE_INDOOR else self.ACCENT_OUT
        tag = "AHT20" if self.mode == MODE_INDOOR else "Open-Meteo"
        bg = self.bg_top()
        self.d.fill_rect(8, 58, 250, 40, bg)
        self.t8(name, 12, 60, accent, bg)
        self.t8(tag, 12, 80, self.WHITE, bg)

        bot = self.bg_bot()
        self.d.fill_rect(140, 220, 50, 12, bot)
        # Left dot = Indoor, right dot = Outdoor (bright = active).
        self.d.fill_rect(150, 222, 8, 8, self.WHITE if self.mode == MODE_INDOOR else self.DIM)
        self.d.fill_rect(172, 222, 8, 8, self.WHITE if self.mode == MODE_OUTDOOR else self.DIM)

    def _fmt_t(self, v):
        """Format temperature number only (degree + C are drawn separately)."""
        return "--.-" if v is None else "{:.1f}".format(v)

    def _fmt_h(self, v):
        """Format humidity with one decimal and a normal % character."""
        return "--.-%" if v is None else "{:.1f}%".format(v)

    def draw_temp_card(self, temp_c):
        """Step: purple card + thermometer icon + value + °C."""
        num = self._fmt_t(temp_c)
        self.d.fill_rect(16, 118, 140, 90, self.CARD_T)
        self.logo_thermo(24, 148, self.WHITE)
        self.t16(num, 48, 145, self.WHITE, self.CARD_T)
        ux = 48 + len(num) * 16
        self._sym_deg(ux + 1, 147, self.WHITE, self.CARD_T)
        self.t16("C", ux + 8, 145, self.WHITE, self.CARD_T)

    def draw_hum_card(self, humidity):
        """Step: orange card + drop icon + humidity%."""
        h_s = self._fmt_h(humidity)
        self.d.fill_rect(164, 118, 140, 90, self.CARD_H)
        self.logo_drop(172, 156, self.WHITE)
        self.t16(h_s, 188, 145, self.WHITE, self.CARD_H)

    def set_mode(self, mode):
        """
        Switch Indoor/Outdoor.
        Returns False if the mode did not change (avoids useless redraws).
        """
        if mode not in (MODE_INDOOR, MODE_OUTDOOR):
            return False
        if mode == self.mode and self._ready:
            return False
        self.mode = mode
        return True

    def show_page(self, temp_c, humidity):
        """
        Draw one complete page for the current mode.

        Steps:
          1) If rain theme changed (or first draw), repaint sky/rain/sun + clock
          2) Draw mode labels
          3) Draw temperature card
          4) Draw humidity card
        """
        rain_changed = self._last_rain != self.raining
        if rain_changed or not self._ready:
            self.draw_shell()
            gc.collect()
            self.draw_clock(force=True)
            gc.collect()

        self.draw_mode()
        gc.collect()
        self.draw_temp_card(temp_c)
        gc.collect()
        self.draw_hum_card(humidity)
        gc.collect()

        self._last_t = self._fmt_t(temp_c)
        self._last_h = self._fmt_h(humidity)
        self._last_mode = self.mode
        self._last_rain = self.raining
        print("ui:", MODE_NAMES[self.mode], self._last_t, self._last_h, "rain", self.raining)

    def render(self, temp_c, humidity, full=False):
        """
        Smart update entry used by main.py.

          full=True  -> boot / force full redraw
          otherwise  -> redraw only what changed (mode, rain, T, H, or clock)
        """
        t_s = self._fmt_t(temp_c)
        h_s = self._fmt_h(humidity)

        # First boot path.
        if full or not self._ready:
            print("ui: boot")
            self.draw_shell()
            gc.collect()
            self.draw_clock(force=True)
            gc.collect()
            self.show_page(temp_c, humidity)
            self._ready = True
            print("ui: boot done")
            return

        # Mode or rain theme changed -> rebuild the page.
        if self._last_mode != self.mode or self._last_rain != self.raining:
            self.show_page(temp_c, humidity)
            return

        # Same page: only touch cards whose text changed.
        if t_s != self._last_t:
            self.draw_temp_card(temp_c)
            self._last_t = t_s

        if h_s != self._last_h:
            self.draw_hum_card(humidity)
            self._last_h = h_s

        # Clock updates when the minute rolls over.
        self.draw_clock(force=False)
