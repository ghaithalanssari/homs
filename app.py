from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///homssec.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'  # يرجى استخدام مفتاح سري قوي

db = SQLAlchemy(app)

# نموذج المسؤول (Admin)
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # في التطبيق الحقيقي يجب تشفير كلمات المرور

# نموذج المنطقة مع بيانات GeoJSON وتفاصيل المسؤول الأمني، بالإضافة إلى لون المنطقة
class Region(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    geojson = db.Column(db.Text, nullable=False)  # تخزين GeoJSON كسلسلة نصية
    official_name = db.Column(db.String(100), nullable=False)
    official_phone = db.Column(db.String(20), nullable=False)
    color = db.Column(db.String(20), nullable=False, default="#6B8E23")  # اللون الافتراضي

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "geojson": json.loads(self.geojson),
            "official": {
                "name": self.official_name,
                "phone": self.official_phone
            },
            "color": self.color
        }

# دالة الحماية للمسارات
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            flash("يجب تسجيل الدخول للوصول إلى هذه الصفحة", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# الصفحة الرئيسية لعرض الخريطة
@app.route('/')
def index():
    return render_template('index.html')

# API لإرجاع بيانات المناطق بصيغة JSON
@app.route('/api/regions')
def api_regions():
    regions = Region.query.all()
    regions_data = [region.to_dict() for region in regions]
    return jsonify(regions_data)

# لوحة التحكم (Dashboard) – محمية بتسجيل الدخول
@app.route('/dashboard')
@login_required
def dashboard():
    regions = Region.query.all()
    return render_template('dashboard.html', regions=regions)

# صفحة إضافة مسؤول جديد ومنطقة مع اختيار اللون
@app.route('/add_region', methods=['GET', 'POST'])
@login_required
def add_region():
    if request.method == 'POST':
        region_name = request.form.get('region_name')
        official_name = request.form.get('official_name')
        official_phone = request.form.get('official_phone')
        geojson_str = request.form.get('geojson')
        color = request.form.get('color', '#6B8E23')
        try:
            geojson_obj = json.loads(geojson_str)
        except Exception as e:
            flash("GeoJSON غير صالح: " + str(e), "danger")
            return redirect(url_for('add_region'))
        new_region = Region(
            name=region_name,
            geojson=json.dumps(geojson_obj),
            official_name=official_name,
            official_phone=official_phone,
            color=color
        )
        db.session.add(new_region)
        db.session.commit()
        flash("تم إضافة البيانات بنجاح", "success")
        return redirect(url_for('dashboard'))
    return render_template('add_region.html')

# صفحة تعديل بيانات المنطقة مع تعديل الحدود واللون
@app.route('/edit_region/<int:region_id>', methods=['GET', 'POST'])
@login_required
def edit_region(region_id):
    region = Region.query.get_or_404(region_id)
    if request.method == 'POST':
        region.official_name = request.form.get('official_name')
        region.official_phone = request.form.get('official_phone')
        region.color = request.form.get('color', region.color)
        new_geojson = request.form.get('geojson')
        if new_geojson:
            try:
                geojson_obj = json.loads(new_geojson)
                region.geojson = json.dumps(geojson_obj)
            except Exception as e:
                flash("GeoJSON غير صالح: " + str(e), "danger")
                return redirect(url_for('edit_region', region_id=region_id))
        db.session.commit()
        flash("تم تحديث البيانات بنجاح", "success")
        return redirect(url_for('dashboard'))
    return render_template('edit_region.html', region=region)

@app.route('/delete_region/<int:region_id>', methods=['POST'])
@login_required
def delete_region(region_id):
    region = Region.query.get_or_404(region_id)
    db.session.delete(region)
    db.session.commit()
    flash("تم حذف المنطقة بنجاح", "success")
    return redirect(url_for('dashboard'))


# صفحة تسجيل الدخول للمسؤولين
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.password == password:
            session['admin_logged_in'] = True
            flash("تم تسجيل الدخول بنجاح", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("بيانات الدخول غير صحيحة", "danger")
    return render_template('login.html')

# تسجيل الخروج
@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash("تم تسجيل الخروج", "success")
    return redirect(url_for('login'))

# مسار تهيئة قاعدة البيانات وإنشاء بيانات تجريبية وحساب المسؤول
@app.route('/initdb')
def initdb():
    db.create_all()
    
    # إنشاء حساب المسؤول إذا لم يكن موجوداً
    if Admin.query.count() == 0:
        admin = Admin(username="admin", password="admin123")
        db.session.add(admin)
        db.session.commit()
    
    # إضافة بيانات تجريبية للمناطق إذا كانت القاعدة فارغة
    if Region.query.count() == 0:
        region1_geojson = {
            "type": "Polygon",
            "coordinates": [
                [[36.716, 34.732], [36.722, 34.732], [36.722, 34.728], [36.716, 34.728], [36.716, 34.732]]
            ]
        }
        region2_geojson = {
            "type": "Polygon",
            "coordinates": [
                [[36.724, 34.728], [36.730, 34.728], [36.730, 34.724], [36.724, 34.724], [36.724, 34.728]]
            ]
        }
        region1 = Region(
            name="المنطقة المركزية",
            geojson=json.dumps(region1_geojson),
            official_name="أحمد العبد",
            official_phone="0912345678",
            color="#556B2F"
        )
        region2 = Region(
            name="منطقة الضاحية",
            geojson=json.dumps(region2_geojson),
            official_name="سارة الخطيب",
            official_phone="0923456789",
            color="#6B8E23"
        )
        db.session.add(region1)
        db.session.add(region2)
        db.session.commit()
    
    return "تم إنشاء قاعدة البيانات وإضافة البيانات التجريبية وحساب المسؤول."

if __name__ == '__main__':
    app.run(debug=True)
