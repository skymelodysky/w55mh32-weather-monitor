"""
net_weather.py — outdoor weather over Ethernet (no PC helper program).

Steps this module covers:
  1) init_ethernet()  — reset W5500, wait for cable link, DHCP (or static IP)
  2) _http_get()      — tiny HTTP/1.0 client (plain TCP, port 80)
  3) fetch_outdoor()  — call Open-Meteo (fallback wttr.in), parse T/H/rain
  4) load/save cache  — remember last outdoor values in /outdoor.txt

Returns from fetch_outdoor():
  (temperature_C, humidity_percent, raining_bool)
  or (None, None, False) if everything failed and there is no cache.
"""
import time
import json
import socket
import network
from machine import Pin, SPI

# config.py is optional so this file can be imported in small tests.
try:
    import config
except ImportError:
    config = None

# Flash file used as a tiny outdoor weather cache.
_CACHE = "/outdoor.txt"


def _cfg(name, default):
    """Read a setting from config.py, or use default if missing."""
    if config is None:
        return default
    return getattr(config, name, default)


def _link_up(nic):
    """Return True when the Ethernet cable link is up."""
    try:
        if hasattr(nic, "isconnected"):
            return bool(nic.isconnected())
    except Exception:
        pass
    try:
        st = nic.status()
        return st != 0 and st is not False
    except Exception:
        return False


def load_cached():
    """
    Step: read last successful outdoor result from flash.
    Used at boot so Outdoor is not empty while the network starts.
    """
    try:
        with open(_CACHE, "r") as f:
            j = json.loads(f.read())
        rain = bool(j.get("rain", False))
        return float(j["t"]), float(j["h"]), rain
    except Exception:
        return None, None, False


def save_cached(t, h, rain=False):
    """Step: store outdoor T/H/rain after a successful fetch."""
    try:
        with open(_CACHE, "w") as f:
            f.write(json.dumps({"t": t, "h": h, "rain": bool(rain)}))
    except Exception:
        pass


def _is_raining(weather_code, precip):
    """
    Decide rain from Open-Meteo fields.
    - weather_code: WMO codes (drizzle / rain / showers / thunder)
    - precipitation: any value > 0 also counts as raining
    """
    rain_codes = (
        51, 53, 55, 56, 57,
        61, 63, 65, 66, 67,
        80, 81, 82,
        95, 96, 99,
    )
    try:
        if weather_code is not None and int(weather_code) in rain_codes:
            return True
    except Exception:
        pass
    try:
        if precip is not None and float(precip) > 0.0:
            return True
    except Exception:
        pass
    return False


def _ip_ok(cfg):
    """True when ifconfig() returned a real IPv4 address."""
    try:
        ip = cfg[0]
        return ip and ip != "0.0.0.0"
    except Exception:
        return False


def init_ethernet(wait_s=30):
    """
    Step-by-step Ethernet bring-up for W55MH32 + W5500:

      1. Drive reset / power pins
      2. Create network.WIZNET5K on SPI2
      3. Wait until cable LINK is up
      4. Request DHCP (or apply static IP)
      5. Wait briefly, then return (nic, ip_string)
    """
    use_dhcp = bool(_cfg("USE_DHCP", True))
    print("==========")
    print("DHCP" if use_dhcp else "Static IP")
    print("==========")
    try:
        # --- hardware pins used by this EVB's Ethernet ---
        spi = SPI(2)
        cs = Pin("PB12", Pin.OUT)
        rst = Pin("PD9", Pin.OUT)
        Pin("PE15", Pin.OUT, value=0)  # PWDN low = chip enabled

        # Hardware reset pulse.
        rst.value(0)
        time.sleep_ms(200)
        rst.value(1)
        time.sleep_ms(500)

        # Create and activate the NIC driver.
        nic = network.WIZNET5K(spi, cs, rst)
        nic.active(True)
        time.sleep_ms(300)

        # Wait for physical link (cable to PC ICS or to a router).
        print("net: waiting LINK (PC ICS or router)...")
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < wait_s * 1000:
            up = _link_up(nic)
            st = "?"
            try:
                st = nic.status()
            except Exception:
                pass
            print("net: link", up, "status", st)
            if up:
                break
            time.sleep_ms(500)

        if not _link_up(nic):
            print("net: NO LINK")
            return None, None

        # Get an IP address.
        if use_dhcp:
            print("net: requesting DHCP...")
            try:
                nic.ifconfig("dhcp")
            except Exception as e:
                print("net: dhcp start err", e)
            t1 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t1) < wait_s * 1000:
                cfg = nic.ifconfig()
                print("net: dhcp", cfg)
                if _ip_ok(cfg):
                    break
                time.sleep_ms(500)
            cfg = nic.ifconfig()
            if not _ip_ok(cfg):
                print("net: DHCP FAILED — enable ICS on PC Wi-Fi -> Ethernet")
                return None, None
        else:
            static = _cfg(
                "STATIC_IP",
                ("192.168.137.2", "255.255.255.0", "192.168.137.1", "8.8.8.8"),
            )
            nic.ifconfig(static)

        # Let the stack settle before the first outbound TCP connect.
        time.sleep_ms(2000)
        print("net: LINK UP", nic.ifconfig())
        return nic, nic.ifconfig()[0]
    except Exception as e:
        print("net: fail", e)
        return None, None


