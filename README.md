# THE DARK ORDER - Halloween Play & Party Ticketing System

A complete Flask-based ticketing application for THE DARK ORDER HALLOWEEN PLAY AND PARTY event, featuring admin management, buyer ticket purchases via M-Pesa/PayHero, QR code validation, and automated PDF ticket delivery.

## Features

### Admin Flow
- **PIN-Based Login**: Secure 4-digit M-Pesa-style PIN authentication
- **Ticket Instance Management**: Create and manage ticket types with capacity and tiered pricing (Regular/VIP/VVIP)
- **QR Code Scanning**: Real-time ticket validation via camera or image upload
- **Scan Validation**:
  - ✅ Green for valid & unused tickets (marks as used)
  - ❌ Red for already-scanned tickets
  - ❌ Red for invalid/non-existent tickets
- **Comprehensive Logging**: All scans logged with ticket details

### Buyer Flow
- **Sign Up/Sign In**: Email + 4-digit PIN authentication
- **Forgot PIN**: Automatic random PIN generation sent via email
- **Ticket Selection**: Browse ticket instances with pricing cards
- **Shopping Cart**: Add multiple tickets with quantity and tier selection
- **M-Pesa Payment**: PayHero STK push integration
- **Ticket Delivery**: Automatic PDF generation and email delivery
- **My Tickets**: View all purchased tickets (newest first) with downloadable PDFs

### Payment & Tickets
- **PayHero Integration**: M-Pesa STK push with callback handling
- **UUID Ticket IDs**: Unique identifiers for each ticket
- **QR Code Generation**: Scannable codes with verification URLs
- **Haunted Theme PDFs**: Red/black Halloween-themed tickets with horror fonts
- **Email Delivery**: Automatic ticket delivery upon successful payment
- **No Expiration**: Tickets remain valid indefinitely

## Technology Stack

- **Backend**: Flask 3.1.2
- **Database**: PostgreSQL (via Replit)
- **ORM**: SQLAlchemy
- **Payment**: PayHero API (M-Pesa)
- **PDF Generation**: ReportLab
- **QR Codes**: qrcode + Pillow
- **Email**: SMTP (Gmail)
- **Frontend**: HTML5, CSS3, JavaScript
- **QR Scanning**: html5-qrcode library

## Database Schema

### Users
- `id` (Primary Key)
- `email` (Unique)
- `pin_hash` (Hashed 4-digit PIN)
- `created_at`

### Ticket Instances
- `id` (Primary Key)
- `name`
- `capacity`
- `regular_price`, `vip_price`, `vvip_price`
- `created_at`

### Tickets
- `id` (UUID, Primary Key)
- `client_id` (Foreign Key → Users)
- `ticket_instance_id` (Foreign Key → Ticket Instances)
- `tier` (regular/vip/vvip)
- `qr_code_url`, `qr_code_base64`
- `scanned_at` (nullable)
- `created_at`

### Payments
- `id` (Primary Key)
- `client_id` (Foreign Key → Users)
- `external_reference` (Unique)
- `amount`
- `status`
- `payment_metadata` (JSON cart data)
- `created_at`, `callback_received_at`

### Scan Logs
- `id` (Primary Key)
- `ticket_id`
- `scanned_at`
- `details`
- `result` (valid/already_scanned/invalid)

## Environment Variables

Required environment variables (configured in Replit Secrets):

```
DATABASE_URL              # PostgreSQL connection string
PAYHERO_BASIC_AUTH_TOKEN  # PayHero API authentication token
PAYHERO_CHANNEL_ID        # PayHero channel ID
ADMIN_PASSWORD            # 4-digit admin PIN
SECRET_KEY                # Flask session secret key
EMAIL_ADDRESS             # Sender email (Gmail)
EMAIL_APP_PASSWORD        # Gmail app-specific password
```

## Installation & Setup

1. **Clone Repository**
```bash
git clone <repository-url>
cd <project-directory>
```

2. **Install Dependencies**
```bash
pip install flask flask-sqlalchemy psycopg2-binary python-dotenv qrcode pillow reportlab requests werkzeug
```

3. **Configure Environment Variables**
Set all required environment variables in Replit Secrets or `.env` file.

4. **Run Application**
```bash
python app.py
```

The application will run on `http://0.0.0.0:5000`

## Usage Guide

### Admin Access

