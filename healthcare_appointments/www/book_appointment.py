# Copyright (c) 2026, Harpreet and contributors
# For license information, please see license.txt

import frappe

no_cache = 1


def get_context(context):
	context.title = "Book an Appointment"
	context.services = frappe.get_all(
		"Healthcare Service",
		fields=["name", "service_name", "price", "duration_minutes", "description"],
		order_by="service_name asc",
	)
	return context
