import os
import uuid
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import qrcode
from io import BytesIO
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import json
import random
import string

load_dotenv()

app = Flask(__name__)

# Use connection pooling to handle Neon's sleep behavior
database_url = os.getenv('DATABASE_URL')
if database_url and '.us-east-2' in database_url:
    database_url = database_url.replace('.us-east-2', '-pooler.us-east-2')

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    pin_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tickets = db.relationship('Ticket', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)

class TicketInstance(db.Model):
    __tablename__ = 'ticket_instances'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    regular_price = db.Column(db.Float, nullable=True)
    vip_price = db.Column(db.Float, nullable=True)
    vvip_price = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tickets = db.relationship('Ticket', backref='ticket_instance', lazy=True)

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
   ticket_instance_id = db.Column(
    db.Integer,
    db.ForeignKey('ticket_instances.id', ondelete='SET NULL'),
    nullable=True
)

    tier = db.Column(db.String(20), nullable=False)
    qr_code_url = db.Column(db.Text, nullable=False)
    qr_code_base64 = db.Column(db.Text, nullable=False)
    scanned_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_path = db.Column(db.String(500), nullable=True)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    external_reference = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    payment_metadata = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    callback_received_at = db.Column(db.DateTime, nullable=True)

class ScanLog(db.Model):
    __tablename__ = 'scan_logs'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.String(36), nullable=True)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)
    result = db.Column(db.String(50), nullable=False)

# Initialize database
with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully")

# Helper Functions
def generate_qr_code(ticket_id):
    base_url = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
    if not base_url.startswith('http'):
        base_url = f'https://{base_url}'
    qr_url = f"{base_url}/ticket/verify/{ticket_id}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return img_base64, qr_url

def generate_pdf_ticket(ticket, user_email):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Red/Black Halloween theme
    c.setFillColorRGB(0.1, 0, 0)
    c.rect(0, 0, width, height, fill=True)
    
    c.setFillColorRGB(0.8, 0, 0)
    c.rect(0.5*inch, height - 2*inch, width - 1*inch, 1.5*inch, fill=True)
    
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width/2, height - 1.2*inch, "THE DARK ORDER")
    
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height - 1.6*inch, "HALLOWEEN PLAY & PARTY")
    
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 3*inch, f"Ticket Instance: {ticket.ticket_instance.name}")
    c.drawString(1*inch, height - 3.5*inch, f"Tier: {ticket.tier.upper()}")
    capacity_text = f"Covers: {ticket.ticket_instance.capacity} {'person' if ticket.ticket_instance.capacity == 1 else 'people'}"
    c.drawString(1*inch, height - 4*inch, capacity_text)
    c.drawString(1*inch, height - 4.5*inch, f"Ticket ID: {ticket.id}")
    c.drawString(1*inch, height - 5*inch, f"Email: {user_email}")
    
    # QR Code
    qr_data, _ = generate_qr_code(ticket.id)
    qr_image = ImageReader(BytesIO(base64.b64decode(qr_data)))
    c.drawImage(qr_image, width/2 - 1.5*inch, height - 8.5*inch, width=3*inch, height=3*inch)
    
    c.setFillColorRGB(0.8, 0, 0)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, height - 9*inch, "SCAN QR CODE AT ENTRANCE")
    
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, 1*inch, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    c.save()
    buffer.seek(0)
    return buffer

