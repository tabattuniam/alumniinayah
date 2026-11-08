import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "data", "alumni.db")


def get_con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    con = get_con()
    with con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS admin (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nama     TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS alumni (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            -- Data Pribadi
            nama_lengkap    TEXT NOT NULL,
            nama_panggilan  TEXT,
            jenis_kelamin   TEXT,   -- L / P
            tempat_lahir    TEXT,
            tanggal_lahir   TEXT,
            foto            TEXT,   -- filename
            -- Data Pesantren
            tahun_masuk     INTEGER,
            tahun_keluar    INTEGER,
            angkatan        INTEGER,
            program         TEXT,   -- Tahfidz / Kitab / Umum / dll
            kelas_terakhir  TEXT,
            no_induk        TEXT,
            -- Kontak & Domisili
            no_hp           TEXT,
            email           TEXT,
            alamat          TEXT,
            desa            TEXT,
            kecamatan       TEXT,
            kota            TEXT,
            provinsi        TEXT,
            -- Pendidikan & Karier
            pendidikan_terakhir TEXT,
            nama_instansi   TEXT,
            pekerjaan       TEXT,
            tempat_kerja    TEXT,
            -- Sosial Media
            instagram       TEXT,
            facebook        TEXT,
            -- Data Orang Tua / Wali
            nama_ayah       TEXT,
            nama_ibu        TEXT,
            no_hp_ortu      TEXT,
            pekerjaan_ayah  TEXT,
            pekerjaan_ibu   TEXT,
            alamat_ortu     TEXT,
            kota_ortu       TEXT,
            -- Meta
            status          TEXT DEFAULT 'aktif',  -- aktif / nonaktif
            verified        INTEGER DEFAULT 0,
            catatan         TEXT,
            created_at      TEXT DEFAULT (datetime('now','localtime')),
            updated_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS pengumuman (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            judul      TEXT NOT NULL,
            isi        TEXT NOT NULL,
            admin_id   INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """)
    # Buat admin default jika belum ada
    row = con.execute("SELECT id FROM admin WHERE username='admin'").fetchone()
    if not row:
        import hashlib
        pw = hashlib.sha256("admin123".encode()).hexdigest()
        with con:
            con.execute("INSERT INTO admin (username, password, nama) VALUES ('admin', ?, 'Administrator')", (pw,))
    con.close()


# ── Admin ──────────────────────────────────────────────────────────────────

def get_admin(username: str):
    con = get_con()
    row = con.execute("SELECT * FROM admin WHERE username=?", (username,)).fetchone()
    con.close()
    return dict(row) if row else None


def update_admin_password(admin_id: int, pw_hash: str):
    con = get_con()
    with con:
        con.execute("UPDATE admin SET password=? WHERE id=?", (pw_hash, admin_id))
    con.close()


# ── Alumni ─────────────────────────────────────────────────────────────────

def list_alumni(search: str = "", angkatan: int = None, program: str = "",
               provinsi: str = "", kota: str = "", kecamatan: str = "", desa: str = "",
               include_pending: bool = False):
    con = get_con()
    if include_pending:
        q = "SELECT * FROM alumni WHERE status != 'ditolak'"
    else:
        q = "SELECT * FROM alumni WHERE status = 'aktif'"
    params = []
    if search:
        q += " AND (nama_lengkap LIKE ? OR nama_panggilan LIKE ? OR no_induk LIKE ? OR kota LIKE ?)"
        s = f"%{search}%"
        params += [s, s, s, s]
    if angkatan:
        q += " AND tahun_masuk=?"
        params.append(angkatan)
    if program:
        q += " AND program=?"
        params.append(program)
    if provinsi:
        q += " AND provinsi=?"
        params.append(provinsi)
    if kota:
        q += " AND kota=?"
        params.append(kota)
    if kecamatan:
        q += " AND kecamatan LIKE ?"
        params.append(f"%{kecamatan}%")
    if desa:
        q += " AND desa LIKE ?"
        params.append(f"%{desa}%")
    q += " ORDER BY angkatan DESC, nama_lengkap"
    rows = con.execute(q, params).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_provinsi():
    con = get_con()
    rows = con.execute(
        "SELECT DISTINCT provinsi FROM alumni WHERE status='aktif' AND provinsi IS NOT NULL AND provinsi!='' ORDER BY provinsi"
    ).fetchall()
    con.close()
    return [r["provinsi"] for r in rows]


def list_kota(provinsi: str = ""):
    con = get_con()
    if provinsi:
        rows = con.execute(
            "SELECT DISTINCT kota FROM alumni WHERE status='aktif' AND kota IS NOT NULL AND kota!='' AND provinsi=? ORDER BY kota",
            (provinsi,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT DISTINCT kota FROM alumni WHERE status='aktif' AND kota IS NOT NULL AND kota!='' ORDER BY kota"
        ).fetchall()
    con.close()
    return [r["kota"] for r in rows]


def list_pending():
    con = get_con()
    rows = con.execute(
        "SELECT * FROM alumni WHERE status='pending' ORDER BY created_at DESC"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def count_pending():
    con = get_con()
    n = con.execute("SELECT COUNT(*) FROM alumni WHERE status='pending'").fetchone()[0]
    con.close()
    return n


def approve_alumni(alumni_id: int):
    con = get_con()
    with con:
        con.execute("UPDATE alumni SET status='aktif', updated_at=datetime('now','localtime') WHERE id=?", (alumni_id,))
    con.close()


def reject_alumni(alumni_id: int):
    con = get_con()
    with con:
        con.execute("UPDATE alumni SET status='ditolak', updated_at=datetime('now','localtime') WHERE id=?", (alumni_id,))
    con.close()


def get_alumni(alumni_id: int):
    con = get_con()
    row = con.execute("SELECT * FROM alumni WHERE id=?", (alumni_id,)).fetchone()
    con.close()
    return dict(row) if row else None


def create_alumni(data: dict) -> int:
    con = get_con()
    cols = list(data.keys())
    vals = list(data.values())
    ph = ",".join("?" * len(cols))
    with con:
        cur = con.execute(
            f"INSERT INTO alumni ({','.join(cols)}) VALUES ({ph})", vals
        )
    con.close()
    return cur.lastrowid


def update_alumni(alumni_id: int, data: dict):
    con = get_con()
    data["updated_at"] = "datetime('now','localtime')"
    sets = []
    vals = []
    for k, v in data.items():
        if k == "updated_at":
            sets.append(f"{k}=datetime('now','localtime')")
        else:
            sets.append(f"{k}=?")
            vals.append(v)
    vals.append(alumni_id)
    with con:
        con.execute(f"UPDATE alumni SET {','.join(sets)} WHERE id=?", vals)
    con.close()


def delete_alumni(alumni_id: int):
    con = get_con()
    with con:
        con.execute("DELETE FROM alumni WHERE id=?", (alumni_id,))
    con.close()


def count_alumni():
    con = get_con()
    total = con.execute("SELECT COUNT(*) FROM alumni WHERE status='aktif'").fetchone()[0]
    per_angkatan = con.execute(
        "SELECT tahun_masuk as angkatan, COUNT(*) as jml FROM alumni WHERE status='aktif' AND tahun_masuk IS NOT NULL GROUP BY tahun_masuk ORDER BY tahun_masuk ASC"
    ).fetchall()
    per_program = con.execute(
        "SELECT program, COUNT(*) as jml FROM alumni WHERE status='aktif' AND program IS NOT NULL AND program!='' GROUP BY program ORDER BY jml DESC"
    ).fetchall()
    per_provinsi = con.execute(
        "SELECT provinsi, COUNT(*) as jml FROM alumni WHERE status='aktif' AND provinsi IS NOT NULL AND provinsi!='' GROUP BY provinsi ORDER BY jml DESC"
    ).fetchall()
    per_pekerjaan = con.execute(
        "SELECT pekerjaan, COUNT(*) as jml FROM alumni WHERE status='aktif' AND pekerjaan IS NOT NULL AND pekerjaan!='' GROUP BY pekerjaan ORDER BY jml DESC LIMIT 8"
    ).fetchall()
    con.close()
    return {
        "total": total,
        "per_angkatan": [dict(r) for r in per_angkatan],
        "per_program": [dict(r) for r in per_program],
        "per_provinsi": [dict(r) for r in per_provinsi],
        "per_pekerjaan": [dict(r) for r in per_pekerjaan],
    }


def list_angkatan():
    con = get_con()
    # Kolom angkatan kosong, pakai tahun_masuk sebagai acuan angkatan
    rows = con.execute(
        "SELECT DISTINCT tahun_masuk FROM alumni WHERE tahun_masuk IS NOT NULL AND status='aktif' ORDER BY tahun_masuk DESC"
    ).fetchall()
    con.close()
    return [r["tahun_masuk"] for r in rows]


# ── Pengumuman ─────────────────────────────────────────────────────────────

def list_pengumuman():
    con = get_con()
    rows = con.execute("SELECT * FROM pengumuman ORDER BY created_at DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_pengumuman(judul: str, isi: str, admin_id: int):
    con = get_con()
    with con:
        con.execute("INSERT INTO pengumuman (judul, isi, admin_id) VALUES (?,?,?)", (judul, isi, admin_id))
    con.close()


def delete_pengumuman(pid: int):
    con = get_con()
    with con:
        con.execute("DELETE FROM pengumuman WHERE id=?", (pid,))
    con.close()
