import os
import sys
import struct
import ast
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand


def parse_po_file(filepath):
    entries = {}
    current_msgid = None
    current_msgstr = None
    state = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('msgid '):
                if current_msgid is not None and current_msgstr is not None:
                    entries[current_msgid] = current_msgstr
                val_str = line[6:].strip()
                current_msgid = ast.literal_eval(val_str)
                current_msgstr = ""
                state = 'msgid'
            elif line.startswith('msgstr '):
                val_str = line[7:].strip()
                current_msgstr = ast.literal_eval(val_str)
                state = 'msgstr'
            elif line.startswith('"') and line.endswith('"'):
                val = ast.literal_eval(line)
                if state == 'msgid':
                    current_msgid += val
                elif state == 'msgstr':
                    current_msgstr += val

    if current_msgid is not None and current_msgstr is not None:
        entries[current_msgid] = current_msgstr

    return entries


def generate_mo(entries, mo_path):
    keys = sorted(entries.keys())
    offsets = []
    ids = b''
    strs = b''

    for k in keys:
        v = entries[k]
        k_enc = k.encode('utf-8')
        v_enc = v.encode('utf-8')
        offsets.append((len(ids), len(k_enc), len(strs), len(v_enc)))
        ids += k_enc + b'\x00'
        strs += v_enc + b'\x00'

    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)

    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets.append((l1, o1 + keystart))
        voffsets.append((l2, o2 + valuestart))

    header = struct.pack(
        "Iiiiiii",
        0x950412de,  # Magic number
        0,           # Version
        len(keys),   # Number of strings
        7 * 4,       # Offset of original strings table
        7 * 4 + len(keys) * 8,  # Offset of translation strings table
        0,           # Size of hashing table
        0            # Offset of hashing table
    )

    output = bytearray(header)
    for l, o in koffsets:
        output += struct.pack("ii", l, o)
    for l, o in voffsets:
        output += struct.pack("ii", l, o)
    output += ids
    output += strs

    os.makedirs(os.path.dirname(mo_path), exist_ok=True)
    with open(mo_path, 'wb') as f:
        f.write(output)
    return len(keys)


class Command(BaseCommand):
    help = 'Compiles all gettext .po catalogs into binary .mo files without requiring gettext CLI'

    def handle(self, *args, **options):
        locale_root = Path(settings.BASE_DIR) / 'locale'
        compiled_count = 0

        for po_path in locale_root.glob('**/LC_MESSAGES/*.po'):
            mo_path = po_path.with_suffix('.mo')
            entries = parse_po_file(str(po_path))
            string_count = generate_mo(entries, str(mo_path))
            self.stdout.write(self.style.SUCCESS(
                f"Compiled {string_count} strings for {po_path.parent.parent.name} -> {mo_path}"
            ))
            compiled_count += 1

        if compiled_count == 0:
            self.stdout.write(self.style.WARNING("No .po files found to compile."))
