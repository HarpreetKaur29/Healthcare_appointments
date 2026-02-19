import datetime

import frappe
from frappe import _
from frappe.utils import get_time

from healthcare_appointments.healthcare_appointments.accounting_utils import (
	create_sales_invoice_for_appointment,
)


@frappe.whitelist(allow_guest=True)
def get_services():
	return frappe.get_all(
		"Healthcare Service",
		fields=["name", "service_name", "price", "duration_minutes"],
		order_by="service_name asc",
	)


@frappe.whitelist(allow_guest=True)
def get_end_time(service, appointment_time):
	if not service or not appointment_time:
		return None

	duration_minutes = frappe.db.get_value("Healthcare Service", service, "duration_minutes")
	if not duration_minutes:
		return None

	combined = datetime.datetime.combine(datetime.date.today(), get_time(appointment_time))
	return (combined + datetime.timedelta(minutes=int(duration_minutes))).strftime("%H:%M")


@frappe.whitelist(allow_guest=True)
def book_appointment(patient_name, patient_contact, appointment_date, appointment_time, service):
	if not all([patient_name, patient_contact, appointment_date, appointment_time, service]):
		frappe.throw(_("All fields are required to book an appointment."))

	if not frappe.db.exists("Healthcare Service", service):
		frappe.throw(_("Selected service does not exist."))

	# HTML time input gives HH:MM — Frappe Time field needs HH:MM:SS
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
