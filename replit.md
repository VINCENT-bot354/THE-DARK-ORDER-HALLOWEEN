# THE DARK ORDER - Halloween Play & Party Ticketing System

## Overview

A Flask-based event ticketing platform for THE DARK ORDER HALLOWEEN PLAY AND PARTY. The system features two completely separated user flows: an admin panel for event management and ticket validation, and a buyer portal for purchasing tickets via M-Pesa. The application handles the complete ticketing lifecycle from purchase through payment processing to ticket delivery and validation at the event entrance.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Web Framework**: Flask 3.1.2 serves as the backend framework, handling routing, session management, and request processing
- **Database ORM**: SQLAlchemy manages database interactions with PostgreSQL
- **Session Management**: Flask sessions with SECRET_KEY for secure user authentication and state management

### Authentication & Authorization
- **Dual Authentication System**: Separate authentication flows for admin and buyers
  - Admin: 4-digit PIN validation against ADMIN_PASSWORD environment variable
  - Buyers: Email + 4-digit PIN stored as hashed values in the database
- **Password Recovery**: Automated PIN reset via email with randomly generated 4-digit PINs
- **Session-Based Access Control**: Role separation prevents buyers from accessing admin endpoints

### Payment Processing Architecture
- **Payment Gateway**: PayHero integration for M-Pesa STK Push payments
- **Async Callback Pattern**: Payment confirmation handled via webhook callbacks
- **Payment Flow**:
  1. Buyer initiates purchase with M-Pesa phone number
  2. STK Push request sent to PayHero with amount, phone, channel_id, provider, external_reference, callback_url, and metadata
  3. Callback endpoint receives payment status and processes accordingly
  4. Success triggers ticket generation pipeline; failure allows retry

### Ticket Generation & Delivery Pipeline
- **Unique Identification**: UUID-based ticket IDs for each individual ticket
- **QR Code System**: 
  - Generated using qrcode + Pillow libraries
  - Encodes verification URL pattern: /ticket/verify/<ticket_id>
  - No expiration mechanism (tickets valid indefinitely)
- **PDF Generation**: 
  - ReportLab creates themed PDF tickets
  - Halloween aesthetic: red/black color scheme, horror fonts for headers
  - Embedded QR codes for scanning
  - Critical information (ID, tier, event name) uses readable fonts
- **Automated Email Delivery**: SMTP (Gmail) sends tickets automatically upon successful payment

### Ticket Validation System
- **Multi-Input Scanning**: 
  - Camera-based scanning using html5-qrcode library (back camera priority)
  - Image upload option for manual QR code scanning
- **Three-State Validation Logic**:
  - Valid & Unused: Green display, mark as scanned, show ticket details
  - Already Scanned: Red display, "Ticket Already Scanned" message
  - Invalid/Non-existent: Red display, "Invalid Ticket" message
- **Audit Trail**: All scan attempts logged with ticket details and timestamps

### Data Model Architecture
- **Users Table**: Stores buyer accounts (id, email, pin_hash, created_at) with relationships to tickets and payments
- **Ticket Instances Table**: Event-level ticket types with capacity and tiered pricing (Regular/VIP/VVIP)
- **Tickets Table**: Individual purchased tickets linked to users and ticket instances, includes QR codes and scan status
- **Payments Table**: Transaction records linked to users, stores payment status and metadata
- **Data Integrity**: Deleting ticket instances does NOT cascade delete purchased tickets (soft reference model)

### Frontend Architecture
- **Template Engine**: Jinja2 templates for server-side rendering
- **Styling**: Custom CSS with Halloween theme (gradient backgrounds, red accents, shadow effects)
- **JavaScript Interactions**: 
  - PIN input with auto-advance functionality
  - AJAX requests for form submissions
  - Tab-based navigation for buyer portal
  - Real-time QR scanning with html5-qrcode
- **Responsive Design**: Mobile-first approach for ticket purchases and scanning

### Shopping Cart Pattern
- **Client-Side State Management**: Cart stored in browser memory during session
- **Multi-Ticket Support**: Users can add multiple ticket instances with different quantities and tiers
- **Accumulation Logic**: Cart items accumulate; X icon allows removal of individual selections
- **Batch Processing**: All cart items processed in single payment transaction

### Security Measures
- **Password Hashing**: werkzeug.security for PIN storage (generate_password_hash/check_password_hash)
- **Environment Variables**: Sensitive credentials (database URL, API tokens, email passwords) externalized
- **Session Security**: Flask SECRET_KEY for session signing
- **File Upload Limits**: MAX_CONTENT_LENGTH set to 16MB for image uploads
- **Logging**: Comprehensive logging of payments, STK pushes, scans, and ticket generation

### Error Handling & Edge Cases
- **Payment Timeout Handling**: STK push may timeout; buyers can retry purchase
- **Orphaned Instance Protection**: Ticket instances can be deleted without affecting purchased tickets
- **Multiple Purchase Support**: Users can make repeated purchases; tickets accumulate in "My Tickets"
- **Email Delivery Failures**: Logged but don't block ticket generation
- **Scan State Pause**: Scanner pauses after each scan to display result; "Scan Next Ticket" clears for next scan

## External Dependencies

### Payment Services
- **PayHero API**: M-Pesa payment processing
  - Requires: PAYHERO_BASIC_AUTH_TOKEN, PAYHERO_CHANNEL_ID
  - Endpoints: STK Push initiation, callback webhook
  - Provider: "m-pesa" with dynamic callback URLs

### Email Service
- **SMTP (Gmail)**: Ticket delivery via email
  - Requires: EMAIL_ADDRESS, EMAIL_APP_PASSWORD
  - MIME multipart messages with PDF attachments
  - Automated sending on successful payment

### Database
- **PostgreSQL**: Primary data store via Replit
  - Connection: DATABASE_URL environment variable
  - ORM: SQLAlchemy with relationship mapping

### Third-Party Libraries
- **QR Code Generation**: qrcode + Pillow for image creation
- **PDF Generation**: ReportLab for ticket PDF creation
- **QR Scanning**: html5-qrcode JavaScript library for camera/upload scanning
- **HTTP Requests**: requests library for PayHero API communication

### Environment Configuration
Required environment variables:
- DATABASE_URL (PostgreSQL connection)
- PAYHERO_BASIC_AUTH_TOKEN (API authentication)
- PAYHERO_CHANNEL_ID (Payment channel identifier)
- ADMIN_PASSWORD (4-digit admin PIN)
- SECRET_KEY (Flask session signing)
- EMAIL_ADDRESS (SMTP sender)
- EMAIL_APP_PASSWORD (SMTP authentication)