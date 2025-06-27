from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os, csv, io
from datetime import date,datetime,timedelta
from sqlalchemy import func
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'devkey')
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') #for production
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')# <-- Use SQLite for local development
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --------------------- Models -----------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'admin' or 'user'
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    veg = db.Column(db.Boolean, default=True)
    available = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item = db.relationship('Item', backref='sales')
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.Date, default=date.today)

    special_occasion = db.Column(db.String(120))  # e.g., "Independence Day", "Festival"
    weather = db.Column(db.String(120))

# --------------------- Create default admin account -----------------------

def create_default_admin():
    # Check if any users exist
    if not User.query.first():
        default_admin = User(
            username='admin',
            password=generate_password_hash('admin123'),  # Default password
            role='admin'
        )
        db.session.add(default_admin)
        db.session.commit()
        print("Default admin account created.")
    else:
        print("Users already exist. Skipping default admin creation.")

    # For production environment
# def create_default_admin():
#     if not User.query.filter_by(role='admin').first():
#         admin_name = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
#         admin_pass = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin@123')
#         admin = User(username=admin_name, role='admin')
#         admin.set_password(admin_pass)  # default password
#         try:
#             db.session.commit()
#             print("✅ Default admin created.")
#         except Exception as e:
#             print("❌ Failed to create admin:", e)

# --------------------- Routes -----------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'user_dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    users = User.query.all()
    available_items = Item.query.filter_by(active=True).all()
    deleted_items = Item.query.filter_by(active=False).all()
    return render_template('admin_dashboard.html', users=users, available_items=available_items, deleted_items=deleted_items)

@app.route('/user')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    items = Item.query.filter_by(active=True, available=True).all()
    available_items = Item.query.filter_by(active=True, available=True).all()
    stockout_items = Item.query.filter_by(active=True, available=False).all()
    cart = session.get('cart', {})
    cart_items = []
    for item_id, qty in cart.items():
        item = Item.query.get(int(item_id))
        if item:
            cart_items.append({
                'id': item.id,
                'name': item.name,
                'qty': qty,
                'price': item.price,
                'veg': item.veg
            })
    return render_template('user_dashboard.html', items=items, cart=cart_items, available_items=available_items, stockout_items=stockout_items)

