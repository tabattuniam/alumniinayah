import os
import hashlib
import shutil
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import storage as db

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

FOTO_DIR = os.path.join("static", "foto_alumni")
os.makedirs(FOTO_DIR, exist_ok=True)

db.init_db()


def _r(request: Request, tmpl: str, **ctx):
    if "pending_count" not in ctx:
        ctx["pending_count"] = db.count_pending()
    return templates.TemplateResponse(request, tmpl, ctx)


def _admin_session(request: Request):
    sid = request.cookies.get("alumni_admin")
    if not sid:
        return None
    import json, base64
    try:
        data = json.loads(base64.b64decode(sid).decode())
        return data
    except Exception:
        return None


def _require_admin(request: Request):
    admin = _admin_session(request)
    if not admin:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return admin


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _ts(s):
    if not s:
        return ""
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").strftime("%d %b %Y %H:%M")
    except Exception:
        return s


templates.env.filters["ts"] = _ts


# ── Self-Registration Alumni ───────────────────────────────────────────────

@app.get("/daftar", response_class=HTMLResponse)
async def daftar_page(request: Request):
    angkatan_list = db.list_angkatan()
    return _r(request, "daftar.html", err="", ok="", angkatan_list=angkatan_list)


@app.post("/daftar", response_class=HTMLResponse)
async def daftar_submit(
    request: Request,
    nama_lengkap: str = Form(...),
    nama_panggilan: str = Form(""),
    jenis_kelamin: str = Form(""),
    tempat_lahir: str = Form(""),
    tanggal_lahir: str = Form(""),
    tahun_masuk: str = Form(""),
    tahun_keluar: str = Form(""),
    angkatan: str = Form(""),
    program: str = Form(""),
    no_hp: str = Form(""),
    email: str = Form(""),
    provinsi: str = Form(""),
    kota: str = Form(""),
    kecamatan: str = Form(""),
    desa: str = Form(""),
    pekerjaan: str = Form(""),
    nama_ayah: str = Form(""),
    nama_ibu: str = Form(""),
):
    def iv(v): return int(v) if str(v).isdigit() else None
    data = dict(
        nama_lengkap=nama_lengkap.strip(),
        nama_panggilan=nama_panggilan, jenis_kelamin=jenis_kelamin,
        tempat_lahir=tempat_lahir, tanggal_lahir=tanggal_lahir,
        tahun_masuk=iv(tahun_masuk), tahun_keluar=iv(tahun_keluar),
        angkatan=iv(angkatan), program=program,
        no_hp=no_hp, email=email,
        provinsi=provinsi, kota=kota, kecamatan=kecamatan, desa=desa,
        pekerjaan=pekerjaan,
        nama_ayah=nama_ayah, nama_ibu=nama_ibu,
        status="pending",
    )
    db.create_alumni(data)
    angkatan_list = db.list_angkatan()
    return _r(request, "daftar.html", err="", angkatan_list=angkatan_list,
              ok="Pendaftaran berhasil! Data Anda sedang menunggu verifikasi admin.")


# ── Landing / Direktori Publik ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    stats = db.count_alumni()
    pengumuman = db.list_pengumuman()[:5]
    return _r(request, "home.html", stats=stats, pengumuman=pengumuman)


@app.get("/statistik", response_class=HTMLResponse)
async def statistik_page(request: Request):
    stats = db.count_alumni()
    return _r(request, "statistik.html", stats=stats)


@app.get("/direktori", response_class=HTMLResponse)
async def direktori(
    request: Request,
    q: str = "",
    angkatan: str = "",
    program: str = "",
    provinsi: str = "",
    kota: str = "",
    kecamatan: str = "",
    desa: str = "",
):
    ang = int(angkatan) if angkatan.isdigit() else None
    alumni_list = db.list_alumni(
        search=q, angkatan=ang, program=program,
        provinsi=provinsi, kota=kota, kecamatan=kecamatan, desa=desa,
    )
    angkatan_list = db.list_angkatan()
    provinsi_list = db.list_provinsi()
    kota_list = db.list_kota(provinsi)
    stats = db.count_alumni()
    return _r(request, "direktori.html",
              alumni_list=alumni_list, angkatan_list=angkatan_list,
              provinsi_list=provinsi_list, kota_list=kota_list,
              q=q, angkatan=angkatan, program=program,
              provinsi=provinsi, kota=kota, kecamatan=kecamatan, desa=desa,
              total=len(alumni_list),
              provinsi_count=len(stats.get("per_provinsi", [])))


