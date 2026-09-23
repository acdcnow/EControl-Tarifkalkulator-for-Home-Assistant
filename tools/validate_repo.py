"""Static consistency checks that do not need a Home Assistant installation.

The script is intentionally dependency free (standard library only) so it can run
on a bare checkout. It verifies:

* every JSON file of the repository parses,
* ``strings.json`` is byte identical to ``translations/en.json``
  (hassfest validates both, and a drift between them is a review finding),
* all translation files share the key structure of ``strings.json``,
* the manifest key order follows the hassfest rule
  (``domain``, ``name``, then alphabetical),
* every translation key that the code relies on actually exists, and
* no translation value contains a URL, HTML or an invalid placeholder
  (all of which hassfest rejects).

Run with:  python tools/validate_repo.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from string import Formatter

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "econtrol"

RE_URL = re.compile(
    r"(((ftp|ftps|scp|http|https|mqtt|mqtts|socket|socks5)://|www\.)"
    r"[a-z0-9]+([\-.][a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(/.*)?)",
    re.IGNORECASE,
)
RE_HTML = re.compile(r"<[a-z/][^>]*>", re.IGNORECASE)

failures: list[str] = []


def fail(message: str) -> None:
    """Record a failed check."""
    failures.append(message)


def check(condition: bool, message: str) -> None:
    """Record a failure when ``condition`` is false."""
    if not condition:
        fail(message)


def load(path: Path) -> dict:
    """Load a JSON file and fail when it is malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        fail(f"{path.relative_to(ROOT)}: {err}")
        return {}


def flatten(data: dict, prefix: str = "") -> dict[str, str]:
    """Return all leaf values of a translation tree, keyed by dotted path."""
    flat: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


def get(data: dict, path: str) -> object | None:
    """Return the value at ``path`` in a nested dictionary."""
    node: object = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def check_translation_values(name: str, data: dict) -> None:
    """Apply the hassfest value rules to every string of a translation file."""
    for key, value in flatten(data).items():
        if not isinstance(value, str):
            fail(f"{name}: {key} is not a string")
            continue
        if value != value.strip():
            fail(f"{name}: {key} has leading or trailing whitespace")
        if RE_HTML.search(value):
            fail(f"{name}: {key} contains HTML")
        if RE_URL.search(value):
            fail(f"{name}: {key} contains a URL (use a description placeholder)")
        for _, field_name, _, _ in Formatter().parse(value):
            if field_name and not field_name.isidentifier():
                fail(f"{name}: {key} has the invalid placeholder {field_name}")


def check_manifest() -> None:
    """Verify the manifest key order and the mandatory keys."""
    manifest = load(INTEGRATION / "manifest.json")
    keys = list(manifest)
    expected = ["domain", "name", *sorted(key for key in keys if key not in {"domain", "name"})]
    check(
        keys == expected,
        f"manifest.json: key order is {keys}, hassfest expects {expected}",
    )
    for key in ("domain", "name", "version", "documentation", "codeowners", "iot_class"):
        check(key in manifest, f"manifest.json: missing the key {key}")


def check_strings_are_identical() -> None:
    """Verify that strings.json and the English translation do not drift."""
    strings = INTEGRATION / "strings.json"
    english = INTEGRATION / "translations" / "en.json"
    if strings.read_bytes() != english.read_bytes():
        fail("strings.json and translations/en.json differ byte for byte")


def check_translation_structure(files: dict[str, dict], reference: dict) -> None:
    """Verify that every translation file mirrors the reference structure."""
    expected = set(flatten(reference))
    for name, data in files.items():
        missing = expected - set(flatten(data))
        if missing:
            fail(f"{name}: missing {', '.join(sorted(missing))}")


def collect_sensor_keys() -> set[str]:
    """Return the translation keys of the sensor descriptions."""
    source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    return set(re.findall(r'translation_key="([a-z0-9_]+)"', source))


