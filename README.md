# Annadhan - AI Powered Food Rescue Platform

Annadhan connects Restaurants, NGOs, Orphanages, and Delivery Runners to reduce food waste and distribute excess food to people in need.

## Run

```bash
cd Annadhan/backend
python3 app.py
```

If you extracted the zip as `FoodBridge`, use:

```bash
cd FoodBridge/backend
python3 app.py
```

## Important .env

Create `.env` in the main project folder:

```env
SECRET_KEY=change-this-secret
MONGO_URI=mongodb://localhost:27017/annadhan
MAIL_USERNAME=yourgmail@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=yourgmail@gmail.com
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
BASE_URL=http://127.0.0.1:5000
```

## New Updates

- Project branding changed to Annadhan.
- New landing dashboard with food donation illustration, quotes, Login and Register buttons.
- Annadhan Helper Assistant chatbot added for registration, login, donation, GPS, QR, and dashboard instructions.
- Registration validates name, email, password, confirm password, role, and full address.
- Password and confirm password must match before saving.
- Live GPS location capture is used instead of manual latitude/longitude fields.
- Logging is enabled for the full backend.
