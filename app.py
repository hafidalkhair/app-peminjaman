from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.utils import secure_filename
from datetime import datetime
import os, json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'rahasia123'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATA_USER = 'data/users.json'
DATA_PINJAMAN = 'data/peminjaman.json'
DATA_LOG = 'data/log_activity.json'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ==== Fungsi Utilitas ====
def load_json(path, default):
    if not os.path.exists(path): return default
    with open(path, 'r') as f:
        try: return json.load(f)
        except: return default

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_activity(username, aksi):
    logs = load_json(DATA_LOG, [])
    logs.append({
        "username": username,
        "aksi": aksi,
        "waktu": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    })
    save_json(DATA_LOG, logs)

@app.template_filter('rupiah')
def rupiah(value):
    try: return f"Rp {int(value):,}".replace(",", ".")
    except: return value

@app.template_filter('tanggal_format')
def tanggal_format(value):
    try: return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except: return value

# ==== Decorator untuk Admin Required ====
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403)  # Kembalikan error 403 Forbidden
        return f(*args, **kwargs)
    return decorated_function

# ==== Error Handler untuk 403 Forbidden ====
@app.errorhandler(403)
def forbidden(e):
    return render_template("forbidden.html"), 403

# ==== ROUTES ====
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_json(DATA_USER, {})
        username = request.form['username'].strip()
        if username in users:
            flash("Username sudah digunakan", 'error')
            return redirect(url_for('register'))

        users[username] = {
            "password": request.form['password'],
            "email": request.form['email'],
            "nama": "", 
            "tempat_lahir": "",
            "kota": "",
            "provinsi": "",
            "jenis_kelamin": "",
            "foto": "",
            "role": "user",
            "tanggal_daftar": datetime.now().strftime("%Y-%m-%d"),
            "total_pinjaman": 0  
        }
        save_json(DATA_USER, users)
        flash("Registrasi berhasil, silakan login", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_json(DATA_USER, {})
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)

        if user and user['password'] == password:
            session['username'] = username
            session['role'] = user['role']
            log_activity(username, "Login")
            return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'user_dashboard'))
        else:
            flash("Username atau password salah", 'error')

    return render_template('login.html')

@app.route('/verifikasi')
def verifikasi():
    if 'username' not in session:
        return redirect(url_for('login'))

    users = load_json(DATA_USER, {})
    user = users.get(session['username'])

    return render_template('verifikasi-biodata.html', profile=user)

@app.route('/upload-foto', methods=['POST'])
def upload_foto():
    if 'username' not in session:
        return redirect(url_for('login'))

    if 'foto' not in request.files:
        flash("Tidak ada file foto yang diupload", 'error')
        return redirect(url_for('verifikasi'))

    file = request.files['foto']
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{session['username']}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        users = load_json(DATA_USER, {})
        users[session['username']]['foto'] = filename
        save_json(DATA_USER, users)
        flash("Foto berhasil diunggah", "success")
    else:
        flash("Format file tidak didukung", 'error')

    return redirect(url_for('verifikasi'))

@app.route('/user')
def user_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = load_json(DATA_PINJAMAN, [])
    user_data = [d for d in data if d['username'] == session['username']]
    users = load_json(DATA_USER, {})
    user = users.get(session['username'], {})
    total = sum(int(d['jumlah']) for d in user_data)

    return render_template('user-dashboard.html', username=session['username'], nama=user.get("nama", "User"), data=user_data, total=total)

@app.route('/admin')
@admin_required
def admin_dashboard():
    users = load_json(DATA_USER, {})
    data_peminjaman = load_json(DATA_PINJAMAN, [])
    log_aktivitas = load_json(DATA_LOG, [])

    total_users = len(users) - 1 if "admin" in users else len(users)
    total_peminjaman = sum(int(item['jumlah']) for item in data_peminjaman)
    
    activity_logs = log_aktivitas[-5:]
    activity_logs.reverse()

    return render_template(
        'admin-dashboard.html',
        total_users=total_users,
        total_peminjaman=total_peminjaman,
        user_activities=activity_logs
    )

