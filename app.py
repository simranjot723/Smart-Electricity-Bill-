from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import random
import io, os, re
from fpdf import FPDF
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np

# ------------------ APP CONFIG ------------------
app = Flask(__name__)
# Use DATABASE_URL if provided, otherwise fall back to local sqlite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ------------------ MODELS ------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meter_number = db.Column(db.String(50), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)   # ✅ not unique
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)

# ------------------ ROUTES ------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# LOGIN (by meter_number + password)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        meter_number = request.form["meter_number"]
        location = request.form["location"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        password = request.form["password"]

        # Query user with all fields
        user = User.query.filter_by(
            meter_number=meter_number,
            location=location,
            email=email,
            mobile=mobile
        ).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("❌ Invalid credentials. Please try again.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")
# REGISTER
@app.route("/register", methods=["POST"])
def register():
    meter_number = request.form["meter_number"]
    location = request.form["location"]
    username = request.form["username"]
    password = request.form["password"]
    email = request.form["email"]
    mobile = request.form["mobile"]

    # Strong password validation
    if len(password) < 8 or not re.search(r"[A-Z]", password) \
       or not re.search(r"[0-9]", password) \
       or not re.search(r"[!@#$%^&*]", password):
        flash("❌ Password must be at least 8 characters long, include an uppercase letter, a number, and a special character (!@#$%^&*).", "danger")
        # Render login page again but keep register modal open
        return render_template("login.html", show_register=True)

    # Duplicate check
    if User.query.filter(
        (User.meter_number == meter_number) |
        (User.email == email) |
        (User.mobile == mobile)|
        (User.username == username)|
        (User.location == location)|
        (User.password == generate_password_hash(password))
        ).first():
        flash("❌ User already exists! Please use different details.", "danger")
        return render_template("login.html", show_register=True)

    # Save user
    hashed_pw = generate_password_hash(password)
    new_user = User(
        meter_number=meter_number,
        location=location,
        username=username,
        password=hashed_pw,
        email=email,
        mobile=mobile
    )
    db.session.add(new_user)
    db.session.commit()
    flash("✅ Registration successful! Please login.", "success")
    return redirect(url_for("login"))

# RESET BY MOBILE
@app.route("/reset_by_mobile", methods=["GET", "POST"])
def reset_by_mobile():
    if request.method == "POST":
        mobile = request.form["mobile"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "warning")
            return redirect(url_for("reset_by_mobile"))

        user = User.query.filter_by(mobile=mobile).first()
        if user:
            user.password = generate_password_hash(password)
            db.session.commit()
            flash("Password updated successfully! Please login.", "success")
            return redirect(url_for("login"))
        else:
            flash("Mobile number not registered!", "danger")
    return render_template("reset_by_mobile.html")

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login first!", "warning")
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    return render_template("dashboard.html",username=user.username, meter_number=user.meter_number, location=user.location, mobile=user.mobile)
                           

# GENERATE BILL
@app.route("/generate_bill", methods=["POST"])
def generate_bill():
    prev_units = int(request.form["previous_units"])
    curr_units = int(request.form["current_units"])
    username = User.query.get(session["user_id"]).username if "user_id" in session else "Guest"

    unit_diff = curr_units - prev_units
    rate_per_unit = 7
    prev_bill = prev_units * rate_per_unit
    curr_bill = curr_units * rate_per_unit
    bill_diff = curr_bill - prev_bill
    percent = round((bill_diff / prev_bill * 100), 2) if prev_bill > 0 else 0

    due_date = (datetime.now() + timedelta(days=10)).strftime("%d-%m-%Y")
    days_left = (datetime.strptime(due_date, "%d-%m-%Y") - datetime.now()).days

    appliance_data = {}
    for key, value in request.form.items():
        if key.startswith("appliances") and value and int(value) > 0:
            appliance_name = key.split('[')[1][:-1]
            appliance_data[appliance_name] = int(value)

    return render_template("bill_result.html",
                           username=username,
                           prev_units=prev_units,
                           curr_units=curr_units,
                           prev_bill=prev_bill,
                           curr_bill=curr_bill,
                           unit_diff=unit_diff,
                           bill_diff=bill_diff,
                           percent=percent,
                           due_date=due_date,
                           days_left=days_left,
                           appliances=appliance_data)

# INSIGHTS
@app.route("/insights", methods=["POST"])
def insights():
    prev_units = int(request.form.get("prev_units"))
    curr_units = int(request.form.get("curr_units"))
    unit_diff = curr_units - prev_units
    rate_per_unit = 7
    prev_bill = prev_units * rate_per_unit
    curr_bill = curr_units * rate_per_unit
    bill_diff = curr_bill - prev_bill
    percent = round((bill_diff / prev_bill * 100), 2) if prev_bill > 0 else 0
    due_date = (datetime.now() + timedelta(days=10)).strftime("%d-%m-%Y")
    days_left = (datetime.strptime(due_date, "%d-%m-%Y") - datetime.now()).days

    user = User.query.get(session["user_id"]) if "user_id" in session else None
    meter_number = user.meter_number if user else "Unknown"
    username = user.username if user else "Guest"
    location = user.location if user else "Unknown"
    email = user.email if user else "Unknown"
    mobile = user.mobile if user else "Unknown"

    return render_template("insights.html",
                           meter_number=meter_number,
                           username=username,
                           location=location,
                           email=email,
                           mobile=mobile,
                           prev_units=prev_units,
                           curr_units=curr_units,
                           prev_bill=prev_bill,
                           curr_bill=curr_bill,
                           unit_diff=unit_diff,
                           bill_diff=bill_diff,
                           days_left=days_left,
                           due_date=due_date,
                           percent=percent)

# DOWNLOAD PDF
@app.route("/download", methods=["POST"])
def download():
    prev_units = int(request.form.get("prev_units"))
    curr_units = int(request.form.get("curr_units"))
    bill_number = f"BILL-{random.randint(100000,999999)}"

    user = User.query.get(session["user_id"]) if "user_id" in session else None
    username = user.username if user else "Guest"
    location = user.location if user else "Unknown"
    email = user.email if user else "Unknown"
    mobile = user.mobile if user else "Unknown"
    meter_number = user.meter_number if user else "Unknown"

    rate_per_unit = 7
    prev_bill = prev_units * rate_per_unit
    curr_bill = curr_units * rate_per_unit
    bill_diff = curr_bill - prev_bill
    percent = round((bill_diff / prev_bill * 100), 2) if prev_bill > 0 else 0
    due_date = (datetime.now() + timedelta(days=10)).strftime("%d-%m-%Y")
    days_left = (datetime.strptime(due_date, "%d-%m-%Y") - datetime.now()).days

    # Graph
    x = np.array(["Previous", "Current"])
    y = np.array([prev_units, curr_units])
    plt.figure(figsize=(3,2))
    plt.bar(x, y, color=["skyblue","pink"])
    plt.title("Electricity Units Comparison")
    plt.ylabel("Units")
    plt.tight_layout()
    graph_path = "static/temp_graph.png"
    plt.savefig(graph_path, format="PNG")
    plt.close()

    # PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial","B",20)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(200,10,"SMART ELECTRICITY BILL",ln=True,align="C")
    pdf.ln(1)

    pdf.set_font("Arial","B",16)
    pdf.set_text_color(0,0,0)
    pdf.set_fill_color(255,200,200)
    pdf.cell(200,10," Bill & Meter Number",ln=True,fill=True)
    pdf.set_font("Arial","B",12)
    pdf.cell(200,10,f"Bill Number: {bill_number}",ln=True)
    pdf.cell(200,10,f"Meter Number: {meter_number}",ln=True)

    pdf.set_font("Arial","B",16)
    pdf.set_fill_color(255,20,200)
    pdf.cell(200,10," Customer Information",ln=True,fill=True)
    pdf.set_font("Arial",size=12)
    pdf.cell(200,10,f"Name: {username}",ln=True)
    pdf.cell(200,10,f"Location: {location}",ln=True)
    pdf.cell(200,10,f"Email: {email}",ln=True)
    pdf.cell(200,10,f"Mobile: {mobile}",ln=True)

    pdf.set_font("Arial","B",16)
    pdf.set_fill_color(230,230,230)
    pdf.cell(200,10,"Units Consumed",ln=True,fill=True)
    pdf.set_font("Arial",size=12)
    pdf.cell(200,10,f"Previous Units: {prev_units}",ln=True)
    pdf.cell(200,10,f"Current Units: {curr_units}",ln=True)

    pdf.set_font("Arial","B",16)
    pdf.set_fill_color(255,230,150)
    pdf.cell(200,10,"Billing Details",ln=True,fill=True)
    pdf.set_font("Arial",size=12)
    pdf.cell(200,10,f"Rate per Unit: Rs {rate_per_unit}",ln=True)
    pdf.cell(200,10,f"Previous Bill: Rs {prev_bill}",ln=True)
    pdf.cell(200,10,f"Current Bill: Rs {curr_bill}",ln=True)
    pdf.cell(200,10,f"Difference: Rs {bill_diff}",ln=True)
    pdf.cell(200,10,f"Percentage Change: {percent}%",ln=True)

    # DUE DATE
    pdf.set_font("Arial","B",16)
    pdf.set_fill_color(255,200,200)
    pdf.cell(200,10,"Date Information",ln=True,fill=True)
    pdf.set_font("Arial",size=12)
    pdf.cell(200,10,f"Due Date: {due_date}",ln=True)
    pdf.cell(200,10,f"Days Left: {days_left} days",ln=True)

    # TOTAL
    pdf.set_fill_color(255,200,0)
    pdf.set_font("Arial","B",16)
    pdf.cell(200,10,f"TOTAL PAYABLE: Rs {curr_bill}",ln=True,fill=True)

    # Insert image
    pdf.ln(1)  # Add some spacing
    pdf.image("static/smart_system.png", x=8, w=100)

    # Insert graph
    pdf.image(graph_path, x=10, w=pdf.w -55)

    # Footer branding
    pdf.ln(15)
    pdf.set_font("Arial", 'I', 12)
    pdf.set_text_color(255, 0, 0)
    pdf.cell(200, 10, "© 2026 Smart Billing | Developed by Simranjot, Muskanpeet, Gurpreet", ln=True, align="C")

    # Output as bytes
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    pdf_stream = io.BytesIO(pdf_bytes)

    return send_file(pdf_stream,
                     as_attachment=True,
                     download_name="SmartBill.pdf",
                     mimetype="application/pdf")

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))

# ------------------ MAIN ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