def send_email_with_tickets(to_email, tickets, user):
    try:
        attachments = []
        for ticket in tickets:
            pdf_buffer = generate_pdf_ticket(ticket, to_email)
            pdf_content = pdf_buffer.read()
            attachments.append(
                Attachment(
                    FileContent(base64.b64encode(pdf_content).decode()),
                    FileName(f"ticket_{ticket.id}.pdf"),
                    FileType("application/pdf"),
                    Disposition("attachment")
                )
            )

        body = f"""
        <html>
        <body style="background-color: #1a0000; color: #ffffff; font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #cc0000;">THE DARK ORDER HALLOWEEN PLAY & PARTY</h1>
            <p>Dear Guest,</p>
            <p>Your tickets have been confirmed! Please find your ticket(s) attached as PDF files.</p>
            <p>Each ticket contains a unique QR code. Please present this QR code at the entrance.</p>
            <p style="color: #cc0000;"><strong>Total Tickets: {len(tickets)}</strong></p>
            <p>We look forward to seeing you at the event!</p>
            <p style="color: #666;">This is an automated email. Please do not reply.</p>
        </body>
        </html>
        """

        message = Mail(
            from_email=os.getenv('EMAIL_ADDRESS'),
            to_emails=to_email,
            subject="Your Dark Order Halloween Tickets",
            html_content=body
        )

        if attachments:
            message.attachment = attachments

        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        sg.send(message)

        logger.info(f"Email sent successfully to {to_email} with {len(tickets)} tickets via SendGrid")
        return True

    except Exception as e:
        logger.error(f"Email sending failed via SendGrid: {str(e)}")
        return False

# Routes - Home
@app.route('/')
def index():
    return render_template('index.html')

# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pin = request.json.get('pin')
        if pin == os.getenv('ADMIN_PASSWORD'):
            session['admin'] = True
            logger.info("Admin logged in successfully")
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid PIN'}), 401
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')

@app.route('/admin/create-ticket-instance', methods=['GET', 'POST'])
def create_ticket_instance():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        data = request.json
        ticket_instance = TicketInstance(
            name=data['name'],
            capacity=data['capacity'],
            regular_price=data.get('regular_price'),
            vip_price=data.get('vip_price'),
            vvip_price=data.get('vvip_price')
        )
        db.session.add(ticket_instance)
        db.session.commit()
        logger.info(f"Ticket instance created: {ticket_instance.name}")
        return jsonify({'success': True, 'id': ticket_instance.id})
    
    return render_template('create_ticket_instance.html')

@app.route('/admin/manage-instances')
def manage_instances():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    instances = TicketInstance.query.all()
    return render_template('manage_instances.html', instances=instances)

@app.route('/admin/delete-instance/<int:instance_id>', methods=['POST'])
def delete_instance(instance_id):
    if not session.get('admin'):
        return jsonify({'success': False}), 401
    
    instance = TicketInstance.query.get(instance_id)
    if instance:
        db.session.delete(instance)
        db.session.commit()
        logger.info(f"Ticket instance deleted: {instance.name} (ID: {instance_id})")
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/admin/scan')
def admin_scan():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin_scan.html')

@app.route('/admin/verify-ticket', methods=['POST'])
def verify_ticket():
    if not session.get('admin'):
        return jsonify({'success': False}), 401
    
    ticket_id = request.json.get('ticket_id')
    ticket = Ticket.query.get(ticket_id)
    
    if not ticket:
        log = ScanLog(ticket_id=ticket_id, result='invalid', details='Ticket not found in database')
        db.session.add(log)
        db.session.commit()
        logger.warning(f"Invalid ticket scanned: {ticket_id}")
        return jsonify({'success': False, 'status': 'invalid', 'message': 'Invalid Ticket'})
    
    if ticket.scanned_at:
        log = ScanLog(ticket_id=ticket_id, result='already_scanned', 
                     details=f'Already scanned at {ticket.scanned_at}')
        db.session.add(log)
        db.session.commit()
        logger.warning(f"Already scanned ticket: {ticket_id}")
        return jsonify({'success': False, 'status': 'already_scanned', 
                       'message': 'Ticket Already Scanned',
                       'scanned_at': ticket.scanned_at.strftime('%Y-%m-%d %H:%M:%S')})
    
    ticket.scanned_at = datetime.utcnow()
    log = ScanLog(ticket_id=ticket_id, result='valid', 
                 details=f'Ticket: {ticket.ticket_instance.name}, Tier: {ticket.tier}')
    db.session.add(log)
    db.session.commit()
    logger.info(f"Ticket scanned successfully: {ticket_id}")
    
    return jsonify({
        'success': True,
        'status': 'valid',
        'ticket': {
            'id': ticket.id,
            'instance': ticket.ticket_instance.name,
            'tier': ticket.tier,
            'capacity': f"Covers {ticket.ticket_instance.capacity} {'person' if ticket.ticket_instance.capacity == 1 else 'people'}",
            'email': ticket.user.email
        }
    })

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