@app.route('/admin/peminjaman')
@admin_required
def admin_peminjaman():
    data_peminjaman = load_json(DATA_PINJAMAN, [])
    return render_template('admin-peminjaman.html', data=data_peminjaman)

@app.route('/admin/users')
@admin_required
def admin_users():
    data_users = load_json(DATA_USER, {})
    return render_template('admin-users.html', users=data_users)

@app.route('/admin/setujui/<int:id>', methods=['POST'])
@admin_required
def setujui_peminjaman(id):
    data_peminjaman = load_json(DATA_PINJAMAN, [])
    users = load_json(DATA_USER, {})

    for pinjam in data_peminjaman:
        if pinjam['id'] == id and pinjam['status'] != 'Disetujui':
            pinjam['status'] = 'Disetujui'
            username = pinjam['username']
            jumlah_pinjaman = int(pinjam['jumlah'])

            user = users.get(username)
            if user:
                user['total_pinjaman'] = user.get('total_pinjaman', 0) + jumlah_pinjaman
                flash(f"Peminjaman {id} disetujui. Total pinjaman {username} bertambah menjadi {rupiah(user['total_pinjaman'])}.", "success")
            else:
                flash(f"User {username} tidak ditemukan.", "error")

    save_json(DATA_PINJAMAN, data_peminjaman)
    save_json(DATA_USER, users)
    return redirect(url_for('admin_peminjaman'))

@app.route('/admin/tolak/<int:id>', methods=['POST'])
@admin_required
def tolak_peminjaman(id):
    data_peminjaman = load_json(DATA_PINJAMAN, [])
    for pinjam in data_peminjaman:
        if pinjam['id'] == id and pinjam['status'] != 'Ditolak':
            pinjam['status'] = 'Ditolak'
    save_json(DATA_PINJAMAN, data_peminjaman)
    return redirect(url_for('admin_peminjaman'))

@app.route('/admin/peminjaman/ubah_status_massal', methods=['POST'])
@admin_required
def ubah_status_peminjaman_massal():
    data_peminjaman = load_json(DATA_PINJAMAN, [])
    users = load_json(DATA_USER, {})

    for pinjam in data_peminjaman:
        id_pinjam = str(pinjam['id'])
        status_baru = request.form.get(f'status_{id_pinjam}')

        if status_baru and pinjam['status'] != status_baru:
            status_lama = pinjam['status']
            pinjam['status'] = status_baru
            username = pinjam['username']
            jumlah_pinjaman = int(pinjam['jumlah'])

            if pinjam['status'] == 'Selesai' and status_lama != 'Selesai':
                user = users.get(username)
                if user:
                    user['total_pinjaman'] = user.get('total_pinjaman', 0) - jumlah_pinjaman
                    flash(f"Peminjaman {id_pinjam} diselesaikan. Total pinjaman {username} berkurang menjadi {rupiah(user['total_pinjaman'])}.", "success")
                else:
                    flash(f"User {username} tidak ditemukan.", "error")
            
            flash(f"Status peminjaman {id_pinjam} berhasil diubah menjadi {status_baru}", "success")

    save_json(DATA_PINJAMAN, data_peminjaman)
    save_json(DATA_USER, users)
    return redirect(url_for('admin_peminjaman'))

