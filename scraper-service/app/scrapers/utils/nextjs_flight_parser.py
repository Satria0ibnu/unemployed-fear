"""Parser untuk React Server Components "Flight" wire format yang dipakai
Next.js App Router untuk streaming data lewat tag <script>self.__next_f.push(...).

Format ini BUKAN satu blok JSON — tiap <script> berisi potongan string yang
digabung jadi satu stream, lalu stream itu berisi banyak "chunk" berpola
`<id>:<payload>` back-to-back TANPA separator yang selalu konsisten:
- chunk biasa (JSON value / module reference) berakhir di newline berikutnya
- chunk teks panjang (`<id>:T<hex_length>,<teks mentah>`) diakhiri persis
  setelah <hex_length> BYTE (bukan karakter) teks mentah — teks ini bisa
  berisi newline asli di dalamnya, jadi TIDAK BOLEH di-split pakai "\\n" naif
- ada juga baris "hint" tanpa id sama sekali (`:HL[...]`) — dilewati begitu
  saja, tidak pernah direferensikan di tempat lain

Nilai yang dipecah ke chunk teks direferensikan di tempat lain sebagai string
"$<id>" (mis. "description":"$1f") — resolve_refs() mengganti referensi itu
dengan isi chunk aslinya.

Ditulis reusable karena pola ini kemungkinan muncul lagi di situs lain yang
pakai Next.js App Router (bukan cuma Kitalulus).
"""

import json
import re

from selectolax.parser import HTMLParser

_HEADER_RE = re.compile(r"([0-9a-fA-F]*):")
_TEXT_RE = re.compile(r"T([0-9a-fA-F]+),")
_REF_RE = re.compile(r"^\$([0-9a-fA-F]+)$")


def extract_flight_chunks(html: str) -> dict[str, str]:
    """Kumpulkan semua <script>self.__next_f.push([1,"..."])</script>,
    gabung jadi satu stream, lalu pecah jadi {chunk_id: payload_string}.
    """
    tree = HTMLParser(html)
    full_stream = ""
    for script_node in tree.css("script"):
        text = script_node.text()
        if not text or "self.__next_f.push(" not in text:
            continue
        start = text.find("push(") + len("push(")
        end = text.rfind(")")
        if end <= start:
            continue
        try:
            push_args = json.loads(text[start:end])
        except (ValueError, TypeError):
            continue
        if isinstance(push_args, list) and len(push_args) > 1 and isinstance(push_args[1], str):
            full_stream += push_args[1]

    return _split_chunks(full_stream)


def _split_chunks(stream: str) -> dict[str, str]:
    chunks: dict[str, str] = {}
    pos = 0
    length = len(stream)

    while pos < length:
        header = _HEADER_RE.match(stream, pos)
        if not header:
            break  # format tidak dikenali — berhenti, jangan menebak sisa stream

        chunk_id = header.group(1)
        rest_start = header.end()

        text_header = _TEXT_RE.match(stream, rest_start)
        if text_header:
            byte_length = int(text_header.group(1), 16)
            text_start = text_header.end()
            # Panjang di header itu byte UTF-8, bukan jumlah karakter Python —
            # slice di level byte dulu supaya benar untuk teks non-ASCII.
            remaining_bytes = stream[text_start:].encode("utf-8")
            payload_text = remaining_bytes[:byte_length].decode("utf-8", errors="replace")
            if chunk_id:
                chunks[chunk_id] = payload_text
            pos = text_start + len(payload_text)
            if pos < length and stream[pos] == "\n":
                pos += 1
        else:
            next_newline = stream.find("\n", rest_start)
            if next_newline == -1:
                next_newline = length
            if chunk_id:  # id kosong = baris hint (":HL[...]"), tidak direferensikan
                chunks[chunk_id] = stream[rest_start:next_newline]
            pos = next_newline + 1

    return chunks


def resolve_refs(value, chunks: dict[str, str]):
    """Ganti rekursif semua string "$<hex_id>" (referensi ke chunk teks lain)
    dengan isi chunk aslinya. String seperti "$Sreact.fragment" atau "$L1e"
    (ada huruf tepat setelah $) BUKAN referensi jenis ini, dibiarkan apa adanya.
    """
    if isinstance(value, dict):
        return {k: resolve_refs(v, chunks) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_refs(v, chunks) for v in value]
    if isinstance(value, str):
        match = _REF_RE.match(value)
        if match and match.group(1) in chunks:
            return chunks[match.group(1)]
        return value
    return value


def find_value_with_key(chunks: dict[str, str], key: str) -> dict | None:
    """Cari dict pertama (di kedalaman manapun, di chunk manapun yang valid
    JSON) yang punya `key`, resolve semua $-reference di dalamnya, lalu
    kembalikan. Dipakai supaya tidak perlu hardcode id chunk tertentu —
    id itu tidak stabil antar-deploy/versi Next.js.
    """
    for payload in chunks.values():
        stripped = payload.lstrip()
        if not stripped or stripped[0] not in "{[":
            continue  # bukan chunk JSON (module-reference "I[...]", dst)
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            continue
        found = _search(data, key)
        if found is not None:
            return resolve_refs(found, chunks)
    return None


def _search(value, key: str):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for v in value.values():
            result = _search(v, key)
            if result is not None:
                return result
    elif isinstance(value, list):
        for item in value:
            result = _search(item, key)
            if result is not None:
                return result
    return None
