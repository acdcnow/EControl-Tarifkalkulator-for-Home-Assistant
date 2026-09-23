# E-Control Tarifkalkulator for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Maintainer](https://img.shields.io/badge/maintainer-acdcnow-blue)](https://github.com/acdcnow)
[![Version](https://img.shields.io/badge/version-1.0.0-green)]()
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.9.3%2B-blue)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

A custom component for Home Assistant that answers one question with numbers instead of
tab hopping: **"How much would I pay for electricity or gas right now, and what would a
change of provider save me?"**

The integration queries the official Austrian **E-Control Tarifkalkulator** (the tariff
calculator of the Austrian regulator) for the postal code of your home and publishes the
result as sensors: the cheapest offer, its all-in price per kWh, the price of the product
you actually hold, and the maximum saving.

```text
sensor.e_control_strom_bezug_cheapest_offer                1.154,55 €
sensor.e_control_strom_bezug_cheapest_offer_price_per_kwh     28,44 ct/kWh
sensor.e_control_strom_bezug_own_product                    1.687,83 €
sensor.e_control_strom_bezug_possible_saving                  173,56 €
sensor.e_control_strom_bezug_offers                                107
```

## ✨ Features

* **Three categories:** electricity consumption (*Strom Bezug*), gas (*Gas*) and
  electricity feed-in (*Strom Einspeisung*, experimental — see below).
* **Consumer tariffs:** the `HOME` customer group; the `BUSINESS` group is selectable.
* **Cheapest offer and own product:** the cheapest offer is priced against the product you
  configured, so the saving is a real number and not just a ranking.
* **Full offer list:** the complete, price-sorted comparison is available as an attribute
  of the offers sensor — build your own cards or automations on top of it.
* **One device per energy type:** electricity, gas and feed-in each get their own device,
  so a dashboard, an energy card or a Voice Assistant can distinguish them.
* **Options flow:** consumption, discount handling, comparison period and polling
  interval are configurable at runtime. A change reloads the integration immediately.
* **Diagnostics:** a download with the resolved grid operator, the comparison product and
  the summary of the last comparison. Credentials are redacted.
* **Partial availability:** if one energy type cannot be compared (for example because the
  feed-in comparison is not offered for your grid area), the other types keep working and
  the failing one reports the reason in its `failed_reason` attribute.

## 📚 Documentation

The design of this integration is documented in the
**[project wiki](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki)**:

| Document | What it covers |
| :--- | :--- |
| 🏠 **[Documentation home](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki/Home)** | Landing page: which document answers which question. |
| 🏛️ **[Architecture Design Document](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki/Architecture-Design-Document)** | Architecture concept, module boundaries and the numbered architecture decisions (`AD-1` … `AD-9`). |
| 🔧 **[Software Design Document](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki/Software-Design-Document)** | Structural view, interface contracts, component design, error handling matrix, traceability. |
| 🔄 **[Workflow Diagrams](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki/Workflow-Diagrams)** | Setup, update cycle, options change and error handling as diagrams. |

The interface itself is documented in the
**[API protocol section of the wiki](https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant/wiki/Software-Design-Document#3-interface-contracts)**,
including the request body, the field semantics and the values that the public endpoint
rejects.

## 📥 Installation

### Option 1: Via HACS (recommended)

This is a custom integration, so it is added as a **custom repository**:

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three dot menu (`...`) in the top right corner and select **Custom repositories**.
4. Paste the URL of this repository (`https://github.com/acdcnow/EControl-Tarifkalkulator-for-Home-Assistant`).
5. Select **Integration** as the category and click **Add**.
6. Search for **E-Control Tarifkalkulator** in HACS and install it.
7. Restart Home Assistant.

### Option 2: Manual

1. Copy the folder `custom_components/econtrol` from this repository.
2. Place it in your Home Assistant configuration directory, so that the result is
   `/config/custom_components/econtrol/__init__.py`.
3. Restart Home Assistant.

## ⚙️ Configuration

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration** and search for **E-Control Tarifkalkulator**.
3. Choose the **data source**:
   * **Public interface without credentials** — the interface behind
     [www.e-control.at/tarifkalkulator](https://www.e-control.at/tarifkalkulator).
     No account is required. **This is the recommended and verified source.**
   * **Partner interface with credentials** — the contractual `rc` interface for
     comparison portals. It needs a user name, a password and the endpoint. ⚠️ The
     resource paths of this interface are derived from the public interface; the
     productive service answered `401` for every request, so this source could not be
     verified end to end.
4. Enter your **postal code** (four digits) and select the **energy types** to compare.
5. Enter the **yearly consumption** for every selected type and confirm.

The grid operator of your postal code and the product used for the comparison are
resolved automatically: the grid operator's own brand and that brand's default product.
That is exactly what the public calculator pre-selects.

### Options

**Settings → Devices & Services → E-Control Tarifkalkulator → Configure**

| Option | Meaning | Default |
| :--- | :--- | :--- |
| Yearly consumption | Per energy type, in kWh (1 … 100000) | 3500 / 2000 / 15000 |
| Include switching discounts | Count one-off switching bonuses | on |
| Comparison period | One, two or three years | one year |
| Update interval | Polling interval in hours (1 … 168) | 24 |
| Offers in the attributes | How many offers the offers sensor carries | 10 |

The second menu entry (**Product to compare against**) selects which product the savings
are calculated against — normally the contract you hold today. Leave it on *Keep automatic
default* to keep using the grid operator's default product.

## 📊 Entities

Each configured energy type becomes one device (`E-Control Strom Bezug`,
`E-Control Strom Einspeisung`, `E-Control Gas`) with the following entities:

| Entity | Unit | Device class | Description |
| :--- | :--- | :--- | :--- |
| Cheapest offer | € | `monetary` | Yearly cost of the cheapest offer, with all offer details as attributes. |
| Cheapest offer price per kWh | ct/kWh | — | All-in price of that offer, derived from the yearly cost. |
| Own product | € | `monetary` | Yearly cost of the product the comparison is made against. |
| Possible saving | € | `monetary` | Maximum saving of the comparison. |
| Offers | — | diagnostic | Number of priced offers, with the full list as attributes. |

The *Own product* and *Possible saving* entities only exist once the interface has
returned the configured product in a comparison.

### Attributes of the offers sensor

| Attribute | Meaning |
| :--- | :--- |
| `zip_code`, `customer_group`, `energy_type`, `source` | The query this result belongs to. |
| `consumption_kwh`, `reference_period`, `include_switching_discounts` | The assumptions of the calculation. |
| `grid_operator`, `grid_operator_id`, `grid_area_id` | The resolved grid operator. |
| `offer_count`, `price_range_from`, `price_range_to` | Number of priced offers and the price range they cover. |
| `last_successful_update` | Timestamp of the comparison. |
| `offers` | The price-sorted offer list, capped at the configured *Offers in the attributes*. |

Every entry of `offers` carries `brand`, `product`, `annual_cost_eur`, `price_ct_per_kwh`,
`saving_eur`, `extra_cost_eur`, `supplier`, `price_guarantee_months`,
`price_guarantee_until`, `switch_url`, `flags`, `renewable_share` and `is_current_product`.

### Attributes of an unavailable entity

`failed_reason` explains why this energy type has no result, for example
`Postal code 1010 is not served for power_feed_in`. The other energy types of the same
entry are unaffected.

## 🔎 Notes on the data

* **All prices are gross** (including taxes and levies) and refer to the configured yearly
  consumption — a tariff comparison is only meaningful together with a consumption.
* The interface only reports **yearly totals**. The `ct/kWh` value is the frontend's own
  client side division (`annual cost ÷ consumption`), reproduced here for convenience.
* `annual_saving` is never negative on the interface side; offers that are more expensive
  than the comparison product carry their difference in `extra_cost_eur` instead.
* Offers without a calculable price (the calculator shows *"Komplexe Preisgestaltung"*)
  are excluded from the sensors so that a EUR 0 offer cannot win the comparison.
* **Strom Einspeisung** uses the electricity endpoints with
  `firstMeterOptions.productType = FEED_IN`. On the reference grid area the public
  interface answered `500 RCGATE_UNK01` for that combination, so treat this category as
  **experimental**: it may work for your grid operator, and if it does not, the entity
  reports the reason and the rest of the integration continues to work.

## 🧹 Troubleshooting

| Symptom | Explanation |
| :--- | :--- |
| Setup is retried and the log reports *not ready* | The public interface was unreachable or the postal code is not served. The entry retries automatically. |
| An energy type is unavailable | Read `failed_reason`. For feed-in this is expected for grid areas where the interface has no data. |
| The saving is `0 €` | The configured product is already the cheapest offer, or the interface did not return your product. Check *Product to compare against* in the options. |
| Nothing is offered for a comparison | The comparison depends on the grid area; some operators have few or no products in the calculator. |

Enable debug logging for details:

```yaml
logger:
  logs:
    custom_components.econtrol: debug
```

## 🤝 Contributing

Issues and pull requests are welcome. The wiki documents the architecture and the interface
contract in enough detail to extend the integration; please keep the numbered architecture
decisions (`AD-x`) in the Architecture Design Document up to date when changing a design.

## 📄 License

This project is licensed under the **GNU General Public License v3.0 or later** — see
[LICENSE](LICENSE).

---

*This is a community project. It is not affiliated with, endorsed by or supported by
E-Control, Austria's Energie-Control Austria für die Regulierung der Elektrizitäts- und
Erdgaswirtschaft, or by any of the energy suppliers whose tariffs are compared.*
