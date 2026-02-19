Here's the humanised version:



# Healthcare Appointments — Frappe Custom App

A custom Frappe + ERPNext app I built as part of a technical assignment. It lets a clinic manage appointment bookings through a public-facing page, and automatically generates a paid Sales Invoice in ERPNext for every booking, no patient login needed.

**Stack:** Frappe v15 · ERPNext v15 · Python 3.10 · MariaDB · Redis



## Getting Started

### 1. Install Frappe Bench

```bash
pip install frappe-bench

bench init frappe-bench --frappe-branch version-15
cd frappe-bench
```

### 2. Create a Site and Install ERPNext

```bash
bench new-site clinic.localhost --db-password <your-db-password>

bench get-app erpnext --branch version-15
bench --site clinic.localhost install-app erpnext
```

### 3. Install This App

```bash
bench get-app https://github.com/HarpreetKaur29/healthcare_appointments

bench --site clinic.localhost install-app healthcare_appointments
bench --site clinic.localhost migrate
```

### 4. One-Time ERPNext Setup

Log into the desk and make sure these master records exist. They're standard ERPNext records and are usually already there if you ran the setup wizard.

| Requirement | Where to find it |
|||
| Mode of Payment: **Cash** | Accounting > Setup > Mode of Payment |
| Item Group: **Services** | Stock > Setup > Item Group |
| Customer Group: **All Customer Groups** | Selling > Setup > Customer Group |
| Territory: **All Territories** | Selling > Setup > Territory |



## Running the App

```bash
bench start
```

This starts the web server, Redis, and background workers together. Then open:

**Public booking page** (no login needed):
`http://clinic.localhost:8000/book-appointment`

**Admin desk** (appointments, invoices, services):
`http://clinic.localhost:8000/app`

> Swap `clinic.localhost` for whatever site name you used in `bench new-site`.



## How Booking Works

The patient lands on the public page, picks a service, selects a date and time, fills in their details, and submits. That's it from their end.

Behind the scenes:

- An appointment record gets created and validated
- A paid Sales Invoice is generated automatically
- Both the Appointment ID and Invoice ID are shown on screen as confirmation



## Running Tests

```bash
bench --site clinic.localhost set-config allow_tests true
bench --site clinic.localhost run-tests --app healthcare_appointments
```

Expected: `25 tests · 0 failures · 0 errors`

The tests cover working hour validation, overlap detection, end time calculation, the full public booking flow, and Sales Invoice creation.



## What I Built

### Healthcare Service DocType
The clinic's service catalog. Each service has a name (used as the document ID), a price, a duration in minutes, and an optional description. Duration drives the end time calculation; price gets copied into every appointment.

### Clinic Appointment DocType
The main booking record, auto-named as `APPT-2026-00001` and so on. Most fields are filled in by the patient, but a few are read-only and set automatically by the system: estimated end time, total amount, and the linked Sales Invoice.

### Working Hours Validation
Bookings are only allowed between 09:00 AM and 05:00 PM. Anything outside that range gets rejected with a validation error. This runs inside `before_save()` so it applies to both desk and public bookings.

### Overlap Detection
I went with proper time-range overlap detection rather than just checking for exact time matches. Two appointments overlap when:

```
new_start < existing_end  AND  new_end > existing_start
```

So a 10:30 booking for a 15-minute service (ending 10:45) will block anything at 10:35, even though the start times differ. Cancelled appointments are excluded from this check.

### Automatic End Time and Amount Calculation
On every save, the system fetches the selected service, adds its duration using Python's `timedelta`, and writes the result into `estimated_end_time`. The service price gets copied into `total_amount` at the same time. This recalculates every time the record is saved, so changing the service mid-edit always stays accurate.

### Public Booking Page
Built using Frappe's `www/` routing, so the file just lives in the `www/` folder and becomes a public URL automatically. Services are injected into the page at render time via `get_context()`, so the dropdown is pre-populated with no extra API call. End time preview and form submission use `frappe.call` to whitelisted server methods.

### Automatic Sales Invoice Creation
Once a booking goes through, `accounting_utils.py` kicks in. It creates a Sales Invoice with `is_pos = 1`, adds the service as a line item, appends a Cash payment entry for the full amount, and submits it. ERPNext marks it as Paid automatically. The invoice name is then written back to the appointment record. No manual payment entry required.

### Completion Logging
When an appointment's status is changed to Completed, a log entry is written via `frappe.logger()` for basic audit tracking.



## Design Decisions

**Why two DocTypes?** Services are master data, appointments are transactions. Keeping them separate means I'm not duplicating service details across every booking row, just linking to it.

**Why controller lifecycle methods over hooks.py?** `hooks.py` is for reacting to events on other apps' DocTypes. Since I own this one, `before_save()` and `on_update()` inside the controller class is the right place.

**Why a separate `accounting_utils.py`?** Keeps things modular. The controller handles appointment logic, `web_methods.py` handles HTTP, and `accounting_utils.py` handles the ERPNext integration. Each file has one job.



## Assumptions and Limitations

The app assumes a single clinic location, a Cash mode of payment, an item group called Services, and uses a generic Walk-in Customer for all public bookings.

It does not currently support patient accounts, public cancellations, email or SMS notifications, or recurring appointments. These would be reasonable next steps for a production version.