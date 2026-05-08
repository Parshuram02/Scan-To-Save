from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
import sqlite3
import qrcode
import io
import base64
import secrets
from datetime import datetime
# import requests
from flask import Flask, render_template
# from twilio.rest import Client
import re
# from dotenv import load_dotenv
import os

# load_dotenv()


# TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
# TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# from flask import Flask, render_template, request, jsonify
# import sqlite3
# import qrcode
# import io
# import base64
# import secrets

# from flask_pwa import PWA

import os
from database import init_db, get_db

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend')
app.secret_key = 'ait_admin_secret_key'

app.config['PWA_APP_NAME'] = "Emergency QR"
app.config['PWA_APP_DESCRIPTION'] = "Offline support for emergency QR code details"
app.config['PWA_APP_THEME_COLOR'] = "#ffffff"
app.config['PWA_APP_BACKGROUND_COLOR'] = "#000000"
app.config['PWA_APP_DISPLAY'] = "standalone"
app.config['PWA_APP_SCOPE'] = "/"
app.config['PWA_APP_START_URL'] = "/"
#pwa = PWA(app)

# Initialize the database when the app is created
with app.app_context():
    init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')


@app.route('/select_template/<template_name>')
def select_template(template_name):
    return render_template('profile_form.html', template=template_name)

@app.route('/generate_profile', methods=['POST'])
def generate_profile():
    # Generate a secure random ID
    profile_id = secrets.token_hex(16)
    
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO profiles (
                id, name, phone, blood_group, template, password, purpose
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            profile_id,
            request.form['name'],
            request.form['phone'],
            request.form['blood_group'],
            request.form['template'],
            request.form['password'],
            request.form.get('purpose')
        ))
        
        # Insert emergency contact if provided
        emergency_contact = request.form.get('emergency_contact')
        if emergency_contact:
            conn.execute('''
                INSERT INTO emergency_contacts (profile_id, contact_name)
                VALUES (?, ?)
            ''', (profile_id, emergency_contact))
            
        # Insert medical records
        medical_conditions = request.form.get('medical_conditions')
        if medical_conditions:
            conn.execute('''
                INSERT INTO medical_records (profile_id, record_type, description)
                VALUES (?, 'condition', ?)
            ''', (profile_id, medical_conditions))
            
        allergies = request.form.get('allergies')
        if allergies:
            conn.execute('''
                INSERT INTO medical_records (profile_id, record_type, description)
                VALUES (?, 'allergy', ?)
            ''', (profile_id, allergies))
            
        medications = request.form.get('medications')
        if medications:
            conn.execute('''
                INSERT INTO medical_records (profile_id, record_type, description)
                VALUES (?, 'medication', ?)
            ''', (profile_id, medications))
            
        conn.commit()
        
        # Generate QR code with just the profile ID
        profile_url = url_for('view_profile', 
                            profile_id=profile_id,
                            _external=True)
        
        # Create QR code in memory
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(profile_url)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert QR code to base64 for displaying in HTML
        buffered = io.BytesIO()
        qr_image.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return render_template('qr_display.html', 
                             qr_base64=qr_base64, 
                             profile_id=profile_id)
                             
    except Exception as e:
        print(f"Error: {e}")
        return "Error creating profile", 500
    finally:
        conn.close()

def calculate_risk_score(profile):
    risk_score = 0
    
    # 1. Use Case Baseline
    purpose = profile.get('purpose', '')
    if purpose == 'Motorcycle Helmet':
        risk_score += 3
    elif purpose == 'Medical ID':
        risk_score += 2
    elif purpose == 'Pet Tag (Dog/Cat)':
        risk_score += 0
    else:
        risk_score += 1
        
    # 2. Medical Complexity
    conditions = profile.get('medical_conditions', '')
    if conditions:
        risk_score += len([c for c in conditions.split(',') if c.strip()]) * 1
        
    medications = profile.get('medications', '')
    if medications:
        risk_score += len([m for m in medications.split(',') if m.strip()]) * 1
        
    # 3. Severe Allergies
    allergies = profile.get('allergies', '')
    if allergies:
        severe_keywords = ['penicillin', 'peanut', 'latex', 'bee', 'wasp', 'nut']
        allergy_text = allergies.lower()
        for keyword in severe_keywords:
            if keyword in allergy_text:
                risk_score += 2
                
    # 4. Safety Net
    contacts = profile.get('emergency_contact', '')
    if not contacts:
        risk_score += 2
        
    if risk_score >= 6:
        return 'High Risk'
    elif risk_score >= 3:
        return 'Medium Risk'
    else:
        return 'Low Risk'

