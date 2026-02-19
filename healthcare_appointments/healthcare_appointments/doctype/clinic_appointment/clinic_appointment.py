

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
				f"'{self.patient_name}' (contact: {self.patient_contact}) "
				f"has been marked as Completed."
			)

	def validate_working_hours(self):
		"""Reject appointments that start outside 09:00–17:00."""
		if not self.appointment_time:
			return

		appt_time = get_time(self.appointment_time)
		clinic_open = datetime.time(9, 0, 0)
		clinic_close = datetime.time(17, 0, 0)

		if appt_time < clinic_open or appt_time >= clinic_close:
			frappe.throw(
				_("Appointments can only be scheduled between 9:00 AM and 5:00 PM. "
				  "Please choose a time within clinic working hours."),
				title=_("Outside Working Hours"),
			)

	def validate_no_overlap(self):
		"""Prevent time-range overlaps with any existing appointment on the same date.

		Two appointments overlap when:  new_start < existing_end  AND  new_end > existing_start
		This catches cases like Jerry 10:30–10:45 vs Jan 10:35–10:50.
		"""
		if not self.appointment_date or not self.appointment_time or not self.service:
			return

		service = frappe.get_cached_doc("Healthcare Service", self.service)
		new_start = datetime.datetime.combine(
			datetime.date.today(), get_time(self.appointment_time)
		)
		new_end = new_start + datetime.timedelta(minutes=service.duration_minutes)

		filters = {
			"appointment_date": self.appointment_date,
			"status": ["!=", "Cancelled"],
		}
		if not self.is_new():
			filters["name"] = ["!=", self.name]

		existing = frappe.get_all(
			"Clinic Appointment",
			filters=filters,
			fields=["name", "patient_name", "appointment_time", "service"],
		)

		for appt in existing:
			existing_duration = (
				frappe.db.get_value("Healthcare Service", appt.service, "duration_minutes") or 0
			)
			existing_start = datetime.datetime.combine(
				datetime.date.today(), get_time(appt.appointment_time)
			)
			existing_end = existing_start + datetime.timedelta(minutes=int(existing_duration))

			if new_start < existing_end and new_end > existing_start:
				frappe.throw(
					_("This time slot overlaps with {0}'s appointment ({1} – {2}). "
					  "Please choose a different time.").format(
						frappe.bold(appt.patient_name),
						frappe.bold(existing_start.strftime("%H:%M")),
						frappe.bold(existing_end.strftime("%H:%M")),
					),
					title=_("Appointment Overlap Detected"),
				)

	def calculate_end_time_and_amount(self):
		"""Compute estimated_end_time and total_amount from the linked Healthcare Service."""
		if not self.service or not self.appointment_time:
			return

		service = frappe.get_cached_doc("Healthcare Service", self.service)

	
		appt_time = get_time(self.appointment_time)
		combined = datetime.datetime.combine(datetime.date.today(), appt_time)
		end_dt = combined + datetime.timedelta(minutes=service.duration_minutes)
		self.estimated_end_time = end_dt.strftime("%H:%M:%S")

		
		self.total_amount = service.price




@frappe.whitelist()
def get_estimated_end_time(service, appointment_time):
	"""Calculate and return the estimated end time.
	"""
	if not service or not appointment_time:
		return None

	duration_minutes = frappe.db.get_value("Healthcare Service", service, "duration_minutes")
	if not duration_minutes:
		return None

	appt_time = get_time(appointment_time)
	combined = datetime.datetime.combine(datetime.date.today(), appt_time)
	end_dt = combined + datetime.timedelta(minutes=int(duration_minutes))
	return end_dt.strftime("%H:%M:%S")


@frappe.whitelist()
def get_service_price(service):
	"""Return the price of a Healthcare Service.
	"""
	if not service:
		return None
	return frappe.db.get_value("Healthcare Service", service, "price")