# Buyer Routes
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.json
        email = data['email']
        pin = data['pin']
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already exists'}), 400
        
        user = User(email=email, pin_hash=generate_password_hash(pin))
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        logger.info(f"New user registered: {email}")
        return jsonify({'success': True})
    
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        data = request.json
        email = data['email']
        pin = data['pin']
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.pin_hash, pin):
            session['user_id'] = user.id
            logger.info(f"User signed in: {email}")
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    
    return render_template('signin.html')

@app.route('/forgot-pin', methods=['POST'])
def forgot_pin():
    data = request.json
    email = data['email']
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({'success': False, 'error': 'Email not found'}), 404
    
    new_pin = ''.join(random.choices(string.digits, k=4))
    user.pin_hash = generate_password_hash(new_pin)
    db.session.commit()
    
    try:
        body = f"""
        <html>
        <body style="background-color: #1a0000; color: #ffffff; font-family: Arial, sans-serif; padding: 20px;">
            <h1 style="color: #cc0000;">PIN Reset</h1>
            <p>Your new PIN is: <strong style="font-size: 24px; color: #cc0000;">{new_pin}</strong></p>
            <p>Please use this PIN to sign in to your account.</p>
        </body>
        </html>
        """

        message = Mail(
            from_email=os.getenv('EMAIL_ADDRESS'),
            to_emails=email,
            subject="Your New PIN - Dark Order",
            html_content=body
        )

        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        sg.send(message)

        logger.info(f"PIN reset email sent to {email} via SendGrid")
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Failed to send PIN reset email via SendGrid: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to send email'}), 500
@app.route('/tickets')
def ticket_selection():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    instances = TicketInstance.query.all()
    instances_data = [{
        'id': instance.id,
        'name': instance.name,
        'capacity': instance.capacity,
        'regular_price': instance.regular_price,
        'vip_price': instance.vip_price,
        'vvip_price': instance.vvip_price
    } for instance in instances]
    
    return render_template('tickets.html', instances=instances, instances_json=instances_data)

@app.route('/purchase', methods=['POST'])
def purchase():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please sign in first'}), 401
    
    data = request.json
    phone_number = data.get('phoneNumber', '')
    cart = data.get('cart', [])
    
    if not phone_number or not cart:
        return jsonify({'success': False, 'error': 'Phone number and cart items are required'}), 400
    
    # Validate phone number format
    if not phone_number.startswith('254') or len(phone_number) != 12:
        return jsonify({'success': False, 'error': 'Invalid phone number format. Use 254XXXXXXXXX'}), 400
    
    total_amount = 0
    for item in cart:
        instance = db.session.get(TicketInstance, item['instance_id'])
        if not instance:
            return jsonify({'success': False, 'error': f'Ticket instance {item["instance_id"]} not found'}), 404
            
        if item['tier'] == 'regular':
            total_amount += instance.regular_price * item['quantity']
        elif item['tier'] == 'vip':
            total_amount += instance.vip_price * item['quantity']
        elif item['tier'] == 'vvip':
            total_amount += instance.vvip_price * item['quantity']
    
    external_reference = str(uuid.uuid4())
    
    payment = Payment(
        client_id=session['user_id'],
        external_reference=external_reference,
        amount=total_amount,
        status='pending',
        payment_metadata=json.dumps(cart)
    )
    db.session.add(payment)
    db.session.commit()
    
    base_url = os.getenv('REPLIT_DEV_DOMAIN', 'localhost:5000')
    if not base_url.startswith('http'):
        base_url = f'https://{base_url}'
    
    payhero_data = {
        "amount": int(total_amount),
        "phone_number": phone_number,
        "channel_id": int(os.getenv('PAYHERO_CHANNEL_ID')),
        "provider": "m-pesa",
        "external_reference": external_reference,
        "callback_url": f"{base_url}/api/payhero/callback"
    }
    
    headers = {
        'Authorization': f'Basic {os.getenv("PAYHERO_BASIC_AUTH_TOKEN")}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post('https://backend.payhero.co.ke/api/v2/payments', 
                               json=payhero_data, headers=headers, timeout=30)
        response_data = response.json()
        
        logger.info(f"PayHero Response: {response_data}")
        logger.info(f"STK Push initiated for {phone_number}, amount: {total_amount}, ref: {external_reference}")
        
        if response.status_code == 200 or response.status_code == 201:
            return jsonify({'success': True, 'reference': external_reference, 'payhero_response': response_data})
        else:
            logger.error(f"PayHero error: {response_data}")
            payment.status = 'failed'
            db.session.commit()
            return jsonify({'success': False, 'error': response_data.get('message', 'Payment initiation failed')}), 500
            
    except Exception as e:
        logger.error(f"STK Push failed: {str(e)}")
        payment.status = 'failed'
        db.session.commit()
        return jsonify({'success': False, 'error': f'Payment system error: {str(e)}'}), 500

