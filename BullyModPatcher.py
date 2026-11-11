"""Bully Master Mod ISO patcher. Python 3, standard library only."""
import os
import queue
import shutil
import struct
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

SECTOR = 2048
# (ISO path, path relative to selected MasterMod folder)
FILES = [
    ('ACT/ACT.IMG', 'ACT/ACT.IMG'),
    ('ACT/ACT.DIR', 'ACT/ACT.dir'),
    ('SCRIPTS/SCRIPTS.IMG', 'Scripts/Scripts.img'),
    ('SCRIPTS/SCRIPTS.DIR', 'Scripts/Scripts.dir'),
    ('DAT/TRIGGER.IMG', 'DAT/Trigger.img'),
    ('DAT/TRIGGER.DIR', 'DAT/Trigger.dir'),
    ('CONFIG/TEXT/AMERICAN.IMG', 'Config/Text/American.img'),
    ('CONFIG/TEXT/AMERICAN.DIR', 'Config/Text/American.dir'),
    ('CONFIG/DAT/OBJECT.DAT', 'Config/dat/object.dat'),
]


def resolve_mod_file(root, relative):
    path = Path(root)
    for part in relative.split('/'):
        if not path.is_dir():
            return path / part
        match = next((item for item in path.iterdir() if item.name.casefold() == part.casefold()), None)
        path = match if match is not None else path / part
    return path


def u32(data, off):
    return struct.unpack_from('<I', data, off)[0]


def both32(value):
    return struct.pack('<I', value) + struct.pack('>I', value)


def read_at(f, pos, count):
    f.seek(pos)
    result = f.read(count)
    if len(result) != count:
        raise ValueError('Unexpected end of ISO')
    return result


def write_at(f, pos, data):
    f.seek(pos)
    f.write(data)


def descriptors(f):
    result = []
    for sector in range(16, 48):
        d = read_at(f, sector * SECTOR, SECTOR)
        if d[1:6] != b'CD001':
            raise ValueError('Not a supported ISO 9660 image (missing CD001 descriptor)')
        result.append((sector, d))
        if d[0] == 255:
            break
    else:
        raise ValueError('ISO descriptor terminator not found')
    primary = next(((s, d) for s, d in result if d[0] == 1), None)
    if primary is None:
        raise ValueError('Primary ISO 9660 descriptor missing')
    return result, primary


def directory_entries(f, lba, length, visited, prefix=''):
    key = (lba, length)
    if key in visited:
        return []
    visited.add(key)
    if length > 32 * 1024 * 1024:
        raise ValueError('Unexpectedly large ISO directory')
    raw = read_at(f, lba * SECTOR, length)
    entries = []
    pos = 0
    while pos < length:
        size = raw[pos]
        if not size:
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        if size < 34 or pos + size > length or pos % SECTOR + size > SECTOR:
            raise ValueError('Invalid ISO directory record')
        record = raw[pos:pos + size]
        name_len = record[32]
        name = record[33:33 + name_len].decode('ascii', errors='replace')
        if name not in ('\x00', '\x01'):
            name = name.split(';')[0].upper()
            path = f'{prefix}/{name}'.strip('/')
            entry = dict(path=path, position=lba * SECTOR + pos,
                         lba=u32(record, 2), length=u32(record, 10),
                         flags=record[25])
            entries.append(entry)
            if record[25] & 0x02:
                entries.extend(directory_entries(f, entry['lba'], entry['length'], visited, path))
        pos += size
    return entries


def inspect(f):
    descs, (pvd_sector, pvd) = descriptors(f)
    root_lba = u32(pvd, 156 + 2)
    root_length = u32(pvd, 156 + 10)
    entries = directory_entries(f, root_lba, root_length, set())
    return descs, entries


def transfer(src, dst, start, length, progress=None):
    src.seek(start)
    remaining = length
    while remaining:
        block = src.read(min(4 * 1024 * 1024, remaining))
        if not block:
            raise ValueError('Unexpected end while copying ISO')
        dst.write(block)
        remaining -= len(block)
        if progress:
            progress(len(block))