def _http_get(ip, host, path, port=80, timeout_s=15):
    """
    Tiny HTTP GET (no TLS).

    Steps:
      1. TCP connect to ip:port
      2. Send GET + Host header
      3. Read response bytes
      4. Require HTTP 200 and return the body as text
    """
    addr = (ip, port)
    print("net: connect", addr, "Host", host)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.settimeout(timeout_s)
        except Exception:
            pass
        s.connect(addr)
        print("net: connected")

        # HTTP/1.0 + Connection: close keeps the exchange simple on MCU.
        req = "GET {} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n".format(
            path, host
        )
        s.send(req.encode())

        buf = b""
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_s * 1000:
            try:
                chunk = s.recv(512)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            if len(buf) > 6000:  # enough for this JSON; avoid huge buffers
                break

        if not buf:
            raise OSError("empty")
        print("net: status", buf.split(b"\r\n", 1)[0])
        if b"\r\n\r\n" not in buf:
            raise ValueError("no body")

        header, body = buf.split(b"\r\n\r\n", 1)
        if b"200" not in header.split(b"\r\n", 1)[0]:
            raise ValueError(header.split(b"\r\n", 1)[0])

        # MicroPython: bytes.decode() does not take errors= keyword args.
        try:
            return body.decode("utf-8")
        except Exception:
            return str(body, "utf-8")
    finally:
        try:
            s.close()
        except Exception:
            pass


def fetch_outdoor():
    """
    Pull outdoor weather for the UI.

    Order:
      1. Try Open-Meteo (primary)
      2. Try wttr.in (fallback)
      3. Each source gets 2 attempts
      4. On total failure, return cached values if present
    """
    targets = [
        (
            _cfg("WX_IP", "188.40.99.226"),
            _cfg("WX_HOST", "api.open-meteo.com"),
            _cfg(
                "WX_PATH",
                "/v1/forecast?latitude=22.3022&longitude=114.1744"
                "&current=temperature_2m,relative_humidity_2m,weather_code,precipitation",
            ),
            "open-meteo",
        ),
        (
            _cfg("WTTR_IP", "5.9.243.187"),
            "wttr.in",
            "/HongKong?format=j1",
            "wttr",
        ),
    ]

    for ip, host, path, name in targets:
        for attempt in range(2):
            try:
                print("net: try", name, "attempt", attempt + 1)
                body = _http_get(ip, host, path)
                rain = False

                if name == "open-meteo":
                    # Open-Meteo JSON: { "current": { "temperature_2m": ... } }
                    cur = json.loads(body).get("current", {})
                    t = cur.get("temperature_2m")
                    h = cur.get("relative_humidity_2m")
                    rain = _is_raining(
                        cur.get("weather_code"),
                        cur.get("precipitation"),
                    )
                else:
                    # wttr.in j1 format
                    j = json.loads(body)
                    cur = j["current_condition"][0]
                    t = float(cur["temp_C"])
                    h = float(cur["humidity"])
                    try:
                        rain = float(cur.get("precipMM", 0) or 0) > 0
                    except Exception:
                        rain = False
                    if not rain:
                        desc = str(cur.get("weatherDesc", [{}])[0].get("value", "")).lower()
                        rain = ("rain" in desc) or ("drizzle" in desc) or ("shower" in desc)

                if t is not None and h is not None:
                    t, h = float(t), float(h)
                    save_cached(t, h, rain)
                    print("net: {} T={} H={} rain={}".format(name, t, h, rain))
                    return t, h, rain
            except Exception as e:
                # On this firmware, errno 13 often means connect timeout.
                print("net: {} err".format(name), e)
                time.sleep_ms(800)

    # Nothing online worked — fall back to flash cache.
    cached = load_cached()
    if cached[0] is not None:
        print("net: using cached outdoor", cached)
        return cached
    return None, None, False


# Old name kept so older imports still work.
fetch_hko = fetch_outdoor
