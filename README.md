# Office Weather Monitor


Board program for the **W55MH32-ADK**: indoor temperature and humidity from an **AHT20**, outdoor weather from **Open-Meteo (Hong Kong)** over Ethernet, shown on the on-board SPI monitor.

You do **not** need a PC program to push weather. The board fetches it itself. The PC only shares Wi‑Fi internet to the board over the Ethernet cable.

## What you need

- W55MH32-ADK with MicroPython
- AHT20 sensor
- Ethernet cable: board → PC Ethernet port
- PC on Wi‑Fi, with Internet Connection Sharing turned on
- Thonny (or another MicroPython uploader) to copy files to the board


## Share the PC internet to the board

The PC uses Wi‑Fi. The board uses the Ethernet cable.

1. Press `Win + R`, type `ncpa.cpl`, press Enter.
2. Right‑click **Wi‑Fi** → **Properties**.
3. Open the **Sharing** tab.
4. Check **Allow other network users to connect through this computer's internet connection.**.
5. Home networking connection: **Ethernet**.
6. Click **ok**.

Plug the board Ethernet port into the PC Ethernet port. Link lights should be on.

`config.py` is already set to DHCP (`USE_DHCP = True`). The board should get an address.

## Copy these files onto the board

From the `micropython` folder on your PC, upload this layout:

```
/main.py
/config.py
/lib/ui.py
/lib/net_weather.py
/lib/ahtx0.py
/lib/roboto16.py
/lib/roboto8.py
```

In Thonny:

1. Connect the board over USB and select the MicroPython interpreter.
2. Open each file above.
3. Use **File → Save as… → MicroPython device**.
4. Save `main.py` and `config.py` in the root (`/`).
5. Save the others inside `/lib/` (create `lib` if it is missing).

Do **not** upload `rain_test.py` as `main.py`. That file is only a display preview.

## Run it

1. In Thonny, open `/main.py` on the board.
2. Press **Run** (or reset the board if `main.py` already runs on boot).
3. The screen starts on **Indoor** (yellow title, `AHT20`).
4. Press the right button (PC7) for **Outdoor** (`Open-Meteo`).
5. Press the left button (PA8) to go back to Indoor.

Indoor updates about every 2 seconds. Outdoor weather updates on boot, then about every 5 minutes.

### Serial output that means it worked

```
ui: Indoor ...
==========
DHCP
==========
net: LINK UP ('192.168.137.xx', ...)
net: try open-meteo attempt 1
net: open-meteo T=... H=... rain=...
outdoor: ...
```

### Rain

If Open-Meteo says Hong Kong is raining, **both** Indoor and Outdoor use the gray rainy background. The outdoor label stays `Open-Meteo` (it does not say “Rain”).

## Optional: preview the rainy screen

This does not use the network. It forces the rain look so you can check the drawing.

1. Upload `micropython/tools/rain_test.py` to the board (any name except replacing a file you still need).
2. Run that file instead of `main.py`.

| Button | Preview |
|--------|---------|
| PA8 | Indoor page |
| PC7 | Outdoor page |
| Both together | Toggle rain / sunny |

When you are done, run `main.py` again.

## If something fails

| What you see | What to check |
|--------------|----------------|
| No link / `net: link False` | Cable, both link lights, Ethernet adapter enabled |
| `DHCP FAILED` | ICS sharing is on Wi‑Fi → Ethernet, then reboot the PC |
| DHCP works, weather fails | PC Wi‑Fi still has internet; try the page again after a reset |
| Indoor numbers missing | AHT20 wiring (PB6 / PB7), 3V3 and GND |
| Outdoor shows `--` | Weather fetch failed; look at the Thonny shell for `net:` lines |

Location used for outdoor weather is Hong Kong: latitude `22.3022`, longitude `114.1744` in `config.py`.