@app.route('/profile/<profile_id>')
def view_profile(profile_id):
    conn = get_db()
    try:
        profile_row = conn.execute(
            'SELECT * FROM profiles WHERE id = ?', 
            (profile_id,)
        ).fetchone()
        
        if profile_row is None:
            return "Profile not found", 404
            
        # Convert to mutable dict
        profile = dict(profile_row)
        
        # Fetch emergency contacts
        contacts = conn.execute(
            'SELECT * FROM emergency_contacts WHERE profile_id = ?', 
            (profile_id,)
        ).fetchall()
        
        if contacts:
            profile['emergency_contact'] = ", ".join([c['contact_name'] for c in contacts if c['contact_name']])
        else:
            profile['emergency_contact'] = ""
            
        # Fetch medical records
        records = conn.execute(
            'SELECT * FROM medical_records WHERE profile_id = ?', 
            (profile_id,)
        ).fetchall()
        
        conditions = [r['description'] for r in records if r['record_type'] == 'condition']
        allergies = [r['description'] for r in records if r['record_type'] == 'allergy']
        medications = [r['description'] for r in records if r['record_type'] == 'medication']
        
        profile['medical_conditions'] = ", ".join(conditions) if conditions else ""
        profile['allergies'] = ", ".join(allergies) if allergies else ""
        profile['medications'] = ", ".join(medications) if medications else ""
        
        # Calculate Patient Risk Score
        profile['risk_level'] = calculate_risk_score(profile)
            
        # Log the scan
        conn.execute('''
            INSERT INTO scan_logs (profile_id, ip_address, user_agent)
            VALUES (?, ?, ?)
        ''', (profile_id, request.remote_addr, request.user_agent.string))
        conn.commit()
        
        # Check for password if provided
        provided_password = request.args.get('password')
        show_sensitive = provided_password and provided_password == profile['password']
        
        return render_template('profile_view.html', 
                             profile=profile,
                             show_sensitive=show_sensitive)
    finally:
        conn.close()

@app.route('/download_qr/<profile_id>')
def download_qr(profile_id):
    conn = get_db()
    try:
        # Verify profile exists
        profile = conn.execute(
            'SELECT id FROM profiles WHERE id = ?', 
            (profile_id,)
        ).fetchone()
        
        if profile is None:
            return "Profile not found", 404
            
        # Generate QR code
        profile_url = url_for('view_profile', 
                            profile_id=profile_id,
                            _external=True)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(profile_url)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO object
        img_io = io.BytesIO()
        qr_image.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(
            img_io,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"qr_code_{profile_id}.png"
        )
    except Exception as e:
        print(f"Download error: {e}")
        return "Error generating QR code", 500
    finally:
        conn.close()
    # Add these new routes to your app.py

