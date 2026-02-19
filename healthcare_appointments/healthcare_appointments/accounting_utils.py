import frappe
from frappe import _
from frappe.utils import nowdate


WALK_IN_CUSTOMER_NAME = "Walk-in Customer"


def get_or_create_walk_in_customer():
	if frappe.db.exists("Customer", WALK_IN_CUSTOMER_NAME):
		return WALK_IN_CUSTOMER_NAME

	customer = frappe.new_doc("Customer")
	customer.customer_name = WALK_IN_CUSTOMER_NAME
	customer.customer_type = "Individual"
	customer.customer_group = (
		frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"
	)
	customer.territory = (
		frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
	)
	customer.insert(ignore_permissions=True)
	frappe.db.commit()
	return WALK_IN_CUSTOMER_NAME


def ensure_service_item(service_name):
	# Sales Invoices need an ERPNext Item — create one per service if missing
	if frappe.db.exists("Item", service_name):
		return service_name

	item = frappe.new_doc("Item")
	item.item_code = service_name
	item.item_name = service_name
	item.item_group = "Services"
	item.is_stock_item = 0
	item.include_item_in_manufacturing = 0
	item.stock_uom = "Nos"
	item.insert(ignore_permissions=True)
	frappe.db.commit()
	return service_name


def create_sales_invoice_for_appointment(appointment_name):
	appointment = frappe.get_doc("Clinic Appointment", appointment_name)

	if not appointment.total_amount:
		frappe.throw(_("Cannot create invoice: total amount is not set on {0}.").format(appointment_name))

	customer = get_or_create_walk_in_customer()
	item_code = ensure_service_item(appointment.service)

	si = frappe.new_doc("Sales Invoice")
	si.customer = customer
	si.posting_date = nowdate()
	si.due_date = nowdate()
	si.is_pos = 1  # POS mode + matching cash payment = auto Paid on submit

	si.append("items", {
		"item_code": item_code,
		"item_name": appointment.service,
		"description": f"Appointment: {appointment_name} | Patient: {appointment.patient_name}",
		"qty": 1,
		"rate": appointment.total_amount,
		"uom": "Nos",
	})

	si.append("payments", {
		"mode_of_payment": "Cash",
		"amount": appointment.total_amount,
	})

	si.insert(ignore_permissions=True)
	si.submit()

	frappe.db.set_value("Clinic Appointment", appointment_name, "sales_invoice", si.name)
	return si.name