@app.route('/api/payhero/callback', methods=['POST'])
def payhero_callback():
    data = request.json
    logger.info(f"PayHero callback received: {json.dumps(data)}")
    
    # PayHero callback format: data['response'] contains the transaction details
    response_data = data.get('response', {})
    external_reference = response_data.get('ExternalReference')
    result_code = response_data.get('ResultCode')
    result_desc = response_data.get('ResultDesc', '')
    payment_status = response_data.get('Status', '')
    
    if not external_reference:
        logger.error(f"No external reference in callback: {data}")
        return jsonify({'success': False, 'error': 'Missing external reference'}), 400
    
    payment = Payment.query.filter_by(external_reference=external_reference).first()
    if not payment:
        logger.error(f"Payment not found for reference: {external_reference}")
        return jsonify({'success': False}), 404
    
    # ResultCode 0 means success
    if result_code == 0 and payment_status == 'Success':
        payment.status = 'success'
        payment.callback_received_at = datetime.utcnow()
        db.session.commit()
        
        cart = json.loads(payment.payment_metadata)
        user = User.query.get(payment.client_id)
        tickets = []
        
        for item in cart:
            for _ in range(item['quantity']):
                ticket_id = str(uuid.uuid4())
                qr_data, qr_url = generate_qr_code(ticket_id)
                
                ticket = Ticket(
                    id=ticket_id,
                    client_id=payment.client_id,
                    ticket_instance_id=item['instance_id'],
                    tier=item['tier'],
                    qr_code_url=qr_url,
                    qr_code_base64=qr_data
                )
                db.session.add(ticket)
                tickets.append(ticket)
        
        db.session.commit()
        logger.info(f"Generated {len(tickets)} tickets for payment {external_reference}")
        
        send_email_with_tickets(user.email, tickets, user)
    else:
        payment.status = 'failed'
        payment.callback_received_at = datetime.utcnow()
        db.session.commit()
        logger.warning(f"Payment failed: {result_desc} (Code: {result_code})")
    
    return jsonify({'success': True})

@app.route('/my-tickets')
def my_tickets():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    tickets = Ticket.query.filter_by(client_id=session['user_id']).order_by(Ticket.created_at.desc()).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/download-ticket/<ticket_id>')
def download_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket or ticket.client_id != session['user_id']:
        return "Ticket not found", 404
    
    user = User.query.get(session['user_id'])
    pdf_buffer = generate_pdf_ticket(ticket, user.email)
    
    return send_file(pdf_buffer, as_attachment=True, download_name=f'ticket_{ticket_id}.pdf', mimetype='application/pdf')

@app.route('/ticket/verify/<ticket_id>')
def verify_ticket_page(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return render_template('verify_ticket.html', valid=False, message='Invalid Ticket')
    
    return render_template('verify_ticket.html', valid=True, ticket=ticket)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