@app.route('/user/form', methods=['GET', 'POST'])
def form_peminjaman():
    if session.get('role') != 'user':
        return redirect(url_for('login'))

    users = load_json(DATA_USER, {})
    user = users.get(session['username'])

    if not all([user.get("nama"), user.get("tempat_lahir"), user.get("kota"),
                user.get("provinsi"), user.get("jenis_kelamin"), user.get("foto")]):
        flash("Lengkapi biodata dan upload foto sebelum mengajukan pinjaman!", "error")
        return redirect(url_for('verifikasi'))

    if request.method == 'POST':
        data = load_json(DATA_PINJAMAN, [])
        username = session['username']
        jumlah_pinjaman = int(request.form.get('jumlah'))

        peminjaman = {
            "id": len(data) + 1,
            "username": username,
            "jumlah": str(jumlah_pinjaman),
            "tanggal_pinjam": request.form.get('tanggal_pinjam'),
            "tanggal_kembali": request.form.get('tanggal_kembali'),
            "status": "Menunggu"
        }
        data.append(peminjaman)

        flash("Peminjaman berhasil diajukan. Menunggu persetujuan Admin.", "success")
        save_json(DATA_PINJAMAN, data)
        log_activity(session['username'], "Ajukan Peminjaman")
        return redirect(url_for('user_dashboard'))

    return render_template('form-peminjaman.html')

@app.route('/user/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    users = load_json(DATA_USER, {})
    username = session['username']
    profile = users.get(username, {})

    if request.method == 'POST':
        profile['nama'] = request.form['nama']
        profile['tempat_lahir'] = request.form['tempat_lahir']
        profile['kota'] = request.form['kota']
        profile['provinsi'] = request.form['provinsi']
        profile['jenis_kelamin'] = request.form['jenis_kelamin']
        profile['password'] = request.form['password']
        users[username] = profile
        save_json(DATA_USER, users)
        flash("Profil berhasil diperbarui", "success")
        return redirect(url_for('verifikasi'))

    return render_template('edit-profile.html', profile=profile)

@app.route('/logout')
def logout():
    log_activity(session.get('username', 'unknown'), "Logout")
    session.clear()
    return redirect(url_for('landing'))

# LAPORAN PEMINJAMAN
@app.route('/admin/laporan', methods=['GET', 'POST'])
@admin_required
def laporan_peminjaman():
    if request.method == 'POST':
        tgl_awal = request.form['tgl_awal']
        tgl_akhir = request.form['tgl_akhir']

        data_pinjaman = load_json(DATA_PINJAMAN, [])
        data_user = load_json(DATA_USER, {})

        data_laporan = [
            p for p in data_pinjaman
            if tgl_awal <= p['tanggal_pinjam'] <= tgl_akhir
        ]

        total_peminjaman = sum(int(p['jumlah']) for p in data_laporan)

        for p in data_laporan:
            username = p['username']
            p['nama_peminjam'] = data_user.get(username, {}).get('nama', 'Tidak Diketahui')

        return render_template(
            'admin/laporan-peminjaman.html',
            tgl_awal=tgl_awal,
            tgl_akhir=tgl_akhir,
            total_peminjaman=total_peminjaman,
            data_laporan=data_laporan
        )

    return render_template('admin/form-laporan.html')

@app.route('/admin/laporan/cetak', methods=['GET'])
@admin_required
def cetak_laporan():
    tgl_awal = request.args.get('tgl_awal')
    tgl_akhir = request.args.get('tgl_akhir')

    data_pinjaman = load_json(DATA_PINJAMAN, [])
    data_user = load_json(DATA_USER, {})

    data_laporan = [
        p for p in data_pinjaman
        if tgl_awal <= p['tanggal_pinjam'] <= tgl_akhir
    ]

    for p in data_laporan:
        username = p['username']
        p['nama_peminjam'] = data_user.get(username, {}).get('nama', 'Tidak Diketahui')

    return render_template('cetak-laporan.html', data_laporan=data_laporan, tgl_awal=tgl_awal, tgl_akhir=tgl_akhir)

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    if not os.path.exists(DATA_USER):
        save_json(DATA_USER, {
            "admin": {
                "password": "admin123",
                "email": "admin@example.com",
                "nama": "Admin",
                "tempat_lahir": "",
                "kota": "",
                "provinsi": "",
                "jenis_kelamin": "",
                "foto": "",
                "role": "admin",
                "tanggal_daftar": datetime.now().strftime("%Y-%m-%d"),
                "total_pinjaman": 0
            }
        })

    app.run(debug=True)