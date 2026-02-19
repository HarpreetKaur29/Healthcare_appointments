import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time


class ClinicAppointment(Document):

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		appointment_date: DF.Date
		appointment_time: DF.Time
		estimated_end_time: DF.Time | None
		patient_contact: DF.Data
		patient_name: DF.Data
		sales_invoice: DF.Link | None
		service: DF.Link
		status: DF.Literal["Scheduled", "Completed", "Cancelled"]
		total_amount: DF.Currency | None

	def before_save(self):
		self.validate_working_hours()
		self.validate_no_overlap()
		self.calculate_end_time_and_amount()

	def on_update(self):
		if self.status == "Completed":
			frappe.logger().info(
				f"[Healthcare Appointments] Appointment {self.name} for patient "
				f"'{self.patient_name}' marked as Completed."
			)

	def validate_working_hours(self):
		if not self.appointment_time:
			return

		appt_time = get_time(self.appointment_time)
		if appt_time < datetime.time(9, 0) or appt_time >= datetime.time(17, 0):
			frappe.throw(
				_("Appointments can only be scheduled between 9:00 AM and 5:00 PM."),
				title=_("Outside Working Hours"),
			)

	def validate_no_overlap(self):
		"""
		Checks time-range overlap, not just exact time match.
		Two appointments overlap when: new_start < existing_end AND new_end > existing_start
		"""
		if not self.appointment_date or not self.appointment_time or not self.service:
			return

		service = frappe.get_cached_doc("Healthcare Service", self.service)
		new_start = datetime.datetime.combine(datetime.date.today(), get_time(self.appointment_time))
		new_end = new_start + datetime.timedelta(minutes=service.duration_minutes)

		filters = {"appointment_date": self.appointment_date, "status": ["!=", "Cancelled"]}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		for appt in frappe.get_all(
			"Clinic Appointment",
			filters=filters,
			fields=["name", "patient_name", "appointment_time", "service"],
		):
			duration = frappe.db.get_value("Healthcare Service", appt.service, "duration_minutes") or 0
			existing_start = datetime.datetime.combine(datetime.date.today(), get_time(appt.appointment_time))
			existing_end = existing_start + datetime.timedelta(minutes=int(duration))

			if new_start < existing_end and new_end > existing_start:
				frappe.throw(
					_("This time slot overlaps with {0}'s appointment ({1} – {2}).").format(
						frappe.bold(appt.patient_name),
						frappe.bold(existing_start.strftime("%H:%M")),
						frappe.bold(existing_end.strftime("%H:%M")),
					),
					title=_("Appointment Overlap Detected"),
				)

	def calculate_end_time_and_amount(self):
		if not self.service or not self.appointment_time:
			return

		service = frappe.get_cached_doc("Healthcare Service", self.service)
		combined = datetime.datetime.combine(datetime.date.today(), get_time(self.appointment_time))
		self.estimated_end_time = (combined + datetime.timedelta(minutes=service.duration_minutes)).strftime("%H:%M:%S")
		self.total_amount = service.price


@frappe.whitelist()
def get_estimated_end_time(service, appointment_time):
	if not service or not appointment_time:
		return None

	duration_minutes = frappe.db.get_value("Healthcare Service", service, "duration_minutes")
	if not duration_minutes:
		return None

	combined = datetime.datetime.combine(datetime.date.today(), get_time(appointment_time))
	return (combined + datetime.timedelta(minutes=int(duration_minutes))).strftime("%H:%M:%S")


@frappe.whitelist()
def get_service_price(service):
	if not service:
		return None
	return frappe.db.get_value("Healthcare Service", service, "price")
