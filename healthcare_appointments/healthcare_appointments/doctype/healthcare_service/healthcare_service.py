# Copyright (c) 2026, Harpreet and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HealthcareService(Document):
	

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		duration_minutes: DF.Int
		price: DF.Currency
		service_name: DF.Data

	
	pass