@app.get("/alumni/{alumni_id}", response_class=HTMLResponse)
async def alumni_detail(request: Request, alumni_id: int):
    alumni = db.get_alumni(alumni_id)
    if not alumni:
        raise HTTPException(404)
    return _r(request, "alumni_detail.html", alumni=alumni)


# ── Admin Login ────────────────────────────────────────────────────────────

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, err: str = ""):
    admin = _admin_session(request)
    if admin:
        return RedirectResponse("/admin", status_code=302)
    return _r(request, "admin_login.html", err=err)


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    admin = db.get_admin(username)
    if not admin or admin["password"] != _hash(password):
        return _r(request, "admin_login.html", err="Username atau password salah")
    import json, base64
    token = base64.b64encode(json.dumps({"id": admin["id"], "nama": admin["nama"], "username": admin["username"]}).encode()).decode()
    resp = RedirectResponse("/admin", status_code=302)
    resp.set_cookie("alumni_admin", token, httponly=True, max_age=86400 * 30)
    return resp


@app.get("/admin/logout")
async def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie("alumni_admin")
    return resp


# ── Admin Dashboard ────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    stats = db.count_alumni()
    pengumuman = db.list_pengumuman()
    return _r(request, "admin_dashboard.html", admin=admin, stats=stats, pengumuman=pengumuman)


# ── Admin Alumni ───────────────────────────────────────────────────────────

@app.get("/admin/alumni", response_class=HTMLResponse)
async def admin_alumni_list(
    request: Request,
    q: str = "",
    angkatan: str = "",
    program: str = "",
    ok: str = "",
    err: str = "",
):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    ang = int(angkatan) if angkatan.isdigit() else None
    alumni_list = db.list_alumni(search=q, angkatan=ang, program=program, include_pending=True)
    angkatan_list = db.list_angkatan()
    pending_count = db.count_pending()
    return _r(request, "admin_alumni.html", admin=admin,
              alumni_list=alumni_list, angkatan_list=angkatan_list,
              q=q, angkatan=angkatan, program=program,
              ok=ok, err=err, pending_count=pending_count)


@app.get("/admin/alumni/tambah", response_class=HTMLResponse)
async def admin_alumni_tambah_page(request: Request):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    return _r(request, "admin_alumni_form.html", admin=admin, mode="tambah", data={}, err="")


@app.post("/admin/alumni/tambah", response_class=HTMLResponse)
async def admin_alumni_tambah(
    request: Request,
    nama_lengkap: str = Form(...),
    nama_panggilan: str = Form(""),
    jenis_kelamin: str = Form(""),
    tempat_lahir: str = Form(""),
    tanggal_lahir: str = Form(""),
    tahun_masuk: str = Form(""),
    tahun_keluar: str = Form(""),
    angkatan: str = Form(""),
    program: str = Form(""),
    kelas_terakhir: str = Form(""),
    no_induk: str = Form(""),
    no_hp: str = Form(""),
    email: str = Form(""),
    alamat: str = Form(""),
    desa: str = Form(""),
    kecamatan: str = Form(""),
    kota: str = Form(""),
    provinsi: str = Form(""),
    pendidikan_terakhir: str = Form(""),
    nama_instansi: str = Form(""),
    pekerjaan: str = Form(""),
    tempat_kerja: str = Form(""),
    instagram: str = Form(""),
    facebook: str = Form(""),
    nama_ayah: str = Form(""),
    nama_ibu: str = Form(""),
    no_hp_ortu: str = Form(""),
    pekerjaan_ayah: str = Form(""),
    pekerjaan_ibu: str = Form(""),
    alamat_ortu: str = Form(""),
    provinsi_ortu: str = Form(""),
    kota_ortu: str = Form(""),
    catatan: str = Form(""),
    foto: UploadFile = File(None),
):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    foto_fn = ""
    if foto and foto.filename:
        ext = foto.filename.rsplit(".", 1)[-1].lower()
        if ext in ("jpg", "jpeg", "png", "webp"):
            import uuid
            foto_fn = f"{uuid.uuid4().hex}.{ext}"
            with open(os.path.join(FOTO_DIR, foto_fn), "wb") as f:
                shutil.copyfileobj(foto.file, f)

    def iv(v): return int(v) if str(v).isdigit() else None

    data = dict(
        nama_lengkap=nama_lengkap, nama_panggilan=nama_panggilan,
        jenis_kelamin=jenis_kelamin, tempat_lahir=tempat_lahir,
        tanggal_lahir=tanggal_lahir, foto=foto_fn,
        tahun_masuk=iv(tahun_masuk), tahun_keluar=iv(tahun_keluar),
        angkatan=iv(angkatan), program=program,
        kelas_terakhir=kelas_terakhir, no_induk=no_induk,
        no_hp=no_hp, email=email, alamat=alamat, desa=desa,
        kecamatan=kecamatan, kota=kota, provinsi=provinsi,
        pendidikan_terakhir=pendidikan_terakhir, nama_instansi=nama_instansi,
        pekerjaan=pekerjaan, tempat_kerja=tempat_kerja,
        instagram=instagram, facebook=facebook,
        nama_ayah=nama_ayah, nama_ibu=nama_ibu, no_hp_ortu=no_hp_ortu,
        pekerjaan_ayah=pekerjaan_ayah, pekerjaan_ibu=pekerjaan_ibu,
        alamat_ortu=alamat_ortu, provinsi_ortu=provinsi_ortu, kota_ortu=kota_ortu,
        catatan=catatan,
    )
    db.create_alumni(data)
    return RedirectResponse("/admin/alumni?ok=Alumni berhasil ditambahkan", status_code=302)