1. Navigate to `/admin/login`
2. Enter 4-digit admin PIN
3. Access dashboard with three options:
   - **Create Ticket Instance**: Add new ticket types
   - **Manage Ticket Instances**: View/delete instances
   - **Scan Tickets**: Validate tickets at entrance

### Buyer Flow

1. **Sign Up**: Navigate to `/signup`, create account with email + PIN
2. **Browse Tickets**: View available ticket instances
3. **Add to Cart**: Select quantity and tier, add multiple tickets
4. **Purchase**: Enter M-Pesa phone number, complete STK push
5. **Receive Tickets**: PDFs emailed automatically upon payment success
6. **View Tickets**: Access "My Tickets" tab to download PDFs

## PayHero Integration

### STK Push Request
```json
{
  "amount": 1000,
  "phoneNumber": "254712345678",
  "channel_id": 12345,
  "provider": "m-pesa",
  "external_reference": "uuid-string",
  "callback_url": "https://your-domain/api/payhero/callback",
  "metadata": {
    "client_id": 1,
    "cart": [{"instance_id": 1, "tier": "vip", "quantity": 2}]
  }
}
```

### Callback Handling
- **Success**: Generates tickets, creates PDFs, sends emails
- **Failure**: Marks payment as failed, allows retry

## Edge Cases Handled

1. ✅ **Deleting Ticket Instances**: Does NOT delete purchased tickets
2. ✅ **Multiple Purchases**: Tickets accumulate properly in My Tickets
3. ✅ **STK Push Timeout**: Error handling allows buyer retry
4. ✅ **Ticket Expiration**: Tickets never expire
5. ✅ **Session Security**: Buyers cannot access admin panel
6. ✅ **Scan Validation**: Prevents duplicate scanning

## Security Features

- **Hashed PINs**: Werkzeug password hashing for all user PINs
- **Session Management**: Flask sessions with SECRET_KEY
- **Role Separation**: Admin and buyer sessions are isolated
- **HTTPS Required**: PayHero callbacks require HTTPS endpoints

## Theme & Design

- **Color Scheme**: Red (#cc0000) and black (#1a0000)
- **Typography**: Helvetica-Bold for headers, readable fonts for details
- **PDF Design**: Haunted Halloween theme with QR codes
- **Responsive**: Mobile-friendly design

## Logging

All critical operations are logged:
- Admin login attempts
- Ticket instance creation/deletion
- Payment STK push requests
- PayHero callback responses
- Ticket generation events
- QR scan validations
- Email delivery status

## API Endpoints

### Public Routes
- `GET /` - Homepage
- `GET /signup` - Sign up page
- `GET /signin` - Sign in page
- `POST /forgot-pin` - Request PIN reset

### Admin Routes (Protected)
- `POST /admin/login` - Admin authentication
- `GET /admin/dashboard` - Admin dashboard
- `GET /admin/create-ticket-instance` - Create instance form
- `POST /admin/create-ticket-instance` - Create instance
- `GET /admin/manage-instances` - List instances
- `POST /admin/delete-instance/<id>` - Delete instance
- `GET /admin/scan` - Scan interface
- `POST /admin/verify-ticket` - Validate ticket

### Buyer Routes (Protected)
- `GET /tickets` - Browse tickets
- `POST /purchase` - Initiate payment
- `GET /my-tickets` - View purchased tickets
- `GET /download-ticket/<id>` - Download PDF

### Callback Routes
- `POST /api/payhero/callback` - PayHero payment callback

### Verification Routes
- `GET /ticket/verify/<id>` - Public ticket verification

## Development Notes

- Database tables are created automatically on first run
- Flask debug mode is enabled (disable in production)
- Uses development server (use Gunicorn for production)
- Email requires Gmail with app-specific password

## Troubleshooting

### Email Not Sending
- Verify `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` are correct
- Enable "Less secure app access" or use app-specific password in Gmail

### PayHero Callback Not Received
- Ensure callback URL is HTTPS
- Check PayHero dashboard for webhook logs
- Verify `PAYHERO_BASIC_AUTH_TOKEN` is correct

### QR Scanning Not Working
- Grant camera permissions in browser
- Try image upload as fallback
- Ensure ticket URL format is correct

## License

This project is proprietary software for THE DARK ORDER HALLOWEEN PLAY AND PARTY event.

## Support

For technical support or feature requests, contact the development team.
