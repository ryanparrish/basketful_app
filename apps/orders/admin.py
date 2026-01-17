# apps/orders/admin.py
"""Admin configuration for Order model."""
# Third-party imports
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.utils import timezone
# First-party imports
from apps.voucher.models import Voucher
# Local imports
from .models import Order, CombinedOrder
from .inline import OrderItemInline
from .forms import CreateCombinedOrderForm
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
        return f"${obj.total_price():.2f}"
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

        if not order.paid and order.total_price() > 0:
            used = order.use_voucher()

        if used:
            order.paid = True
            order.save(update_fields=["paid"])


@admin.register(CombinedOrder)
class CombinedOrderAdmin(admin.ModelAdmin):
    """Admin for CombinedOrder with custom actions."""
    actions = ['download_combined_order_pdf']
    readonly_fields = ('display_orders', 'created_at', 'updated_at')
    exclude = ('summarized_data', 'is_parent')
    change_list_template = "admin/orders/combinedorder/change_list.html"
    change_form_template = "admin/orders/combinedorder/change_form.html"
    list_display = (
        'name', 'program', 'created_at', 'updated_at', 'order_count'
    )
    
    def display_orders(self, obj):
        """Display orders in a readable format with links."""
        from django.urls import reverse
        from django.utils.html import format_html_join
        from django.utils.safestring import mark_safe
        
        orders = obj.orders.all()
        if not orders:
            return "No orders"
        
        # Build list of tuples for format_html_join
        order_data = []
        for order in orders:
            url = reverse('admin:orders_order_change', args=[order.id])
            participant_name = order.account.participant.user.get_full_name()
            order_text = f"Order #{order.order_number} - {participant_name}"
            order_data.append((url, order_text))
        
        # Use format_html_join to safely join HTML
        return format_html_join(
            mark_safe('<br>'),  # noqa: S308
            '<a href="{}">{}</a>',
            order_data
        )
    
    display_orders.short_description = 'Orders'
    
    def order_count(self, obj):
        """Display count of orders in the combined order."""
        return obj.orders.count()
    
    order_count.short_description = 'Order Count'

    # ------------------------
    # Custom URLs
    # ------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "create-combined-order/",
                self.admin_site.admin_view(self.create_combined_order_view),
                name="orders_combinedorder_create",
            ),
        ]

        return custom_urls + urls
    
    def create_combined_order_view(self, request):
        """
        Handle the creation of a combined order with custom time frame.
        """
        if request.method == 'POST':
            form = CreateCombinedOrderForm(request.POST)
            if form.is_valid():
                program = form.cleaned_data['program']
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                
                # Convert dates to datetime for filtering
                start_datetime = timezone.make_aware(
                    timezone.datetime.combine(
                        start_date, timezone.datetime.min.time()
                    )
                )
                end_datetime = timezone.make_aware(
                    timezone.datetime.combine(
                        end_date, timezone.datetime.max.time()
                    )
                )
                
                # Get orders for the selected program and time frame
                orders = Order.objects.filter(
                    account__participant__program=program,
                    order_date__gte=start_datetime,
                    order_date__lte=end_datetime,
                    status='confirmed'
                ).select_related('account__participant')
                
                if not orders.exists():
                    messages.warning(
                        request,
                        f"No confirmed orders found for {program.name} "
                        f"between {start_date} and {end_date}."
                    )
                    return render(
                        request,
                        'admin/orders/create_combined_order.html',
                        {'form': form}
                    )
                
                # Use get_or_create to avoid duplicate constraint violation
                # The unique constraint is on program, week, year
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                order_name = f"Combined Order - {timestamp}"
                
                # Get or create based on program and current week/year
                now = timezone.now()
                week = now.isocalendar()[1]
                year = now.year
                
                combined_order, created = CombinedOrder.objects.get_or_create(
                    program=program,
                    week=week,
                    year=year,
                    defaults={'name': order_name}
                )
                
                if not created:
                    # Update the name with new timestamp if reusing existing
                    combined_order.name = order_name
                    combined_order.save(update_fields=['name'])
                
                # Add orders to the combined order
                combined_order.orders.add(*orders)
                combined_order.save()
                
                messages.success(
                    request,
                    f"Combined order created successfully with "
                    f"{orders.count()} orders for {program.name}."
                )
                return redirect('admin:orders_combinedorder_changelist')
        else:
            form = CreateCombinedOrderForm()
        
        return render(
            request,
            'admin/orders/create_combined_order.html',
            {'form': form}
        )

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
