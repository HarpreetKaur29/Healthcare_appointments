# Copyright (c) 2026, Harpreet and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

# Use a far-future date so tests never conflict with real clinic bookings
TEST_DATE = "2099-01-15"


def make_service(
	service_name="_Test Service",
	price=500.0,
	duration_minutes=30,
	description="Test healthcare service",
):
	if frappe.db.exists("Healthcare Service", service_name):
		return frappe.get_doc("Healthcare Service", service_name)

	svc = frappe.new_doc("Healthcare Service")
	svc.service_name = service_name
	svc.price = price
	svc.duration_minutes = duration_minutes
	svc.description = description
	svc.insert(ignore_permissions=True)
	return svc


def make_appointment(
	patient_name="_Test Patient",
	patient_contact="9000000001",
	appointment_date=None,
	appointment_time="10:00:00",
	service=None,
	do_not_save=False,
):
	if service is None:
		make_service()
		service = "_Test Service"

	appt = frappe.new_doc("Clinic Appointment")
	appt.patient_name = patient_name
	appt.patient_contact = patient_contact
	appt.appointment_date = appointment_date or TEST_DATE
	appt.appointment_time = appointment_time
	appt.service = service

	if not do_not_save:
		appt.insert(ignore_permissions=True)

	return appt


def _cleanup_test_services():
	for name in frappe.get_all("Healthcare Service", filters=[["service_name", "like", "_Test%"]], pluck="name"):
		frappe.delete_doc("Healthcare Service", name, ignore_permissions=True, force=True)


def _cleanup_test_appointments(contact_prefix):
	for name in frappe.get_all(
		"Clinic Appointment",
		filters=[["patient_contact", "like", contact_prefix + "%"]],
		pluck="name",
	):
		frappe.delete_doc("Clinic Appointment", name, ignore_permissions=True, force=True)


