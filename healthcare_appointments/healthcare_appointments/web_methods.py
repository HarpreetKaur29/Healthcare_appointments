
"""Whitelisted API methods called by the public book-appointment web page.

All methods here use allow_guest=True because the booking page is publicly
accessible (no login required).
"""

import datetime

import frappe
from frappe import _
from frappe.utils import get_time

from healthcare_appointments.healthcare_appointments.accounting_utils import (
	create_sales_invoice_for_appointment,
)


@frappe.whitelist(allow_guest=True)
def get_services():
	"""Return all Healthcare Services for the public booking dropdown.

	Returns:
		list[dict]: List of service dicts with name, service_name, price, duration_minutes
	"""
	return frappe.get_all(
		"Healthcare Service",
		fields=["name", "service_name", "price", "duration_minutes"],
		order_by="service_name asc",
	)


@frappe.whitelist(allow_guest=True)
def get_end_time(service, appointment_time):
	"""Calculate and return the estimated end time for dynamic display on the booking page.

	Args:
		service (str): Name of the Healthcare Service
		appointment_time (str): Time string in HH:MM or HH:MM:SS format

	Returns:
		str | None: Estimated end time as "HH:MM" string, or None
	"""
	if not service or not appointment_time:
		return None

	duration_minutes = frappe.db.get_value("Healthcare Service", service, "duration_minutes")
	if not duration_minutes:
		return None

	appt_time = get_time(appointment_time)
	combined = datetime.datetime.combine(datetime.date.today(), appt_time)
	end_dt = combined + datetime.timedelta(minutes=int(duration_minutes))
	return end_dt.strftime("%H:%M")


@frappe.whitelist(allow_guest=True)
def book_appointment(patient_name, patient_contact, appointment_date, appointment_time, service):
	"""Create a Patient Appointment and its linked Sales Invoice from the public page.

	Validation (working hours, overlap) is handled by the PatientAppointment
	controller's before_save hook. Any frappe.throw() raised there will surface
	as r.exc in the browser JS callback.

	Args:
		patient_name (str): Full name of the patient
		patient_contact (str): Phone number or email
		appointment_date (str): Date in YYYY-MM-DD format
		appointment_time (str): Time in HH:MM format (from HTML time input)
		service (str): Name of the Healthcare Service document

	Returns:
		dict: {"appointment": <name>, "invoice": <name>}

	Raises:
		frappe.ValidationError: If required fields are missing or validation fails
	"""
	if not all([patient_name, patient_contact, appointment_date, appointment_time, service]):
		frappe.throw(_("All fields are required to book an appointment."))

	if not frappe.db.exists("Healthcare Service", service):
		frappe.throw(_("Selected service does not exist."))

	if len(str(appointment_time).strip()) == 5:
		appointment_time = appointment_time + ":00"

	appointment = frappe.new_doc("Clinic Appointment")
	appointment.patient_name = patient_name.strip()
	appointment.patient_contact = patient_contact.strip()
	appointment.appointment_date = appointment_date
	appointment.appointment_time = appointment_time
	appointment.service = service
	appointment.status = "Scheduled"
	appointment.insert(ignore_permissions=True)

	invoice_name = create_sales_invoice_for_appointment(appointment.name)

	frappe.db.commit()

	return {
		"appointment": appointment.name,
		"invoice": invoice_name,
	}
