

frappe.ui.form.on("Clinic Appointment", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status === "Scheduled") {
			frm.add_custom_button(__("Mark as Completed"), () => {
				frappe.confirm(
					__("Mark this appointment as Completed?"),
					() => {
						frm.set_value("status", "Completed");
						frm.save();
					}
				);
			}, __("Actions"));

			frm.add_custom_button(__("Cancel Appointment"), () => {
				frappe.confirm(
					__("Are you sure you want to cancel this appointment?"),
					() => {
						frm.set_value("status", "Cancelled");
						frm.save();
					}
				);
			}, __("Actions"));
		}
	},

	service(frm) {
		frm.trigger("calculate_end_time");
		frm.trigger("fetch_price");
	},

	appointment_time(frm) {
		frm.trigger("calculate_end_time");
	},

	calculate_end_time(frm) {
		if (!frm.doc.service || !frm.doc.appointment_time) return;

		frappe.call({
			method: "healthcare_appointments.healthcare_appointments.doctype"
				+ ".clinic_appointment.clinic_appointment.get_estimated_end_time",
			args: {
				service: frm.doc.service,
				appointment_time: frm.doc.appointment_time,
			},
			callback(r) {
				if (r.message) {
					frm.set_value("estimated_end_time", r.message);
				}
			},
		});
	},

	fetch_price(frm) {
		if (!frm.doc.service) return;

		frappe.call({
			method: "healthcare_appointments.healthcare_appointments.doctype"
				+ ".clinic_appointment.clinic_appointment.get_service_price",
			args: {
				service: frm.doc.service,
			},
			callback(r) {
				if (r.message !== undefined && r.message !== null) {
					frm.set_value("total_amount", r.message);
				}
			},
		});
	},
});