class TestCalculations(FrappeTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_cleanup_test_appointments("9001")
		_cleanup_test_services()
		frappe.db.commit()

	def test_estimated_end_time_30_min(self):
		make_service("_Test Calc 30min", price=300, duration_minutes=30)
		appt = make_appointment(
			patient_contact="9001000001",
			appointment_time="10:00:00",
			service="_Test Calc 30min",
		)
		self.assertEqual(str(appt.estimated_end_time)[:5], "10:30")

	def test_estimated_end_time_60_min(self):
		make_service("_Test Calc 60min", price=600, duration_minutes=60)
		appt = make_appointment(
			patient_contact="9001000002",
			appointment_time="09:00:00",
			service="_Test Calc 60min",
		)
		self.assertEqual(str(appt.estimated_end_time)[:5], "10:00")

	def test_total_amount_matches_service_price(self):
		make_service("_Test Amount Svc", price=750.0, duration_minutes=45)
		appt = make_appointment(
			patient_contact="9001000003",
			appointment_time="11:00:00",
			service="_Test Amount Svc",
		)
		self.assertEqual(appt.total_amount, 750.0)

	def test_different_prices_reflected_on_resave(self):
		make_service("_Test Price A", price=200.0, duration_minutes=15)
		make_service("_Test Price B", price=800.0, duration_minutes=45)

		appt = make_appointment(
			patient_contact="9001000004",
			appointment_time="14:00:00",
			service="_Test Price A",
		)
		self.assertEqual(appt.total_amount, 200.0)

		appt.service = "_Test Price B"
		appt.save()
		self.assertEqual(appt.total_amount, 800.0)


class TestOverlapValidation(FrappeTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_cleanup_test_appointments("9002")
		frappe.db.commit()

	def test_non_overlapping_different_times(self):
		make_service()
		make_appointment(patient_contact="9002000001", appointment_time="13:00:00")
		appt2 = make_appointment(patient_contact="9002000001", appointment_time="14:00:00")
		self.assertIsNotNone(appt2.name)

	def test_non_overlapping_different_patients(self):
		# two different patients, non-overlapping slots — both should go through
		make_service()
		make_appointment(patient_contact="9002000002", appointment_time="09:00:00")
		appt2 = make_appointment(patient_contact="9002000003", appointment_time="11:00:00")
		self.assertIsNotNone(appt2.name)

	def test_overlapping_same_time_raises(self):
		make_service()
		make_appointment(patient_contact="9002000004", appointment_time="12:00:00")

		with self.assertRaises(frappe.ValidationError):
			make_appointment(patient_contact="9002000004", appointment_time="12:00:00")

	def test_cancelled_appointment_does_not_block_rebooking(self):
		make_service()
		existing = make_appointment(patient_contact="9002000005", appointment_time="15:00:00")

		existing.status = "Cancelled"
		existing.save()

		appt2 = make_appointment(patient_contact="9002000005", appointment_time="15:00:00")
		self.assertIsNotNone(appt2.name)


class TestWorkingHoursValidation(FrappeTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_cleanup_test_appointments("9003")
		frappe.db.commit()

	def test_within_working_hours_succeeds(self):
		appt = make_appointment(patient_contact="9003000001", appointment_time="14:00:00")
		self.assertIsNotNone(appt.name)

	def test_at_opening_time_succeeds(self):
		appt = make_appointment(patient_contact="9003000002", appointment_time="09:00:00")
		self.assertIsNotNone(appt.name)

	def test_before_opening_raises(self):
		with self.assertRaises(frappe.ValidationError):
			make_appointment(patient_contact="9003000003", appointment_time="08:59:00")

	def test_at_closing_time_raises(self):
		with self.assertRaises(frappe.ValidationError):
			make_appointment(patient_contact="9003000004", appointment_time="17:00:00")

	def test_after_closing_raises(self):
		with self.assertRaises(frappe.ValidationError):
			make_appointment(patient_contact="9003000005", appointment_time="18:00:00")

	def test_midnight_raises(self):
		with self.assertRaises(frappe.ValidationError):
			make_appointment(patient_contact="9003000006", appointment_time="00:00:00")


class TestWhitelistedMethods(FrappeTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_cleanup_test_services()
		frappe.db.commit()

	def test_get_estimated_end_time(self):
		from healthcare_appointments.healthcare_appointments.doctype.clinic_appointment.clinic_appointment import (
			get_estimated_end_time,
		)

		make_service("_Test WL 45min", price=450, duration_minutes=45)
		result = get_estimated_end_time("_Test WL 45min", "10:00:00")
		self.assertEqual(result[:5], "10:45")

	def test_get_service_price(self):
		from healthcare_appointments.healthcare_appointments.doctype.clinic_appointment.clinic_appointment import (
			get_service_price,
		)

		make_service("_Test WL Price", price=1200.0, duration_minutes=30)
		price = get_service_price("_Test WL Price")
		self.assertEqual(price, 1200.0)

	def test_get_estimated_end_time_empty_inputs(self):
		from healthcare_appointments.healthcare_appointments.doctype.clinic_appointment.clinic_appointment import (
			get_estimated_end_time,
		)

		self.assertIsNone(get_estimated_end_time("", ""))
		self.assertIsNone(get_estimated_end_time(None, None))

	def test_get_service_price_empty_input(self):
		from healthcare_appointments.healthcare_appointments.doctype.clinic_appointment.clinic_appointment import (
			get_service_price,
		)

		self.assertIsNone(get_service_price(""))
		self.assertIsNone(get_service_price(None))


class TestPublicBooking(FrappeTestCase):
	# book_appointment() calls frappe.db.commit() internally, so tearDownClass cleans up persisted records

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_cleanup_test_appointments("9004")
		_cleanup_test_services()
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		_cleanup_test_appointments("9004")
		_cleanup_test_services()
		frappe.db.commit()
		super().tearDownClass()

	def test_successful_booking_creates_appointment(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service("_Test Booking A", price=500, duration_minutes=30)
		frappe.db.commit()

		result = book_appointment(
			patient_name="Alice Sharma",
			patient_contact="9004000001",
			appointment_date=TEST_DATE,
			appointment_time="11:00",
			service="_Test Booking A",
		)

		self.assertIn("appointment", result)
		self.assertTrue(frappe.db.exists("Clinic Appointment", result["appointment"]))

	def test_successful_booking_creates_submitted_sales_invoice(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service("_Test Invoice B", price=750, duration_minutes=60)
		frappe.db.commit()

		result = book_appointment(
			patient_name="Bob Mehta",
			patient_contact="9004000002",
			appointment_date=TEST_DATE,
			appointment_time="12:00",
			service="_Test Invoice B",
		)

		self.assertIn("invoice", result)
		invoice = frappe.get_doc("Sales Invoice", result["invoice"])
		self.assertEqual(invoice.docstatus, 1, "Invoice must be submitted")
		self.assertEqual(invoice.status, "Paid", "Invoice must be Paid")
		self.assertEqual(invoice.grand_total, 750.0)

	def test_sales_invoice_linked_to_appointment(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service("_Test Link C", price=300, duration_minutes=30)
		frappe.db.commit()

		result = book_appointment(
			patient_name="Carol Patel",
			patient_contact="9004000003",
			appointment_date=TEST_DATE,
			appointment_time="10:00",
			service="_Test Link C",
		)

		appt = frappe.get_doc("Clinic Appointment", result["appointment"])
		self.assertEqual(appt.sales_invoice, result["invoice"])

	def test_booking_outside_hours_raises_error(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service("_Test OOH Svc", price=200, duration_minutes=30)
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			book_appointment(
				patient_name="Dave Kumar",
				patient_contact="9004000004",
				appointment_date=TEST_DATE,
				appointment_time="08:00",
				service="_Test OOH Svc",
			)

	def test_booking_overlap_raises_error(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service("_Test Overlap Svc", price=400, duration_minutes=30)
		frappe.db.commit()

		book_appointment(
			patient_name="Eve Singh",
			patient_contact="9004000005",
			appointment_date=TEST_DATE,
			appointment_time="14:00",
			service="_Test Overlap Svc",
		)

		with self.assertRaises(frappe.ValidationError):
			book_appointment(
				patient_name="Eve Singh",
				patient_contact="9004000005",
				appointment_date=TEST_DATE,
				appointment_time="14:00",
				service="_Test Overlap Svc",
			)

	def test_booking_with_missing_fields_raises_error(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service()
		frappe.db.commit()

		with self.assertRaises(frappe.ValidationError):
			book_appointment(
				patient_name="",
				patient_contact="9004000006",
				appointment_date=TEST_DATE,
				appointment_time="10:00",
				service="_Test Service",
			)

	def test_booking_time_normalization(self):
		from healthcare_appointments.healthcare_appointments.web_methods import book_appointment

		make_service("_Test Norm Svc", price=100, duration_minutes=15)
		frappe.db.commit()

		result = book_appointment(
			patient_name="Frank Nair",
			patient_contact="9004000007",
			appointment_date=TEST_DATE,
			appointment_time="09:00",
			service="_Test Norm Svc",
		)

		appt = frappe.get_doc("Clinic Appointment", result["appointment"])
		t_str = str(appt.appointment_time).zfill(8)[:5]
		self.assertEqual(t_str, "09:00")