@app.get("/admin/alumni/{alumni_id}/edit", response_class=HTMLResponse)
async def admin_alumni_edit_page(request: Request, alumni_id: int):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    alumni = db.get_alumni(alumni_id)
    if not alumni:
        raise HTTPException(404)
    return _r(request, "admin_alumni_form.html", admin=admin, mode="edit", data=alumni, err="")


@app.post("/admin/alumni/{alumni_id}/edit", response_class=HTMLResponse)
async def admin_alumni_edit(
    request: Request,
    alumni_id: int,
    nama_lengkap: str = Form(...),
    nama_panggilan: str = Form(""),
    jenis_kelamin: str = Form(""),
    tempat_lahir: str = Form(""),
    tanggal_lahir: str = Form(""),
    tahun_masuk: str = Form(""),
    tahun_keluar: str = Form(""),
    angkatan: str = Form(""),
    program: str = Form(""),
    kelas_terakhir: str = Form(""),
    no_induk: str = Form(""),
    no_hp: str = Form(""),
    email: str = Form(""),
    alamat: str = Form(""),
    desa: str = Form(""),
    kecamatan: str = Form(""),
    kota: str = Form(""),
    provinsi: str = Form(""),
    pendidikan_terakhir: str = Form(""),
    nama_instansi: str = Form(""),
    pekerjaan: str = Form(""),
    tempat_kerja: str = Form(""),
    instagram: str = Form(""),
    facebook: str = Form(""),
    nama_ayah: str = Form(""),
    nama_ibu: str = Form(""),
    no_hp_ortu: str = Form(""),
    pekerjaan_ayah: str = Form(""),
    pekerjaan_ibu: str = Form(""),
    alamat_ortu: str = Form(""),
    provinsi_ortu: str = Form(""),
    kota_ortu: str = Form(""),
    catatan: str = Form(""),
    foto: UploadFile = File(None),
):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    existing = db.get_alumni(alumni_id)
    if not existing:
        raise HTTPException(404)

    foto_fn = existing.get("foto", "")
    if foto and foto.filename:
        ext = foto.filename.rsplit(".", 1)[-1].lower()
        if ext in ("jpg", "jpeg", "png", "webp"):
            import uuid
            foto_fn = f"{uuid.uuid4().hex}.{ext}"
            with open(os.path.join(FOTO_DIR, foto_fn), "wb") as f:
                shutil.copyfileobj(foto.file, f)

    def iv(v): return int(v) if str(v).isdigit() else None

    data = dict(
        nama_lengkap=nama_lengkap, nama_panggilan=nama_panggilan,
        jenis_kelamin=jenis_kelamin, tempat_lahir=tempat_lahir,
        tanggal_lahir=tanggal_lahir, foto=foto_fn,
        tahun_masuk=iv(tahun_masuk), tahun_keluar=iv(tahun_keluar),
        angkatan=iv(angkatan), program=program,
        kelas_terakhir=kelas_terakhir, no_induk=no_induk,
        no_hp=no_hp, email=email, alamat=alamat, desa=desa,
        kecamatan=kecamatan, kota=kota, provinsi=provinsi,
        pendidikan_terakhir=pendidikan_terakhir, nama_instansi=nama_instansi,
        pekerjaan=pekerjaan, tempat_kerja=tempat_kerja,
        instagram=instagram, facebook=facebook,
        nama_ayah=nama_ayah, nama_ibu=nama_ibu, no_hp_ortu=no_hp_ortu,
        pekerjaan_ayah=pekerjaan_ayah, pekerjaan_ibu=pekerjaan_ibu,
        alamat_ortu=alamat_ortu, provinsi_ortu=provinsi_ortu, kota_ortu=kota_ortu,
        catatan=catatan,
    )
    db.update_alumni(alumni_id, data)
    return RedirectResponse("/admin/alumni?ok=Data alumni berhasil diperbarui", status_code=302)