@app.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    username = request.form['username']
    role = request.form['role']
    new_user = User(username=username, role=role)
    new_user.set_password(request.form['password'])
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_user/<int:id>')
def delete_user(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get(id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/add_item', methods=['POST'])
def add_item():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    name = request.form['name'].strip()
    price = float(request.form['price'])
    veg = request.form.get('veg') == 'on'
    available = request.form.get('available') == 'on'

    # Check if active item with same name exists
    existing_active = Item.query.filter_by(name=name, active=True).first()
    if existing_active:
        return redirect(url_for('admin_dashboard', section='manage-item', error='exists'))

    # Case 1: Item with same name and active
    existing_active = Item.query.filter_by(name=name, active=True).first()
    if existing_active:
        # Item already exists and is active – do not add again
        return redirect(url_for('admin_dashboard', section='manage-item'))

    # Case 2: Item with same name and inactive
    existing_inactive = Item.query.filter_by(name=name, active=False).first()
    if existing_inactive:
        existing_inactive.active = True
        existing_inactive.available = available
        existing_inactive.veg = veg
        # Update price if changed
        if existing_inactive.price != price:
            existing_inactive.price = price
        db.session.commit()
        return redirect(url_for('admin_dashboard', section='manage-item'))

    # Case 3: Brand new item
    new_item = Item(name=name, price=price, veg=veg, available=available)
    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('admin_dashboard', section='manage-item'))

@app.route('/update_item/<int:id>', methods=['POST'])
def update_item(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    item = Item.query.get(int(request.form['id']))
    item.name = request.form['name']
    item.price = float(request.form['price'])
    item.veg = 'veg' in request.form
    item.available = 'available' in request.form
    db.session.commit()
    return redirect(url_for('admin_dashboard', section='manage-item'))

@app.route('/delete_item/<int:id>', methods=['POST'])
def delete_item(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    item = Item.query.get(id)
    item.active=False
    db.session.commit()
    return redirect(url_for('admin_dashboard', section='manage-item'))

@app.route('/restore_item/<int:id>', methods=['POST'])
def restore_item(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    item = Item.query.get(id)
    if item:
        item.active = True
        db.session.commit()
    return redirect(url_for('admin_dashboard', section='manage-item'))

@app.route('/mark_stock_out', methods=['POST'])
def mark_stock_out():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    item_ids = request.form.getlist('item_ids')
    if item_ids:
        Item.query.filter(Item.id.in_(item_ids)).update({Item.available: False}, synchronize_session=False)
        db.session.commit()
        flash("Items marked as Stock Out.")
    return redirect(url_for('user_dashboard',section='stock'))

@app.route('/mark_available', methods=['POST'])
def mark_available():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    item_ids = request.form.getlist('item_ids')
    if item_ids:
        Item.query.filter(Item.id.in_(item_ids)).update({Item.available: True}, synchronize_session=False)
        db.session.commit()
        flash("Items marked as Available.")
    return redirect(url_for('user_dashboard',section='stock'))

@app.route('/reset_stock', methods=['POST'])
def reset_stock():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    Item.query.filter_by(available=False).update({Item.available: True}, synchronize_session=False)
    db.session.commit()
    flash("All stock-out items reset to available.")
    return redirect(url_for('user_dashboard',section='stock'))

@app.route('/add_to_cart/<int:item_id>', methods=['POST'])
def add_to_cart(item_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    cart[str(item_id)] = cart.get(str(item_id), 0) + 1
    session['cart'] = cart
    return redirect(url_for('user_dashboard'))

@app.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    item_id_str = str(item_id)
    if item_id_str in cart:
        del cart[item_id_str]
        session['cart'] = cart
    return redirect(url_for('user_dashboard'))

@app.route('/increment_item/<int:item_id>')
def increment_item(item_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    cart[str(item_id)] = cart.get(str(item_id), 0) + 1
    session['cart'] = cart
    return redirect(url_for('user_dashboard'))

@app.route('/decrement_item/<int:item_id>')
def decrement_item(item_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    item_id_str = str(item_id)
    if item_id_str in cart:
        cart[item_id_str] -= 1
        if cart[item_id_str] <= 0:
            del cart[item_id_str]
    session['cart'] = cart
    return redirect(url_for('user_dashboard'))

@app.route('/bill_preview/<int:sale_id>')
def bill_preview(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    # Get all sales for this user on this day with same metadata
    all_sales_today = Sale.query.filter_by(
        sale_date=sale.sale_date,
        special_occasion=sale.special_occasion,
        weather=sale.weather
    ).all()

    # Group into order format expected by the template
    order = []
    total = 0
    for s in all_sales_today:
        item_data = {
            'name': s.item.name,
            'qty': s.quantity,
            'price': s.total_amount / s.quantity,
            'subtotal': s.total_amount
        }
        total += s.total_amount
        order.append(item_data)

    return render_template('bill_preview.html', order=order, total=total)

@app.route('/resume_order_after_metadata')
def resume_order_after_metadata():
    cart = session.get('pending_order', {})
    if not cart:
        flash("Order data is missing.")
        return redirect(url_for('user_dashboard'))

    metadata = session.get('day_metadata', {})
    if not metadata:
        flash("Day metadata missing.")
        return redirect(url_for('user_dashboard'))

    sale_ids = []

    for item_id, qty in cart.items():
        item = Item.query.get(int(item_id))
        if item:
            sale = Sale(
                item_id=item.id,
                quantity=qty,
                total_amount=item.price * qty,
                sale_date=date.today(),
                special_occasion=metadata.get('special_occasion'),
                weather=metadata.get('weather')
            )
            db.session.add(sale)
            db.session.flush()  # Get sale.id before commit
            sale_ids.append(sale.id)

    db.session.commit()

    # Cleanup session
    session.pop('cart', None)
    session.pop('pending_order', None)
    session.pop('day_metadata', None)

    # ✅ Redirect to bill preview with the first sale ID
    if sale_ids:
        return redirect(url_for('bill_preview', sale_id=sale_ids[0]))
    else:
        flash("Something went wrong.")
        return redirect(url_for('user_dashboard'))

@app.route('/fill-day-metadata', methods=['GET', 'POST'])
def fill_day_metadata():
    if request.method == 'POST':
        # Save metadata in session
        session['day_metadata'] = {
            'special_occasion': request.form.get('occasion'),
            'weather': request.form.get('weather')
        }
        return redirect(url_for('resume_order_after_metadata'))

    return render_template('fill_day_metadata.html')

@app.route('/place_order', methods=['POST'])
def place_order():
    if session.get('role') != 'user':
        return redirect(url_for('login'))

    cart = session.get('cart', {})
    if not cart:
        flash('Cart is empty.')
        return redirect(url_for('user_dashboard'))

    # Check if today's metadata exists (sales entry for today)
    existing_metadata = Sale.query.filter_by(sale_date=date.today()).first()

    if not existing_metadata:
        # First sale of the day – collect occasion/weather
        session['pending_order'] = cart
        return redirect(url_for('fill_day_metadata'))

    else:
        occasion = existing_metadata.special_occasion
        weather = existing_metadata.weather
        print(occasion,weather)
        # Proceed to save/update the sale items
        for item_id, qty in cart.items():
            item = Item.query.get(int(item_id))
            if item:
                existing_sale = Sale.query.filter_by(
                    item_id=item.id,
                    sale_date=date.today()
                ).first()

                if existing_sale:
                    # Update existing sale
                    existing_sale.quantity += qty
                    existing_sale.total_amount += item.price * qty
                else:
                    # Create new sale entry with default/null metadata
                    new_sale = Sale(
                        item_id=item.id,
                        quantity=qty,
                        total_amount=item.price * qty,
                        sale_date=date.today(),
                        special_occasion = occasion,
                        weather = weather
                    )
                    db.session.add(new_sale)

        db.session.commit()

    # Prepare order summary
    order = []
    total = 0
    for item_id, qty in cart.items():
        item = Item.query.get(int(item_id))
        if item:
            subtotal = item.price * qty
            total += subtotal
            order.append({'name': item.name, 'qty': qty, 'price': item.price, 'subtotal': subtotal})

    session.pop('cart', None)
    return render_template('bill_preview.html', order=order, total=total)

@app.route('/statistics')
def view_statistics():
    if session.get('role') not in ['admin', 'user']:
        return redirect(url_for('login'))

    # 🔁 Ensure section=statistics is present in the URL
    if request.args.get('section') != 'statistics':
        query_params = request.args.to_dict()
        query_params['section'] = 'statistics'
        return redirect(url_for('view_statistics', **query_params))

    stat_date_str = request.args.get('stat_date')
    statistics = []
    occasion = weather = None

    if stat_date_str:
        try:
            selected_date = datetime.strptime(stat_date_str, "%Y-%m-%d").date()

            statistics = db.session.query(
                Item.name,
                func.sum(Sale.quantity).label('quantity'),
                func.sum(Sale.total_amount).label('total_amount')
            ).join(Sale, Sale.item_id == Item.id)\
             .filter(Sale.sale_date == selected_date)\
             .group_by(Sale.item_id).all()

            meta = Sale.query.filter_by(sale_date=selected_date).first()
            if meta:
                occasion = meta.special_occasion
                weather = meta.weather

        except ValueError:
            flash("Invalid date format selected.")

    # --- Prepare chart_data for last 15 days ---
    today = datetime.today().date()
    start_date = today - timedelta(days=14)

    raw_data = db.session.query(
        Item.name,
        Sale.sale_date,
        func.sum(Sale.quantity)
    ).join(Item)\
     .filter(Sale.sale_date.between(start_date, today))\
     .group_by(Item.name, Sale.sale_date).all()

    # Build chart_data dictionary
    date_range = [start_date + timedelta(days=i) for i in range(15)]
    item_date_map = defaultdict(lambda: {d: 0 for d in date_range})
    for item_name, sale_date, qty in raw_data:
        item_date_map[item_name][sale_date] = qty

    chart_data = {
        "labels": [d.strftime("%Y-%m-%d") for d in date_range],
        "datasets": [
            {
                "label": item,
                "data": [item_date_map[item][d] for d in date_range]
            } for item in item_date_map
        ]
    }

    # --- Top 5 items in last 30 days ---
    past_30_days = today - timedelta(days=30)
    top_5_items = db.session.query(
        Item.name,
        func.sum(Sale.quantity).label('total_qty')
    ).join(Sale).filter(Sale.sale_date >= past_30_days)\
     .group_by(Item.id)\
     .order_by(func.sum(Sale.quantity).desc())\
     .limit(5).all()

    return render_template(
        'user_dashboard.html',
        statistics=statistics,
        occasion=occasion,
        weather=weather,
        chart_data=chart_data,
        top_5_items=top_5_items,
        items=Item.query.filter_by(active=True).all(),
        available_items=Item.query.filter_by(available=True, active=True).all(),
        stockout_items=Item.query.filter_by(available=False, active=True).all(),
        cart=session.get('cart', {})
    )

@app.route('/export_sales_page')
def export_sales_page():
    if session.get('role') not in ['admin', 'user']:
        return redirect(url_for('login'))

    return render_template(
        'user_dashboard.html',
        section='export',  # optionally use this to show section by default
        statistics=[],
        occasion=None,
        weather=None,
        chart_data={},
        top_5_items=[],
        items=Item.query.filter_by(active=True).all(),
        available_items=Item.query.filter_by(available=True, active=True).all(),
        stockout_items=Item.query.filter_by(available=False, active=True).all(),
        cart=session.get('cart', {})
    )

@app.route('/export_sales', methods=['GET'])
def export_sales():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Start and End date required", 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        return "Invalid date format", 400

    # Step 1: Query all relevant sales
    sales = db.session.query(Sale).join(Sale.item).filter(
        Sale.sale_date.between(start_date, end_date)
    ).all()

    # Step 2: Determine unique item names
    item_names = sorted({sale.item.name for sale in sales})

    # Step 3: Build date -> {item_name -> quantity, occasion, weather, total_amount}
    daily_summary = defaultdict(lambda: {
        "occasion": "",
        "weather": "",
        "items": defaultdict(int),
        "total_amount": 0.0
    })

    for sale in sales:
        key = sale.sale_date
        summary = daily_summary[key]
        summary["occasion"] = sale.special_occasion or ""
        summary["weather"] = sale.weather or ""
        summary["items"][sale.item.name] += sale.quantity
        summary["total_amount"] += sale.total_amount

    # Step 4: Write to CSV
    mem = io.StringIO()
    writer = csv.writer(mem)

    # Header: date, occasion, weather, item1, item2, ..., total_amount
    header = ['Date', 'Occasion', 'Weather'] + item_names + ['Total Sale Amount']
    writer.writerow(header)

    for date in sorted(daily_summary):
        row = [
            date.strftime('%Y-%m-%d'),
            daily_summary[date]['occasion'],
            daily_summary[date]['weather']
        ]
        for name in item_names:
            row.append(daily_summary[date]['items'].get(name, 0))
        row.append(f"{daily_summary[date]['total_amount']:.2f}")
        writer.writerow(row)

    # Convert to BytesIO for send_file
    output = io.BytesIO()
    output.write(mem.getvalue().encode('utf-8'))
    output.seek(0)

    filename = f"sales_summary_{start_date}_{end_date}.csv"
    return send_file(output,
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name=filename)

@app.route('/admin_sales_summary')
def admin_sales_summary():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    # Calculate date 15 days ago from today
    start_date = date.today() - timedelta(days=14)  # includes today + 14 previous days

    data = (
        db.session.query(Sale.sale_date, db.func.sum(Sale.total_amount))
        .filter(Sale.sale_date >= start_date)
        .group_by(Sale.sale_date)
        .order_by(Sale.sale_date)
        .all()
    )
    chart_data = {
        "labels": [str(row[0]) for row in data],
        "datasets": [{
            "label": "Total Sales (₹)",
            "data": [float(row[1]) for row in data],
            "backgroundColor": "rgba(75, 192, 192, 0.5)"
        }]
    }
    users = User.query.all()
    available_items = Item.query.filter_by(active=True).all()
    deleted_items = Item.query.filter_by(active=False).all()
    return render_template("admin_dashboard.html",users=users,
                           available_items=available_items, deleted_items=deleted_items, chart_data=chart_data, section="view_sales")


# --------------------- Main -----------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run(debug=True)

# # For production
# def setup():
#     with app.app_context():
#         db.create_all()
#         create_default_admin()
#
# setup()