def collect_flow_keys() -> tuple[set[str], set[str], set[str], set[str]]:
    """Return the error keys, abort reasons, menu options and selector keys."""
    source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    errors = set(re.findall(r'errors\[[^\]]+\] = "([a-z0-9_]+)"', source))
    aborts = set(re.findall(r'async_abort\(reason="([a-z0-9_]+)"', source))
    menus = set(re.findall(r'"([a-z0-9_]+)"', re.search(r"menu_options=\[[^\]]*\]", source).group(0)))
    selectors = set(re.findall(r"translation_key=([A-Z_]+)", source))
    return errors, aborts, menus, selectors


def main() -> int:
    """Run all checks and print a report."""
    strings = load(INTEGRATION / "strings.json")
    check(strings.get("config"), "strings.json: no config section")
    check(strings.get("options"), "strings.json: no options section")
    check(strings.get("entity"), "strings.json: no entity section")

    translations = {
        path.name: load(path)
        for path in sorted((INTEGRATION / "translations").glob("*.json"))
    }
    for name, data in translations.items():
        check_translation_values(name, data)
    check_translation_structure(
        {name: data for name, data in translations.items() if name != "en.json"}, strings
    )
    check_strings_are_identical()
    check_manifest()

    # Translation keys the code relies on.
    required = [f"entity.sensor.{key}.name" for key in collect_sensor_keys()]
    errors, _aborts, menus, _selectors = collect_flow_keys()
    required += [f"config.error.{key}" for key in errors]
    required += [f"options.step.init.menu_options.{key}" for key in menus]
    required += [
        "config.abort.already_configured",
        "options.abort.no_products",
        "config.step.user.title",
        "config.step.user.data.source",
        "config.step.user.data.zip_code",
        "config.step.user.data.customer_group",
        "config.step.user.data.energy_types",
        "config.step.partner.title",
        "config.step.partner.data.username",
        "config.step.partner.data.password",
        "config.step.partner.data.url",
        "config.step.consumption.title",
        "config.step.consumption.data.include_switching_discounts",
        "config.step.consumption.data.reference_period",
        "config.step.consumption.sections.consumption.name",
        "config.step.consumption.sections.consumption.data.power",
        "config.step.consumption.sections.consumption.data.power_feed_in",
        "config.step.consumption.sections.consumption.data.gas",
        "options.step.settings.title",
        "options.step.settings.data.scan_interval_hours",
        "options.step.settings.data.offer_count",
        "options.step.settings.sections.consumption.data.power",
        "options.step.product.title",
        "options.step.product.data.energy_type",
        "options.step.product_select.title",
        "options.step.product_select.description",
        "options.step.product_select.data.product",
        "selector.source.options.public",
        "selector.source.options.partner",
        "selector.energy_type_option.options.power",
        "selector.energy_type_option.options.power_feed_in",
        "selector.energy_type_option.options.gas",
        "selector.customer_group.options.home",
        "selector.customer_group.options.business",
        "selector.reference_period.options.one_year",
        "selector.reference_period.options.two_years",
        "selector.reference_period.options.three_years",
    ]
    for path in sorted(set(required)):
        check(get(strings, path) is not None, f"strings.json: missing {path}")

    # Constants that the config flow selects must have a translation too.
    const = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    literals = dict(re.findall(r'^([A-Z][A-Z0-9_]*): Final = "([^"]+)"', const, re.M))
    literals.update(re.findall(r'^    ([A-Z][A-Z0-9_]*) = "([^"]+)"', const, re.M))
    for name, key in (
        ("CUSTOMER_GROUPS", "customer_group"),
        ("REFERENCE_PERIODS", "reference_period"),
        ("ENERGY_TYPES", "energy_type_option"),
    ):
        block = re.search(rf"^{name}: Final = \(([^)]*)\)", const, re.MULTILINE | re.DOTALL)
        members = re.findall(r"\b[A-Z][A-Z0-9_]*\b", block.group(1)) if block else []
        check(bool(members), f"validate_repo.py: cannot read {name} from const.py")
        for member in members:
            value = literals.get(member)
            check(value is not None, f"const.py: {member} has no string value")
            if value is None:
                continue
            check(
                get(strings, f"selector.{key}.options.{value}") is not None,
                f"strings.json: missing selector.{key}.options.{value}",
            )

    if failures:
        print(f"FAILED ({len(failures)})\n")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
