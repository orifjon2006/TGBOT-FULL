"""Yordamchi funksiyalar — barcha modullar uchun umumiy."""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
#  HTML xavfsizlik
# ═══════════════════════════════════════════════════════════════════════════

def html_escape(value: str) -> str:
    """HTML maxsus belgilarni escape qilish."""
    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Pul formatlash
# ═══════════════════════════════════════════════════════════════════════════

def format_amount(value: Decimal | int | float | str) -> str:
    """Summani chiroyli formatda ko'rsatish: 26 000 000"""
    amount = Decimal(str(value))
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def parse_amount(text: str) -> Decimal:
    """Foydalanuvchi kiritgan summani Decimal ga o'girish."""
    cleaned = (
        text.strip()
        .replace(" ", "")
        .replace("\u00A0", "")
        .replace(",", ".")
    )
    if not cleaned:
        raise ValueError("Summa bo'sh bo'lishi mumkin emas.")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as e:
        raise ValueError("Summani to'g'ri formatda kiriting. Masalan: 26000000") from e
    if amount < 0:
        raise ValueError("Summa manfiy bo'lishi mumkin emas.")
    return amount.quantize(Decimal("0.01"))


# ═══════════════════════════════════════════════════════════════════════════
#  Telefon normalizatsiya
# ═══════════════════════════════════════════════════════════════════════════

def normalize_phone(text: str) -> str:
    """Telefon raqamni normalizatsiya qilish."""
    raw = text.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if raw.startswith("+"):
        normalized = "+" + digits
    else:
        normalized = digits
    if len(digits) < 7:
        raise ValueError("Telefon raqam juda qisqa ko'rinmoqda.")
    return normalized


# ═══════════════════════════════════════════════════════════════════════════
#  Matn yordamchilari
# ═══════════════════════════════════════════════════════════════════════════

def truncate(text: str, max_len: int = 40) -> str:
    """Uzun textni qisqartirish."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def split_long_text(text: str, chunk_size: int = 3500) -> list[str]:
    """Uzun xabarni Telegram limitiga sig'adigan qismlarga bo'lish."""
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    current = ""

    for block in text.split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(block) <= chunk_size:
                current = block
            else:
                for i in range(0, len(block), chunk_size):
                    chunks.append(block[i : i + chunk_size])
                current = ""

    if current:
        chunks.append(current)

    return chunks


def build_display_name(from_user) -> str:
    """Telegram foydalanuvchi ismini tuzish."""
    parts = [from_user.first_name or "", from_user.last_name or ""]
    full_name = " ".join(part.strip() for part in parts if part.strip()).strip()
    return full_name or from_user.username or f"user_{from_user.id}"


def now_ts() -> int:
    """Hozirgi vaqtning timestamp'i."""
    return int(time.time())


# ═══════════════════════════════════════════════════════════════════════════
#  Xizmat daraxti yordamchilari
# ═══════════════════════════════════════════════════════════════════════════

def get_tree_node_by_path(tree: dict, path_keys: list[str]) -> dict[str, Any] | None:
    """Daraxt bo'yicha yo'l orqali node topish."""
    if not path_keys:
        return None
    current = tree.get(path_keys[0])
    if current is None:
        return None
    for key in path_keys[1:]:
        current = current.get("children", {}).get(key)
        if current is None:
            return None
    return current


def build_tree_label_from_path(tree: dict, path_keys: list[str]) -> str:
    """Yo'ldan label matn tuzish: 'A > B > C'."""
    labels: list[str] = []
    current = tree.get(path_keys[0])
    if current is None:
        return ""
    labels.append(current["label"])
    for key in path_keys[1:]:
        current = current.get("children", {}).get(key)
        if current is None:
            break
        labels.append(current["label"])
    return " > ".join(labels)


def collect_tree_leaf_labels(tree: dict) -> list[str]:
    """Daraxtdagi barcha barg (leaf) labellarni yig'ish."""
    collected: list[str] = []

    def walk(node: dict[str, Any], labels_stack: list[str]) -> None:
        label = node["label"]
        current_stack = labels_stack + [label]
        children = node.get("children", {})
        if not children:
            collected.append(" > ".join(current_stack))
            return
        for child_node in children.values():
            walk(child_node, current_stack)

    for root_node in tree.values():
        walk(root_node, [])
    return collected
