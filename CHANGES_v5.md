# Annadhan v5 — Change Summary

## What's Fixed & Added

### 1. Language Switcher (Fixed)
- Language change now actually updates text on page
- Saved language preference remembered across page loads (localStorage)
- All dashboard labels have `data-i18n` attributes

### 2. New Food Listing Form (Restaurant)
- Redesigned to match screenshot: Food Item, Quantity, Unit (dropdown), Pickup By, Expires In, Notes
- Unit dropdown: portions, plates, kg, litres, packets, pieces
- "+ Add item" button to add multiple food rows

### 3. OTP System (Replaces QR Codes)
- 6-digit numeric OTP only (no alphabets)
- **Flow for NGO self-pickup:** Restaurant gives 1 OTP → NGO enters it to confirm pickup
- **Flow with Runner:**
  - OTP 1: Restaurant gives Pickup OTP → Runner enters it to confirm food collected
  - OTP 2: NGO generates Delivery OTP → Runner enters it to confirm food delivered to NGO
- OTPs shown in large, clear monospace font

### 4. History Tab (Restaurant Dashboard)
- Shows all past listings with status badges
- Shows WHO took the food: NGO name and/or Runner name
- Shows Pickup OTP and verification status

### 5. History Tab (NGO Dashboard)
- New 3-tab layout: Available / Active / History
- History tab shows all completed deliveries

### 6. Runner Map in NGO Dashboard (Active tab)
- When runner is assigned, NGO sees "Open Live Map" button
- Fetches latest GPS coordinates from runner
- Auto-refreshes every 30 seconds

### 7. Who Took the Order (Tracking)
- Restaurant history shows: NGO name + Runner name
- Status badges: Available / Accepted / Picked Up / Delivered

### 8. Delivery Type Field
- Restaurant can specify: NGO Self Pickup / Runner Delivery / Either
- NGO can select when accepting: "I'll collect myself" or "Send a runner"

### 9. Email Notifications (Fixed)
- Graceful fail if .env credentials not set (no crash)
- Better email body with all new fields (unit, pickup_by, expires_in, notes)
- Warning logged if email not configured

## .env Requirements
```
MONGO_URI=mongodb+srv://siddhardhavenat_db_user:<password>@cluster0.rc4wuwp.mongodb.net/annadhan
SECRET_KEY=your-random-secret-key
MAIL_USERNAME=yourgmail@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=yourgmail@gmail.com
```
For Gmail: use App Password (not your regular password). Enable 2FA → Google Account → Security → App Passwords.
