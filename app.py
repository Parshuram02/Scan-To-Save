from flask import Flask, render_template, request,jsonify, redirect, url_for, send_file
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

app = Flask(__name__)

app.config['PWA_APP_NAME'] = "Emergency QR"
app.config['PWA_APP_DESCRIPTION'] = "Offline support for emergency QR code details"
app.config['PWA_APP_THEME_COLOR'] = "#ffffff"
app.config['PWA_APP_BACKGROUND_COLOR'] = "#000000"
app.config['PWA_APP_DISPLAY'] = "standalone"
app.config['PWA_APP_SCOPE'] = "/"
app.config['PWA_APP_START_URL'] = "/"
#pwa = PWA(app)




def init_db():
    """Initialize the SQLite database and create tables if they don't exist"""
    conn = sqlite3.connect('profiles.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT NOT NULL,
            blood_group TEXT,
            template TEXT,
            phone TEXT,
            password TEXT,
            emergency_contact TEXT,
            medical_conditions TEXT,
            allergies TEXT,
            medications TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect('profiles.db')
    conn.row_factory = sqlite3.Row  # This enables name-based access to columns
    return conn

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
                id, name, phone, blood_group, template, password,
                emergency_contact, medical_conditions, allergies, medications
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            profile_id,
            request.form['name'],
            request.form['phone'],
            request.form['blood_group'],
            request.form['template'],
            request.form['password'],
            request.form.get('emergency_contact'),
            request.form.get('medical_conditions'),
            request.form.get('allergies'),
            request.form.get('medications')
        ))
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

@app.route('/profile/<profile_id>')
def view_profile(profile_id):
    conn = get_db()
    try:
        profile = conn.execute(
            'SELECT * FROM profiles WHERE id = ?', 
            (profile_id,)
        ).fetchone()
        
        if profile is None:
            return "Profile not found", 404
            
        # Check for password if provided
        provided_password = request.args.get('password')
        show_sensitive = provided_password and provided_password == profile['password']
        
        return render_template('profile_view.html', 
                             profile=dict(profile),  # Convert Row to dict
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
                
            # Update profile
            conn.execute('''
                UPDATE profiles 
                SET name = ?,
                    phone = ?,
                    blood_group = ?,
                    emergency_contact = ?,
                    medical_conditions = ?,
                    allergies = ?,
                    medications = ?
                WHERE id = ?
            ''', (
                request.form['name'],
                request.form['phone'],
                request.form['blood_group'],
                request.form.get('emergency_contact'),
                request.form.get('medical_conditions'),
                request.form.get('allergies'),
                request.form.get('medications'),
                profile_id
            ))
            conn.commit()
            return redirect(url_for('view_profile', profile_id=profile_id))
            
        # GET request - show edit form
        profile = conn.execute(
            'SELECT * FROM profiles WHERE id = ?', 
            (profile_id,)
        ).fetchone()
        
        if profile is None:
            return "Profile not found", 404
            
        return render_template('edit_profile.html', profile=dict(profile))
        
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


        
if __name__ == '__main__':
    app.run(debug=True)

