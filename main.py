"""
Office climate monitor — main program (run this file on the board).

What this app does (high level):
  1. Show Indoor temp/humidity from the AHT20 sensor.
  2. Fetch Outdoor Hong Kong weather from Open-Meteo over Ethernet.
  3. Let you switch pages with two buttons.
  4. If Open-Meteo says it is raining, use a gray rainy background on BOTH pages.

Buttons:
  PA8  = Indoor
  PC7  = Outdoor

Network:
  Board Ethernet <-> PC Ethernet, with Windows ICS sharing Wi-Fi to Ethernet
  (board usually gets 192.168.137.x by DHCP).
"""
import time

# Give USB/serial a moment after reset so Thonny can attach cleanly.
time.sleep(1)

import gc
import sys
from machine import Pin, I2C, SPI

# MicroPython looks for modules on the board filesystem.
# Our helpers live in /lib (ui, net_weather, fonts, sensor driver).
sys.path.append("/lib")
sys.path.append(".")

import config
import ahtx0
import st7789py as st7789
import roboto16 as font_big
import roboto8 as font_small
from ui import ClimateUI, MODE_INDOOR, MODE_OUTDOOR
import net_weather


def init_display():
    """Step: bring up the ST7789 LCD on SPI1."""
    print("init display...")

    # SPI1 pins on this EVB: SCK=PA5, MOSI=PA7 (wired to the panel).
    spi = SPI(1, baudrate=72_000_000, polarity=0, phase=0)

    # Panel physical size is 240x320; rotation=1 makes the UI landscape 320x240.
    # Backlight (BR/BL) is a normal digital pin — on/off only, not PWM.
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
    print("display ok", display.width, display.height)
    return display


def main():
    """
    Startup steps:
      1) Load last outdoor cache (so Outdoor is not blank if net is slow)
      2) Init display + UI
      3) Init AHT20 and draw Indoor
      4) Bring up Ethernet and fetch outdoor weather once
      5) Loop forever: buttons, sensor updates, periodic weather refresh
    """
    # Status LED — blinks briefly on each successful indoor sensor read.
    led = Pin(getattr(config, "PIN_LED", "PD14"), Pin.OUT)

    # Step 1: try cached outdoor values from flash (/outdoor.txt).
    outdoor_t, outdoor_h, outdoor_rain = net_weather.load_cached()
    nic = None  # Ethernet interface handle; set after init_ethernet()

    # Step 2: display + UI object (UI draws; main only decides what to show).
    display = init_display()
    ui = ClimateUI(display, st7789, font_big, font_small)
    ui.set_raining(outdoor_rain)  # apply cached rain theme early if any

    # Buttons are active-low with internal pull-ups (pressed => value 0).
    btn_left = Pin(getattr(config, "PIN_BTN_LEFT", "PA8"), Pin.IN, Pin.PULL_UP)
    btn_right = Pin(getattr(config, "PIN_BTN_RIGHT", "PC7"), Pin.IN, Pin.PULL_UP)

    # Step 3: I2C AHT20 indoor sensor.
    print("init sensor...")
    i2c = I2C(config.I2C_ID)
    print("i2c:", [hex(a) for a in i2c.scan()])  # helpful wiring check
    sensor = ahtx0.AHT20(i2c)
    print("sensor ok")

    # First paint: always start on Indoor with a full-screen redraw.
    indoor_t = sensor.temperature
    indoor_h = sensor.relative_humidity
    ui.set_mode(MODE_INDOOR)
    ui.render(indoor_t, indoor_h, full=True)

    # Step 4: optional outdoor fetch over Ethernet.
    if getattr(config, "WX_ENABLED", True):
        nic, _ip = net_weather.init_ethernet()
        if nic:
            t, h, rain = net_weather.fetch_outdoor()
            if t is not None:
                outdoor_t, outdoor_h, outdoor_rain = t, h, rain
                ui.set_raining(outdoor_rain)
                print("outdoor:", outdoor_t, outdoor_h, "rain", outdoor_rain)
            else:
                print("outdoor: fetch failed — check ICS / DHCP / cable")

    # Edge-detect state for buttons (1 = released, 0 = pressed).
    last_left = 1
    last_right = 1

    # Non-blocking timers (MicroPython ticks wrap; use ticks_diff).
    last_sensor_ms = time.ticks_ms()
    last_wx_ms = time.ticks_ms()
    sensor_ms = getattr(config, "SENSOR_INTERVAL_MS", 2000)   # ~2 s indoor
    wx_ms = getattr(config, "WX_INTERVAL_MS", 300000)         # ~5 min outdoor

    # Step 5: main loop — never returns.
    while True:
        left_now = btn_left.value()
        right_now = btn_right.value()

        # Falling edge on left button => switch to Indoor page.
        if last_left == 1 and left_now == 0:
            if ui.set_mode(MODE_INDOOR):
                print("mode: Indoor")
                ui.show_page(indoor_t, indoor_h)
            time.sleep_ms(200)  # simple debounce

        # Falling edge on right button => switch to Outdoor page.
        if last_right == 1 and right_now == 0:
            if ui.set_mode(MODE_OUTDOOR):
                print("mode: Outdoor", outdoor_t, outdoor_h, "rain", outdoor_rain)
                ui.show_page(outdoor_t, outdoor_h)
            time.sleep_ms(200)

        last_left = left_now
        last_right = right_now

        now = time.ticks_ms()

        # Periodic indoor sensor update.
        if time.ticks_diff(now, last_sensor_ms) >= sensor_ms:
            last_sensor_ms = now
            try:
                led.on()
                indoor_t = sensor.temperature
                indoor_h = sensor.relative_humidity
                led.off()
                # Only redraw cards when the Indoor page is visible.
                if ui.mode == MODE_INDOOR:
                    ui.render(indoor_t, indoor_h, full=False)
            except Exception as e:
                print("sensor err:", e)

        # Periodic outdoor weather refresh (needs a working NIC).
        if nic and time.ticks_diff(now, last_wx_ms) >= wx_ms:
            last_wx_ms = now
            t, h, rain = net_weather.fetch_outdoor()
            if t is not None:
                outdoor_t, outdoor_h, outdoor_rain = t, h, rain
                changed = ui.set_raining(outdoor_rain)
                if ui.mode == MODE_OUTDOOR:
                    # Outdoor page is open — show fresh numbers now.
                    ui.show_page(outdoor_t, outdoor_h)
                elif changed:
                    # Indoor is open; rain theme applies on next full page draw.
                    pass

        # Free unused heap between loops (helps MicroPython stay stable).
        gc.collect()
        time.sleep_ms(30)


main()
