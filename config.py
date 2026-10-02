# =============================================================================
# config.py — all user-tunable settings for the climate monitor
# Edit this file to change network mode, pins, refresh rates, or location.
# =============================================================================

# --- Network ---
# USE_DHCP=True is the normal desk setup:
#   PC Wi-Fi -> Internet Connection Sharing -> PC Ethernet (often 192.168.137.1)
#   Board Ethernet cable plugged into the PC -> board gets 192.168.137.x
USE_DHCP = True

# Used only when USE_DHCP=False (manual static address on the ICS subnet).
NET_IP = "192.168.137.2"
NET_SN = "255.255.255.0"
NET_GW = "192.168.137.1"       # PC ICS gateway
NET_DNS = "8.8.8.8"
STATIC_IP = (NET_IP, NET_SN, NET_GW, NET_DNS)

# Reserved for older TCP-server experiments (not required by current main.py).
LOCAL_PORT = 5000

# How often main.py re-reads the AHT20 (milliseconds).
SENSOR_INTERVAL_MS = 2000

# --- Pins (match your wiring) ---
I2C_ID = 1                     # AHT20 on I2C1 (PB6/PB7 on this EVB)

# ST7789 display on SPI1
SPI_DISPLAY_ID = 1
SPI_DISPLAY_BAUD = 72_000_000
PIN_TFT_CS = "PC4"
PIN_TFT_DC = "PB0"
PIN_TFT_RST = "PC5"
PIN_TFT_BL = "PB1"             # backlight / BR pin (digital on/off)
TFT_WIDTH = 240
TFT_HEIGHT = 320
TFT_INVERSION = False
TFT_ROTATION = 1               # landscape UI

# W5500 Ethernet on SPI2 (onboard on W55MH32L-EVB)
SPI_ETH_ID = 2
SPI_ETH_BAUD = 8_000_000
PIN_ETH_CS = "PB12"
PIN_ETH_RST = "PD9"
PIN_ETH_PWDN = "PE15"

PIN_LED = "PD14"               # activity LED in main loop
PIN_BTN_LEFT = "PA8"           # Indoor page
PIN_BTN_RIGHT = "PC7"          # Outdoor page

# --- Outdoor weather (board fetches this itself; no PC push program) ---
# Location: Hong Kong (22.3022N, 114.1744E)
WX_ENABLED = True

# Open-Meteo IP is fixed here so the board does not need DNS.
# HTTP still sends Host: api.open-meteo.com
WX_IP = "188.40.99.226"
WX_HOST = "api.open-meteo.com"
WX_PATH = (
    "/v1/forecast?latitude=22.3022&longitude=114.1744"
    "&current=temperature_2m,relative_humidity_2m,weather_code,precipitation"
)

# Fallback weather host if Open-Meteo fails.
WTTR_IP = "5.9.243.187"

# How often main.py refetches outdoor weather (milliseconds). 300000 = 5 minutes.
WX_INTERVAL_MS = 300000