def replace_one(source, destination, internal_path, replacement, progress=None):
    """Create a new ISO, shifting ISO9660 extents after the replaced file."""
    with open(source, 'rb') as src:
        descs, entries = inspect(src)
        matches = [e for e in entries if e['path'] == internal_path.upper()]
        if len(matches) != 1:
            raise ValueError(f'Expected one {internal_path} in ISO, found {len(matches)}')
        target = matches[0]
        if target['flags'] & 0x80:
            raise ValueError('Multi-extent ISO files are not supported')
        old_lba, old_size = target['lba'], target['length']
        old_sectors = (old_size + SECTOR - 1) // SECTOR
        new_size = os.path.getsize(replacement)
        new_sectors = (new_size + SECTOR - 1) // SECTOR
        delta = new_sectors - old_sectors
        boundary = old_lba + old_sectors
        file_size = os.path.getsize(source)
        if file_size % SECTOR:
            raise ValueError('ISO file length is not a multiple of 2048 bytes')
        total_sectors = file_size // SECTOR
        if boundary > total_sectors:
            raise ValueError('Target extent is outside the ISO')
        if not (0 < total_sectors + delta < 2**32):
            raise ValueError('Resulting ISO is outside supported size limits')
        # Directory/path-table metadata must not overlap the target's data extent.
        for e in entries:
            if e['flags'] & 2 and e['lba'] < boundary and e['lba'] + (e['length'] + SECTOR - 1) // SECTOR > old_lba:
                raise ValueError('Target overlaps directory metadata')
        def shift_lba(lba):
            return lba + delta if lba >= boundary else lba
        def shift_pos(pos):
            return pos + delta * SECTOR if pos >= boundary * SECTOR else pos
        with open(destination, 'w+b') as dst:
            transfer(src, dst, 0, old_lba * SECTOR, progress)
            with open(replacement, 'rb') as repl:
                transfer(repl, dst, 0, new_size, progress)
            padding = new_sectors * SECTOR - new_size
            if padding:
                dst.write(b'\x00' * padding)
            transfer(src, dst, boundary * SECTOR, file_size - boundary * SECTOR, progress)
            # Update all directory entries, including parent directory pointers.
            for e in entries:
                if e['path'] == internal_path.upper():
                    write_at(dst, shift_pos(e['position']) + 10, both32(new_size))
                elif delta and e['lba'] >= boundary:
                    write_at(dst, shift_pos(e['position']) + 2, both32(shift_lba(e['lba'])))
            # Update the '.' and '..' directory records, too.
            if delta:
                directory_lbas = set()
                for _, d in descs:
                    if d[0] in (1, 2):
                        directory_lbas.add((u32(d, 156 + 2), u32(d, 156 + 10)))
                directory_lbas.update((e['lba'], e['length']) for e in entries if e['flags'] & 2)
                for lba, length in directory_lbas:
                    raw = read_at(src, lba * SECTOR, min(length, SECTOR))
                    offset = 0
                    for _ in range(2):
                        rec_len = raw[offset]
                        if rec_len < 34:
                            break
                        rec = raw[offset:offset + rec_len]
                        if rec[32] == 1 and rec[33] in (0, 1):
                            entry_lba = u32(rec, 2)
                            if entry_lba >= boundary:
                                write_at(dst, shift_pos(lba * SECTOR + offset) + 2, both32(shift_lba(entry_lba)))
                        offset += rec_len
            # Update volume descriptors and both LE/BE path tables.
            for sector, d in descs:
                if d[0] not in (1, 2):
                    continue
                base = sector * SECTOR
                if delta:
                    write_at(dst, base + 80, both32(u32(d, 80) + delta))
                    root = u32(d, 156 + 2)
                    if root >= boundary:
                        write_at(dst, base + 156 + 2, both32(shift_lba(root)))
                table_len = u32(d, 132)
                for off, endian in ((140, '<'), (144, '<'), (148, '>'), (152, '>')):
                    lba = struct.unpack_from(endian + 'I', d, off)[0]
                    if not lba:
                        continue
                    if delta and lba >= boundary:
                        write_at(dst, base + off, struct.pack(endian + 'I', shift_lba(lba)))
                    if not delta:
                        continue
                    table = read_at(src, lba * SECTOR, table_len)
                    pos = 0
                    while pos + 8 <= len(table):
                        n = table[pos]
                        if not n:
                            break
                        old_extent = struct.unpack_from(endian + 'I', table, pos + 2)[0]
                        if old_extent >= boundary:
                            write_at(dst, shift_pos(lba * SECTOR + pos + 2),
                                     struct.pack(endian + 'I', shift_lba(old_extent)))
                        pos += 8 + n + (n & 1)
            dst.flush()
            os.fsync(dst.fileno())
    # Validate the resulting ISO directory can be parsed and the file has correct size.
    with open(destination, 'rb') as check:
        _, new_entries = inspect(check)
        found = [e for e in new_entries if e['path'] == internal_path.upper()]
        if len(found) != 1 or found[0]['length'] != new_size:
            raise ValueError('Post-write verification failed')


