"""Pano JSON'u çıkarma ve doğrulama (saf fonksiyonlar)."""
import json
import re

FORMAT = "makeurchoice.board"
MAX_OPTIONS = 100
MAX_FIELD = 20000

_FENCE = re.compile(r"```[ \t]*(?:json|JSON)?[ \t]*\r?\n(.*?)```", re.S)


class BoardError(ValueError):
    pass


def _str_field(obj, key, default="", label=None):
    v = obj.get(key)
    if v is None:
        return default
    if not isinstance(v, str):
        raise BoardError(f"'{label or key}' metin olmalı")
    if len(v) > MAX_FIELD:
        raise BoardError(f"'{label or key}' en fazla {MAX_FIELD} karakter olabilir")
    return v


def validate_board(obj):
    """Ham nesneyi doğrular; normalleştirilmiş board sözlüğü döndürür."""
    if not isinstance(obj, dict):
        raise BoardError("Pano bir JSON nesnesi olmalı")
    fmt = obj.get("format")
    if fmt is not None and fmt != FORMAT:
        raise BoardError(f"Desteklenmeyen format: {fmt!r}")
    ver = obj.get("version")
    if ver is not None:
        if isinstance(ver, bool) or not isinstance(ver, (int, float)):
            raise BoardError("'version' sayı olmalı")
        if ver > 1:
            raise BoardError(f"Desteklenmeyen pano sürümü: {ver}")
    title = _str_field(obj, "title").strip()
    if not title:
        raise BoardError("'title' boş olamaz")
    options = obj.get("options")
    if not isinstance(options, list):
        raise BoardError("'options' bir dizi olmalı")
    if len(options) > MAX_OPTIONS:
        raise BoardError(f"En fazla {MAX_OPTIONS} seçenek içe aktarılabilir")
    opts = []
    for i, o in enumerate(options, 1):
        if not isinstance(o, dict):
            raise BoardError(f"Seçenek {i} bir nesne olmalı")
        name = _str_field(o, "name", label=f"options[{i}].name").strip()
        if not name:
            raise BoardError(f"Seçenek {i} için 'name' boş olamaz")
        opts.append({
            "name": name,
            **{k: _str_field(o, k, label=f"options[{i}].{k}")
               for k in ("gains", "losses", "risks")},
        })
    status = obj.get("status", "open")
    if status is None:
        status = "open"
    if status not in ("open", "decided"):
        raise BoardError("'status' 'open' veya 'decided' olmalı")
    chosen = obj.get("chosen_option")
    if chosen is not None and not isinstance(chosen, str):
        raise BoardError("'chosen_option' metin veya null olmalı")
    return {
        "title": title,
        "notes": _str_field(obj, "notes"),
        "status": status,
        "chosen_option": chosen,
        "decision_reason": _str_field(obj, "decision_reason"),
        "options": opts,
    }


def _balanced_objects(text):
    """Metindeki üst düzey dengeli {...} alt dizilerini sırayla üretir."""
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth, j, in_str, esc = 0, i, False, False
        end = None
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
            j += 1
        if end is None:
            i += 1  # kapanmayan '{' — sonrakini dene
        else:
            yield text[i:end + 1]
            i = end + 1


def extract_board(text):
    """Serbest metinden ilk geçerli board'u çıkarır (normalleştirilmiş)."""
    if not isinstance(text, str) or not text.strip():
        raise BoardError("Metin boş")
    fenced = _FENCE.findall(text)
    candidates = list(reversed(fenced))
    if not candidates:
        candidates = list(_balanced_objects(text))
    if not candidates:
        raise BoardError("Metinde pano JSON'u bulunamadı")
    last_err = None
    for c in candidates:
        try:
            return validate_board(json.loads(c))
        except json.JSONDecodeError:
            last_err = BoardError("Pano JSON'u geçersiz")
        except BoardError as e:
            last_err = e
    raise last_err


def parse_import(body):
    """POST /api/import gövdesinden board üretir."""
    if isinstance(body.get("text"), str):
        return extract_board(body["text"])
    if "text" in body and "title" not in body:
        raise BoardError("'text' metin olmalı")
    return validate_board(body)