@app.post("/admin/alumni/{alumni_id}/hapus")
async def admin_alumni_hapus(request: Request, alumni_id: int):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    db.delete_alumni(alumni_id)
    return RedirectResponse("/admin/alumni?ok=Alumni berhasil dihapus", status_code=302)


# ── Admin Pending ──────────────────────────────────────────────────────────

@app.get("/admin/pending", response_class=HTMLResponse)
async def admin_pending_list(request: Request, ok: str = ""):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    pending_list = db.list_pending()
    pending_count = len(pending_list)
    return _r(request, "admin_pending.html", admin=admin,
              pending_list=pending_list, pending_count=pending_count, ok=ok)


@app.post("/admin/alumni/{alumni_id}/approve")
async def admin_approve(request: Request, alumni_id: int):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    db.approve_alumni(alumni_id)
    return RedirectResponse("/admin/pending?ok=Alumni berhasil disetujui", status_code=302)


@app.post("/admin/alumni/{alumni_id}/tolak")
async def admin_tolak(request: Request, alumni_id: int):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    db.reject_alumni(alumni_id)
    return RedirectResponse("/admin/pending?ok=Alumni ditolak", status_code=302)


# ── Admin Pengumuman ───────────────────────────────────────────────────────

@app.post("/admin/pengumuman/tambah")
async def admin_pengumuman_tambah(
    request: Request,
    judul: str = Form(...),
    isi: str = Form(...),
):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    db.create_pengumuman(judul, isi, admin["id"])
    return RedirectResponse("/admin?ok=Pengumuman berhasil ditambahkan", status_code=302)


@app.post("/admin/pengumuman/{pid}/hapus")
async def admin_pengumuman_hapus(request: Request, pid: int):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    db.delete_pengumuman(pid)
    return RedirectResponse("/admin?ok=Pengumuman dihapus", status_code=302)


# ── Admin Export Excel ─────────────────────────────────────────────────────

@app.get("/admin/alumni/export.xlsx")
async def export_excel(request: Request):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    from fastapi.responses import StreamingResponse
    import openpyxl, io
    alumni_list = db.list_alumni()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Alumni"
    headers = [
        "No", "Nama Lengkap", "Nama Panggilan", "L/P", "Tempat Lahir", "Tanggal Lahir",
        "Tahun Masuk", "Tahun Keluar", "Angkatan", "Program", "Kelas Terakhir", "No Induk",
        "No HP", "Email", "Alamat", "Kecamatan", "Kota", "Provinsi",
        "Pendidikan Terakhir", "Instansi", "Pekerjaan", "Tempat Kerja",
        "Instagram", "Facebook",
        "Nama Ayah", "Nama Ibu", "No HP Ortu", "Pekerjaan Ayah", "Pekerjaan Ibu",
        "Alamat Ortu", "Kota Ortu", "Catatan",
    ]
    ws.append(headers)
    for i, a in enumerate(alumni_list, 1):
        ws.append([
            i, a.get("nama_lengkap"), a.get("nama_panggilan"), a.get("jenis_kelamin"),
            a.get("tempat_lahir"), a.get("tanggal_lahir"),
            a.get("tahun_masuk"), a.get("tahun_keluar"), a.get("angkatan"), a.get("program"),
            a.get("kelas_terakhir"), a.get("no_induk"),
            a.get("no_hp"), a.get("email"), a.get("alamat"), a.get("kecamatan"),
            a.get("kota"), a.get("provinsi"),
            a.get("pendidikan_terakhir"), a.get("nama_instansi"), a.get("pekerjaan"), a.get("tempat_kerja"),
            a.get("instagram"), a.get("facebook"),
            a.get("nama_ayah"), a.get("nama_ibu"), a.get("no_hp_ortu"),
            a.get("pekerjaan_ayah"), a.get("pekerjaan_ibu"),
            a.get("alamat_ortu"), a.get("kota_ortu"), a.get("catatan"),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=alumni-alinayah.xlsx"},
    )


# ── Admin Import Excel ─────────────────────────────────────────────────────

@app.get("/admin/alumni/template.xlsx")
async def download_template(request: Request):
    """Download template Excel kosong untuk diisi dan di-import."""
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    from fastapi.responses import StreamingResponse
    import openpyxl, io
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Alumni"
    headers = [
        "Nama Lengkap*", "Nama Panggilan", "L/P", "Tempat Lahir", "Tanggal Lahir (YYYY-MM-DD)",
        "Tahun Masuk", "Tahun Keluar", "Angkatan", "Program", "Kelas Terakhir", "No Induk",
        "No HP", "Email", "Alamat", "Kecamatan", "Kota", "Provinsi",
        "Pendidikan Terakhir", "Instansi/Kampus", "Pekerjaan", "Tempat Kerja",
        "Instagram", "Facebook",
        "Nama Ayah", "Nama Ibu", "No HP Ortu", "Pekerjaan Ayah", "Pekerjaan Ibu",
        "Alamat Ortu", "Kota Ortu", "Catatan",
    ]
    ws.append(headers)
    # Style header
    green = PatternFill("solid", fgColor="059669")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = green
        cell.alignment = Alignment(horizontal="center")
    # Contoh baris
    ws.append([
        "Muhammad Fauzan", "Fauzan", "L", "Tasikmalaya", "2000-01-15",
        2015, 2020, 12, "Tahfidz", "XII", "2015001",
        "081234567890", "fauzan@gmail.com", "Jl. Merdeka No.5", "Cihideung", "Tasikmalaya", "Jawa Barat",
        "S1", "UIN Bandung", "Guru", "SMPN 1 Tasikmalaya",
        "@fauzan", "Muhammad Fauzan",
        "Ahmad Sholeh", "Siti Fatimah", "081111111111", "Petani", "IRT",
        "Jl. Pesantren No.1", "Tasikmalaya", "",
    ])
    # Auto column width
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 35)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template-alumni-alinayah.xlsx"},
    )


