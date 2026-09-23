# E-Control Tarifkalkulator for Home Assistant

[![Version](https://img.shields.io/badge/version-1.0.0-green)]()
[![Maintainer](https://img.shields.io/badge/maintainer-acdcnow-blue)](https://github.com/acdcnow)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.9.3%2B-blue)](https://www.home-assistant.io/)

Compare Austrian electricity and gas tariffs from the official **E-Control
Tarifkalkulator** inside Home Assistant.

**Supported categories:**
* ✅ **Strom Bezug** (electricity consumption)
* ✅ **Gas** (gas consumption)
* 🧪 **Strom Einspeisung** (electricity feed-in, experimental)

## ✨ Highlights

* **Cheapest offer as a sensor**, in € per year and in ct/kWh.
* **Your own product as a sensor**, plus the maximum saving of the comparison.
* **Full offer list** as an attribute of the offers sensor — brand, product, annual cost,
  price per kWh, supplier, price guarantee, switching link and renewable share.
* **One device per energy type**, so electricity, gas and feed-in never collide.
* **No credentials needed** for the public interface.
* **Configurable at runtime:** consumption, discount handling, comparison period,
  polling interval and the product the savings are calculated against.
* **Diagnostics download** with the resolved grid operator and the comparison summary
  (credentials redacted).

## ⚠️ Important notes

* A tariff comparison needs a **yearly consumption** — there is no such thing as a
  consumption-independent electricity price. The defaults follow the usual household
  values and can be changed at any time.
* The public interface has no data for **every** grid area, and the **feed-in**
  comparison is not offered everywhere. Affected energy types stay unavailable and
  report the reason while the other types keep working.
* The **partner interface** (with credentials) needs an account at E-Control. Its
  resource paths could not be verified against the productive service — use the public
  interface unless you have been given credentials.

## Installation

1. Add this repository as a **Custom Repository** of type *Integration* in HACS.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for
   **E-Control Tarifkalkulator**.

## Documentation

Architecture, software design and workflow diagrams:
**[wiki](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki)**

---
*This is a community project and is not affiliated with E-Control or any energy supplier.*
