"""
Rainy background preview — no Ethernet / weather fetch.

PA8 = Indoor page, PC7 = Outdoor page
Both pages share rain bg when raining=True (forced in this test).

Edit RAINING below, or hold both buttons to toggle rain/sunny.
"""
import time
import sys
from machine import Pin, SPI

sys.path.append("/lib")
sys.path.append(".")

import st7789py as st7789
import roboto16 as font_big
import roboto8 as font_small
from ui import ClimateUI, MODE_INDOOR, MODE_OUTDOOR

# Force rain theme for preview (True = gray + streaks on BOTH pages)
RAINING = True


def init_display():
    spi = SPI(1, baudrate=72_000_000, polarity=0, phase=0)
    display = st7789.ST7789(
        spi,
        240,
        320,
        reset=Pin("PC5", Pin.OUT),
        dc=Pin("PB0", Pin.OUT),
        cs=Pin("PC4", Pin.OUT),
        backlight=Pin("PB1", Pin.OUT),
        rotation=1,
    )
    display.inversion_mode(False)
    return display


def show(ui, mode, raining):
    ui.set_raining(raining)
    ui.set_mode(mode)
    if mode == MODE_INDOOR:
        ui.show_page(27.9, 50.8)
    else:
        ui.show_page(26.5, 88.0)
    print(
        "rain test:",
        "Indoor" if mode == MODE_INDOOR else "Outdoor",
        "RAIN" if raining else "SUNNY",
    )


def main():
    print("rain_test: start")
    display = init_display()
    ui = ClimateUI(display, st7789, font_big, font_small)

    btn_in = Pin("PA8", Pin.IN, Pin.PULL_UP)
    btn_out = Pin("PC7", Pin.IN, Pin.PULL_UP)

    raining = RAINING
    mode = MODE_OUTDOOR
    show(ui, mode, raining)

    last_l = 1
    last_r = 1
    while True:
        l = btn_in.value()
        r = btn_out.value()

        # both pressed together -> toggle rain / sunny
        if last_l == 1 and last_r == 1 and l == 0 and r == 0:
            raining = not raining
            show(ui, mode, raining)
            time.sleep_ms(400)
            last_l = btn_in.value()
            last_r = btn_out.value()
            continue

        if last_l == 1 and l == 0:
            mode = MODE_INDOOR
            show(ui, mode, raining)
            time.sleep_ms(200)
        if last_r == 1 and r == 0:
            mode = MODE_OUTDOOR
            show(ui, mode, raining)
            time.sleep_ms(200)

        last_l = l
        last_r = r
        time.sleep_ms(30)


main()
