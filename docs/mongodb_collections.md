# MongoDB Collections

## users
name, email, password, role, phone, address, capacity, latitude, longitude, created_at

## donations
restaurant_id, restaurant_name, order_id (unique, e.g. FB-7K2R9Q), food_type, food_items[], quantity, preparation_time, expiry_time, location, latitude, longitude, food_image, status (Available | Accepted | Picked Up | Delivered | Deleted), ngo_id, runner_id, qr_path, recommended_ngo, created_at, updated_at

## issues  (Contact Us / Report a Problem)
reporter_id, reporter_role, reporter_name, reporter_phone, reporter_email, category, message, attachment (relative static path, image or video), status (Open | Resolved), created_at, resolved_at

## locations
user_id, role, latitude, longitude, timestamp

## messages
sender, receiver, message, timestamp

## Updated users collection fields

Registration now stores a required full address and optional browser GPS location:

```json
{
  "name": "Restaurant / NGO / Runner name",
  "email": "user@example.com",
  "password": "bcrypt_hash",
  "role": "restaurant | ngo | runner | admin",
  "phone": "optional phone",
  "address": "printable full address",
  "address_details": {
    "door_no": "D/No or flat no",
    "building_name": "building / apartment",
    "street": "street name",
    "area": "area / locality",
    "city": "city",
    "district": "district",
    "state": "state",
    "pincode": "6 digit pincode",
    "landmark": "nearby landmark"
  },
  "live_location_name": "browser GPS label",
  "gps_location": {
    "latitude": 17.000000,
    "longitude": 78.000000
  },
  "created_at": "UTC datetime",
  "updated_at": "UTC datetime"
}
```

## Logs

Application logs are written to:

```text
logs/annadhan.log
```

Rotating backups are created automatically when the log file grows.