@app.get("/admin/alumni/import", response_class=HTMLResponse)
async def admin_import_page(request: Request, ok: str = "", err: str = ""):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    return _r(request, "admin_import.html", admin=admin, ok=ok, err=err)


@app.post("/admin/alumni/import", response_class=HTMLResponse)
async def admin_import_excel(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form("skip"),  # skip = lewati duplikat, update = perbarui
):
    admin = _admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    import openpyxl, io
    if not file.filename.endswith(".xlsx"):
        return _r(request, "admin_import.html", admin=admin, ok="",
                  err="File harus berformat .xlsx")

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
    except Exception as e:
        return _r(request, "admin_import.html", admin=admin, ok="",
                  err=f"File tidak valid: {e}")

    # Kolom mapping (index 0-based sesuai template)
    COL = [
        "nama_lengkap", "nama_panggilan", "jenis_kelamin", "tempat_lahir", "tanggal_lahir",
        "tahun_masuk", "tahun_keluar", "angkatan", "program", "kelas_terakhir", "no_induk",
        "no_hp", "email", "alamat", "kecamatan", "kota", "provinsi",
        "pendidikan_terakhir", "nama_instansi", "pekerjaan", "tempat_kerja",
        "instagram", "facebook",
        "nama_ayah", "nama_ibu", "no_hp_ortu", "pekerjaan_ayah", "pekerjaan_ibu",
        "alamat_ortu", "kota_ortu", "catatan",
    ]

    berhasil = 0
    dilewati = 0
    error_rows = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue
        nama = str(row[0] or "").strip()
        if not nama:
            dilewati += 1
            continue

        def sv(v):
            if v is None:
                return ""
            return str(v).strip()

        def iv(v):
            try:
                return int(float(str(v))) if v not in (None, "") else None
            except Exception:
                return None

        data = {}
        for i, col in enumerate(COL):
            val = row[i] if i < len(row) else None
            if col in ("tahun_masuk", "tahun_keluar", "angkatan"):
                data[col] = iv(val)
            else:
                data[col] = sv(val)

        # Cek duplikat berdasarkan nama + tahun_masuk
        existing = db.list_alumni(search=nama)
        dup = next((a for a in existing
                    if a["nama_lengkap"].lower() == nama.lower()
                    and a.get("tahun_masuk") == data.get("tahun_masuk")), None)

        if dup:
            if mode == "update":
                db.update_alumni(dup["id"], data)
                berhasil += 1
            else:
                dilewati += 1
        else:
            try:
                db.create_alumni(data)
                berhasil += 1
            except Exception as e:
                error_rows.append(f"Baris {row_idx}: {e}")

    msg = f"{berhasil} alumni berhasil diimport, {dilewati} dilewati."
    if error_rows:
        msg += f" Error: {'; '.join(error_rows[:3])}"
    return RedirectResponse(f"/admin/alumni?ok={msg}", status_code=302)
