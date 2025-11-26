# admin.py
"""Admin configuration for Order model."""
# Third-party imports
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponse
# First-party imports
from voucher.models import Voucher
# Local imports
from .models import Order, CombinedOrder
from .inline import OrderItemInline
from .utils.order_helper import OrderHelper
from .utils.order_services import generate_combined_order_pdf


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin for Order model."""
    list_display = ('order_number', 'updated_at', 'display_total_price', 'paid')
    readonly_fields = ('paid',)
    inlines = [OrderItemInline]
    change_form_template = "admin/food_orders/order/change_form.html"
    exclude = ('user',)

    def display_total_price(self, obj):
        """Display the total price of the order."""
        return obj.total_price
    display_total_price.short_description = "Total Price"

    class Media:
        """Media class to include custom JS."""
        js = ('food_orders/js/orderitem_inline.js',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:order_id>/print/',
                self.admin_site.admin_view(self.print_order),
                name='order-print',
            ),
        ]
        return custom_urls + urls

    def print_order(self, request, order_id):
        """Render a printable view of the order."""
        helper = OrderHelper()
        order = helper.get_order_or_404(order_id)
        context = helper.get_order_print_context(order)
        return render(request, "admin/food_orders/order/print_order.html", context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        product_json = OrderHelper.get_product_prices_json()
        script_tag = f'<script>window.productPrices = {product_json};</script>'
        context['additional_inline_script'] = script_tag
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        order = form.instance
        used = False

        if (
            order.status_type == "Confirmed"
            and not Voucher.active_vouchers.filter(
                account=order.account, active=True
            ).exists()
        ):
            raise ValidationError(
                "Cannot confirm order: no active vouchers available."
            )

        if not order.paid and order.total_price > 0:
            used = order.use_voucher()

        if used:
            order.paid = True
            order.save(update_fields=["paid"])


@admin.register(CombinedOrder)
class CombinedOrderAdmin(admin.ModelAdmin):
    """Admin for CombinedOrder with custom actions."""
    actions = ['download_combined_order_pdf']
    readonly_fields = ('orders',)
    change_list_template = "admin/program_changelist.html"
    list_display = ('program', 'created_at', 'updated_at')

    # ------------------------
    # Custom URLs
    # ------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "run-weekly-task/",
                self.admin_site.admin_view(self.create_weekly_task_view),
                name="food_orders_combinedorder_run_weekly_task",
            ),
        ]

        return custom_urls + urls
    
    def create_weekly_task_view(self, request):
        """Handle the creation of a weekly task."""
        # Add your logic for creating a weekly task here
        self.message_user(request, "Weekly task created successfully.")
        return HttpResponse("Weekly task created successfully.")


    
    @admin.action(description="Download Combined Order PDF")
    def download_combined_order_pdf(self, request, queryset):
        """Generate and download a PDF for the selected combined order."""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one combined order to download.",
                level='error'
            )
            return
        combined_order = queryset.first()

        # Call your utils function (returns BytesIO)
        pdf_buffer = generate_combined_order_pdf(combined_order)

        # Wrap in HttpResponse for download
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="combined_order_{combined_order.id}.pdf"'
        )
        return response

# Register your models here.
