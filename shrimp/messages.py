# Bot messages live in two plain text files you can edit: messages_vi.txt and messages_en.txt
import re
from pathlib import Path
from typing import Dict, Optional

CATALOG_DIR = Path(__file__).parent
LANGUAGES = ("vi", "en")

# every message key and the {placeholders} its text may use
KEYS: Dict[str, tuple] = {
    "photo.count_left_out": ("n", "k"),
    "photo.count": ("n",),
    "photo.size": ("cm", "size"),
    "photo.size_outside": ("cm",),
    "photo.rough": (),
    "photo.crowded": (),
    "photo.too_few": ("n", "min"),
    "photo.too_few_hint": (),
    "photo.no_reference": (),
    "photo.no_shrimp": (),
    "photo.saved": (),
    "photo.not_saved": (),
    "choose.bad_number_list": ("n",),
    "choose.bad_number_cmd": ("n",),
    "left_out.none": (),
    "left_out.caption": ("example",),
    "misc.no_pending": (),
    "misc.cancelled": (),
    "misc.expired": (),
    "misc.download_failed": (),
    "misc.cannot_process": (),
    "misc.sorry": (),
    "status.empty": (),
    "status.latest_date_data": ("date", "data"),
    "status.latest_data": ("data",),
    "status.latest_date": ("date",),
    "status.latest": (),
    "status.part_length": ("cm",),
    "status.part_size": ("size",),
    "status.slow": ("growth", "threshold"),
    "status.growing": ("growth",),
    "status.unclear": (),
    "status.not_enough": (),
    "status.price": ("size", "price"),
    "status.next_class": ("size", "gain", "days"),
    "status.next_class_days": ("days",),
    "status.breakeven": ("mm",),
    "status.stall_cost": ("cost",),
    "status.chart_link": ("link",),
    "setup.ask_name": ("name",),
    "setup.name_too_long": ("max",),
    "setup.ask_price": ("price",),
    "setup.bad_price": ("min", "max"),
    "setup.confirm": ("name", "price"),
    "setup.confirm_hint": (),
    "setup.saved": ("name", "price"),
    "setup.cancelled": (),
    "help.text": (),
    "button.save_sample": (),
    "button.show_left_out": (),
    "button.cancel": (),
    "button.add_all": (),
    "button.status": (),
    "button.help": (),
    "button.save": (),
    "button.keep": ("name",),
}


class MessageError(ValueError):
    pass


def parse_catalog(text: str, source: str) -> Dict[str, str]:
    # "=== key" starts a message, the lines after it are its text, ";;" lines are comments
    result: Dict[str, str] = {}
    key: Optional[str] = None
    lines: list = []

    def finish() -> None:
        if key is None:
            return
        body = "\n".join(lines).strip("\n")
        if not body.strip():
            raise MessageError(f"{source}: message {key} is empty")
        result[key] = body

    for line in text.splitlines():
        if line.startswith(";;"):
            continue
        if line.startswith("=== "):
            finish()
            key = line[4:].strip()
            if key in result:
                raise MessageError(f"{source}: message {key} appears twice")
            lines = []
        elif key is None:
            if line.strip():
                raise MessageError(f"{source}: text before the first '=== key' line: {line!r}")
        else:
            lines.append(line)
    finish()
    return result


def load_catalog(lang: str, directory: Optional[Path] = None) -> Dict[str, str]:
    # Read and check one language file; the error names the key and the problem
    if lang not in LANGUAGES:
        raise MessageError(f"unknown language {lang!r}, use one of {', '.join(LANGUAGES)}")
    path = (directory or CATALOG_DIR) / f"messages_{lang}.txt"
    catalog = parse_catalog(path.read_text(encoding="utf-8"), path.name)
    for key in catalog:
        if key not in KEYS:
            raise MessageError(f"{path.name}: unknown message {key}")
    for key, allowed in KEYS.items():
        if key not in catalog:
            raise MessageError(f"{path.name}: message {key} is missing")
        for name in set(re.findall(r"{(\w*)}", catalog[key])):
            if name not in allowed:
                shown = ", ".join("{" + a + "}" for a in allowed) or "none"
                raise MessageError(
                    f"{path.name}: message {key} uses {{{name}}}, allowed placeholders: {shown}"
                )
    return catalog


_lang = "vi"
_catalog: Dict[str, str] = load_catalog("vi")


def use(lang: str) -> None:
    # Switch the language of every message sent from now on
    global _lang, _catalog
    _catalog = load_catalog(lang)
    _lang = lang


def t(key: str, **values: object) -> str:
    # The text of one message with its placeholders filled in
    return _catalog[key].format(**values)


def num(value: float) -> str:
    # One decimal: 9,5 in Vietnamese, 9.5 in English
    text = f"{value:.1f}"
    return text.replace(".", ",") if _lang == "vi" else text


def money(value: int) -> str:
    # 45000: 45.000 in Vietnamese, 45,000 in English
    text = f"{value:,}"
    return text.replace(",", ".") if _lang == "vi" else text