class App:
    def __init__(self, root):
        self.root = root
        root.title('Bully Master Mod ISO Patcher')
        root.geometry('770x495')
        root.minsize(690, 440)
        self.iso = tk.StringVar()
        self.mod = tk.StringVar()
        self.out = tk.StringVar()
        self.events = queue.Queue()
        outer = ttk.Frame(root, padding=18)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Bully Master Mod ISO Patcher', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Select the original USA PS2 ISO and the extracted MasterMod folder.').pack(anchor='w', pady=(3, 17))
        for label, var, kind in [('Original Bully ISO', self.iso, 'iso'), ('MasterMod folder', self.mod, 'folder'), ('New patched ISO', self.out, 'save')]:
            ttk.Label(outer, text=label).pack(anchor='w')
            line = ttk.Frame(outer)
            line.pack(fill='x', pady=(3, 12))
            ttk.Entry(line, textvariable=var).pack(side='left', fill='x', expand=True)
            ttk.Button(line, text='Browse…', command=lambda v=var, k=kind: self.browse(v, k)).pack(side='left', padx=(8, 0))
        self.button = ttk.Button(outer, text='Patch ISO', command=self.start)
        self.button.pack(anchor='w', pady=(1, 8))
        self.bar = ttk.Progressbar(outer, mode='determinate', maximum=len(FILES))
        self.bar.pack(fill='x')
        ttk.Label(outer, text='Activity log').pack(anchor='w', pady=(12, 3))
        self.log = tk.Text(outer, height=8, state='disabled', wrap='word', font=('Consolas', 9))
        self.log.pack(fill='both', expand=True)
        self.note('Your original ISO will not be modified. A separate output file is created.')
        root.after(100, self.poll)

    def browse(self, var, kind):
        if kind == 'folder':
            result = filedialog.askdirectory(title='Select MasterMod folder')
        elif kind == 'iso':
            result = filedialog.askopenfilename(title='Select original Bully ISO', filetypes=[('ISO images', '*.iso'), ('All files', '*.*')])
        else:
            result = filedialog.asksaveasfilename(title='Save patched ISO', defaultextension='.iso',
                                                   initialfile='Bully (USA) Master Mod.iso', filetypes=[('ISO images', '*.iso')])
        if result:
            var.set(result)

    def note(self, msg):
        self.log.config(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def start(self):
        iso, mod, out = map(lambda x: x.get().strip(), (self.iso, self.mod, self.out))
        if not Path(iso).is_file() or not Path(mod).is_dir() or not out:
            messagebox.showerror('Missing paths', 'Select an existing ISO, a MasterMod folder, and an output ISO.')
            return
        if os.path.abspath(iso).lower() == os.path.abspath(out).lower():
            messagebox.showerror('Unsafe output', 'Output must have a different filename from the original ISO.')
            return
        if Path(out).exists():
            messagebox.showerror('Output exists', 'Choose a new output filename; existing files are never overwritten.')
            return
        missing = [rel for _, rel in FILES if not resolve_mod_file(mod, rel).is_file()]
        if missing:
            messagebox.showerror('Missing mod files', 'These expected files are missing:\n' + '\n'.join(missing) + '\n\nCheck folder names and choose the correct MasterMod folder.')
            return
        self.button.config(state='disabled')
        self.bar['value'] = 0
        self.note('Starting. This can take several minutes and needs extra free disk space.')
        threading.Thread(target=self.work, args=(iso, mod, out), daemon=True).start()

    def work(self, iso, mod, out):
        temporary = []
        current = iso
        try:
            out_parent = Path(out).parent
            if not out_parent.exists():
                raise ValueError('Output directory does not exist')
            # Keep intermediates beside output; no original ISO is ever changed.
            for i, (internal, rel) in enumerate(FILES, 1):
                self.events.put(('log', f'[{i}/{len(FILES)}] Replacing {internal}'))
                fd, next_file = tempfile.mkstemp(prefix='bully_patch_', suffix='.iso', dir=out_parent)
                os.close(fd)
                temporary.append(next_file)
                try:
                    replace_one(current, next_file, internal, str(resolve_mod_file(mod, rel)))
                except Exception:
                    raise
                if current in temporary and current != next_file:
                    os.unlink(current)
                    temporary.remove(current)
                current = next_file
                self.events.put(('progress', i))
            os.replace(current, out)
            temporary.remove(current)
            self.events.put(('done', f'Finished: {out}\nTest the ISO in PCSX2 before deleting any backups.'))
        except Exception as exc:
            self.events.put(('error', str(exc)))
        finally:
            for p in temporary:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'progress':
                    self.bar['value'] = value
                elif kind == 'log':
                    self.note(value)
                else:
                    self.note(value)
                    self.button.config(state='normal')
                    if kind == 'error':
                        messagebox.showerror('Patch failed', value)
                    else:
                        messagebox.showinfo('Completed', value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()