@app.route('/scanner')
def scanner():
    """Route to show QR scanner page"""
    return render_template('scanner.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    """Admin dashboard to view logs and verify database changes"""
    if request.method == 'POST':
        if request.form.get('password') == 'ait':
            session['admin_logged_in'] = True
        else:
            return render_template('admin_login.html', error="Invalid password")
            
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')

    conn = get_db()
    try:
        logs = conn.execute('SELECT * FROM scan_logs ORDER BY scanned_at DESC').fetchall()
        profiles_rows = conn.execute('SELECT * FROM profiles ORDER BY created_at DESC').fetchall()
        
        risk_distribution = {'High Risk': 0, 'Medium Risk': 0, 'Low Risk': 0}
        profiles_list = []
        for row in profiles_rows:
            p = dict(row)
            contacts = conn.execute('SELECT * FROM emergency_contacts WHERE profile_id = ?', (p['id'],)).fetchall()
            p['emergency_contact'] = "yes" if contacts else ""
            
            records = conn.execute('SELECT * FROM medical_records WHERE profile_id = ?', (p['id'],)).fetchall()
            conditions = [r['description'] for r in records if r['record_type'] == 'condition']
            allergies = [r['description'] for r in records if r['record_type'] == 'allergy']
            medications = [r['description'] for r in records if r['record_type'] == 'medication']
            
            p['medical_conditions'] = ",".join(conditions)
            p['allergies'] = ",".join(allergies)
            p['medications'] = ",".join(medications)
            
            risk = calculate_risk_score(p)
            p['risk_level'] = risk
            risk_distribution[risk] += 1
            profiles_list.append(p)
            
        profiles = profiles_list
        
        # --- Analytics Queries ---
        total_profiles = conn.execute('SELECT COUNT(*) as count FROM profiles').fetchone()['count']
        total_scans = conn.execute('SELECT COUNT(*) as count FROM scan_logs').fetchone()['count']
        
        common_allergies = conn.execute('''
            SELECT description, COUNT(*) as count 
            FROM medical_records 
            WHERE record_type='allergy' 
            GROUP BY description 
            ORDER BY count DESC LIMIT 5
        ''').fetchall()
        
        purposes = conn.execute('''
            SELECT purpose, COUNT(*) as count 
            FROM profiles 
            WHERE purpose IS NOT NULL AND purpose != '' 
            GROUP BY purpose 
            ORDER BY count DESC
        ''').fetchall()
        
        # Prepare Chart Data for Frontend
        chart_data = {
            'purposes': {
                'labels': [p['purpose'] for p in purposes],
                'data': [p['count'] for p in purposes]
            },
            'risk': {
                'labels': ['High Risk', 'Medium Risk', 'Low Risk'],
                'data': [risk_distribution['High Risk'], risk_distribution['Medium Risk'], risk_distribution['Low Risk']]
            }
        }

        import json
        return render_template('admin.html', 
                               logs=logs, 
                               profiles=profiles,
                               total_profiles=total_profiles,
                               total_scans=total_scans,
                               common_allergies=common_allergies,
                               chart_data=json.dumps(chart_data))
    finally:
        conn.close()

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_profile/<profile_id>', methods=['GET', 'POST'])
def edit_profile(profile_id):
    conn = get_db()
    try:
        if request.method == 'POST':
            # Verify password first
            profile = conn.execute(
                'SELECT password FROM profiles WHERE id = ?', 
                (profile_id,)
            ).fetchone()
            
            if not profile or profile['password'] != request.form.get('password'):
                return "Invalid password", 403
                
            # Update core profile
            conn.execute('''
                UPDATE profiles 
                SET name = ?,
                    phone = ?,
                    blood_group = ?,
                    purpose = ?
                WHERE id = ?
            ''', (
                request.form['name'],
                request.form['phone'],
                request.form['blood_group'],
                request.form.get('purpose'),
                profile_id
            ))
            
            # Update emergency contact
            conn.execute('DELETE FROM emergency_contacts WHERE profile_id = ?', (profile_id,))
            emergency_contact = request.form.get('emergency_contact')
            if emergency_contact:
                conn.execute('INSERT INTO emergency_contacts (profile_id, contact_name) VALUES (?, ?)', (profile_id, emergency_contact))
                
            # Update medical records
            conn.execute('DELETE FROM medical_records WHERE profile_id = ?', (profile_id,))
            
            medical_conditions = request.form.get('medical_conditions')
            if medical_conditions:
                conn.execute('INSERT INTO medical_records (profile_id, record_type, description) VALUES (?, ?, ?)', (profile_id, 'condition', medical_conditions))
                
            allergies = request.form.get('allergies')
            if allergies:
                conn.execute('INSERT INTO medical_records (profile_id, record_type, description) VALUES (?, ?, ?)', (profile_id, 'allergy', allergies))
                
            medications = request.form.get('medications')
            if medications:
                conn.execute('INSERT INTO medical_records (profile_id, record_type, description) VALUES (?, ?, ?)', (profile_id, 'medication', medications))

            conn.commit()
            return redirect(url_for('view_profile', profile_id=profile_id))
            
        # GET request - show edit form
        profile_row = conn.execute(
            'SELECT * FROM profiles WHERE id = ?', 
            (profile_id,)
        ).fetchone()
        
        if profile_row is None:
            return "Profile not found", 404
            
        profile = dict(profile_row)
        
        # Fetch relationships
        contacts = conn.execute('SELECT * FROM emergency_contacts WHERE profile_id = ?', (profile_id,)).fetchall()
        profile['emergency_contact'] = ", ".join([c['contact_name'] for c in contacts if c['contact_name']]) if contacts else ""
        
        records = conn.execute('SELECT * FROM medical_records WHERE profile_id = ?', (profile_id,)).fetchall()
        
        conditions = [r['description'] for r in records if r['record_type'] == 'condition']
        allergies = [r['description'] for r in records if r['record_type'] == 'allergy']
        medications = [r['description'] for r in records if r['record_type'] == 'medication']
        
        profile['medical_conditions'] = ", ".join(conditions) if conditions else ""
        profile['allergies'] = ", ".join(allergies) if allergies else ""
        profile['medications'] = ", ".join(medications) if medications else ""
            
        return render_template('edit_profile.html', profile=profile)
        
    finally:
        conn.close()

@app.route('/verify_password/<profile_id>', methods=['POST'])
def verify_password(profile_id):
    """API endpoint to verify password"""
    conn = get_db()
    try:
        profile = conn.execute(
            'SELECT password FROM profiles WHERE id = ?', 
            (profile_id,)
        ).fetchone()
        
        if not profile:
            return {"valid": False}, 404
            
        provided_password = request.json.get('password')
        is_valid = profile['password'] == provided_password
        
        return {"valid": is_valid}
    finally:
        conn.close()

# client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def is_valid_phone_number(phone_number):
    """Validate phone number format (E.164)"""
    pattern = r"^\+\d{10,15}$"
    return bool(re.match(pattern, phone_number))

# def send_sms(emergency_contact, location_link):
#     """Send emergency SMS with live location"""
#     try:
#         # Validate phone number format
#         if not is_valid_phone_number(emergency_contact):
#             print(f"❌ Invalid Phone Number: {emergency_contact}")
#             return 400  # Bad request

#         message = client.messages.create(
#             body=f"🚨 Emergency Alert! Live Location: {location_link}",
#             from_=TWILIO_PHONE_NUMBER,
#             to=emergency_contact
#         )
#         print(f"✅ SMS Sent! Message SID: {message.sid}")
#         return 200  # Success
#     except Exception as e:
#         print(f"❌ Error sending SMS: {e}")
#         return 500  # Failure

@app.route('/send_emergency', methods=['POST'])
def send_emergency():
    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    emergency_contact = data.get("emergency_contact")

    if not latitude or not longitude or not emergency_contact:
        return jsonify({"error": "Missing data"}), 400

    # Ensure phone number is valid
    if not is_valid_phone_number(emergency_contact):
        return jsonify({"error": "Invalid phone number format"}), 400

    # Generate Google Maps Link
    location_link = f"https://www.google.com/maps?q={latitude},{longitude}"

    # Just simulate success without sending SMS
    print(f"🚨 Simulated emergency message to {emergency_contact} with location: {location_link}")
    
    return jsonify({"message": "Simulated emergency message sent!"}), 200


        
@app.route('/admin/seed')
def seed_live_data():
    import uuid
    import random
    from datetime import datetime, timedelta
    
    conn = get_db()
    try:
        # Clear existing demo data to avoid duplicates if run multiple times
        # Only clear if you want a fresh start; otherwise, comment these out.
        conn.execute('DELETE FROM scan_logs')
        conn.execute('DELETE FROM medical_records')
        conn.execute('DELETE FROM emergency_contacts')
        conn.execute('DELETE FROM profiles')

        names = ["Aarav Sharma", "Aditi Rao", "Vihaan Gupta", "Ananya Singh", "Siddharth Verma", 
                 "Ishani Iyer", "Arjun Reddy", "Meera Nair", "Kabir Malhotra", "Diya Joshi",
                 "Rohan Das", "Sana Khan", "Aryan Kapoor", "Kyra Sen", "Ishaan Bhat",
                 "Zoya Ali", "Dev Patel", "Myra Saxena", "Rahul Bose", "Tara Dutta",
                 "John Doe", "Jane Smith", "Michael Ross", "Rachel Zane", "Harvey Specter",
                 "Donna Paulsen", "Louis Litt", "Mike Ehrmantraut", "Walter White", "Jesse Pinkman"]

        blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
        purposes = ["Medical ID", "Motorcycle Helmet", "Pet Tag (Dog/Cat)", "General Identification", "Other"]
        
        conditions_list = ["Hypertension", "Type 2 Diabetes", "Asthma", "Epilepsy", "Cardiac Arrhythmia"]
        allergies_list = ["Penicillin", "Peanuts", "Latex", "Bee Stings", "Dairy"]
        medications_list = ["Metformin", "Lisinopril", "Albuterol", "Levothyroxine", "Atorvastatin"]

        for i in range(50):
            profile_id = uuid.uuid4().hex
            name = names[i % len(names)]
            phone = f"+91 {random.randint(70000, 99999)} {random.randint(10000, 99999)}"
            bg = random.choice(blood_groups)
            purpose = random.choice(purposes)
            created_at = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d %H:%M:%S')
            
            conn.execute('''
                INSERT INTO profiles (id, name, phone, blood_group, template, password, purpose, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (profile_id, name, phone, bg, "template1", "ait", purpose, created_at))

            conn.execute('''
                INSERT INTO emergency_contacts (profile_id, contact_name, contact_phone, relation)
                VALUES (?, ?, ?, ?)
            ''', (profile_id, f"Contact {i}", f"+91 {random.randint(60000, 69999)} 00000", "Family"))

            for _ in range(random.randint(1, 2)):
                rtype = random.choice(['condition', 'allergy', 'medication'])
                desc = random.choice(conditions_list if rtype=='condition' else allergies_list if rtype=='allergy' else medications_list)
                conn.execute('INSERT INTO medical_records (profile_id, record_type, description) VALUES (?, ?, ?)', (profile_id, rtype, desc))

            for _ in range(random.randint(2, 5)):
                scanned_at = (datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S') + timedelta(hours=random.randint(1, 48))).strftime('%Y-%m-%d %H:%M:%S')
                ip = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
                conn.execute('INSERT INTO scan_logs (profile_id, scanned_at, ip_address, user_agent) VALUES (?, ?, ?, ?)', 
                             (profile_id, scanned_at, ip, "Mozilla/5.0 (Mobile Demo User)"))

        conn.commit()
        return "Database Seeded Successfully! You can now view the Admin Dashboard."
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)

