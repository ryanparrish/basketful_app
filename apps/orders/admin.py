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
import io
import zipfile
# First-party imports
from apps.voucher.models import Voucher
# Local imports
from .models import Order, CombinedOrder, PackingSplitRule, PackingList
from .inline import OrderItemInline
from .forms import CreateCombinedOrderForm
from .utils.order_helper import OrderHelper
from .utils.order_services import generate_combined_order_pdf
from .tasks.helper.combined_order_helper import (
    get_eligible_orders,
    get_split_preview,
    validate_split_strategy,
    create_combined_order_with_packing,
    uncombine_order,
)


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
    """Admin for CombinedOrder with preview/confirm workflow."""
    actions = ['download_primary_order_pdf', 'download_packing_list_pdf', 'download_all_packing_lists_zip', 'uncombine_orders_action']
    readonly_fields = ('orders', 'split_strategy', 'display_orders', 'created_at', 'updated_at', 'display_packing_lists', 'display_split_strategy')
    exclude = ('summarized_data', 'is_parent')
    change_list_template = "admin/orders/combinedorder/change_list.html"
    change_form_template = "admin/orders/combinedorder/change_form.html"
    list_display = (
        'name', 'program', 'display_split_strategy', 'created_at', 'updated_at', 'order_count', 'packing_list_count'
    )
    list_filter = ('program', 'split_strategy', 'created_at')
    
    def display_split_strategy(self, obj):
        """Display split strategy with human-readable label."""
        return obj.get_split_strategy_display()
    display_split_strategy.short_description = 'Split Strategy'
    
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
            # Use customer_number for privacy
            participant = order.account.participant
            customer_num = getattr(participant, 'customer_number', 'N/A')
            order_text = f"Order #{order.order_number} - Customer #{customer_num}"
            order_data.append((url, order_text))
        
        # Use format_html_join to safely join HTML
        return format_html_join(
            mark_safe('<br>'),  # noqa: S308
            '<a href="{}">{}</a>',
            order_data
        )
    
    display_orders.short_description = 'Orders'
    
    def display_packing_lists(self, obj):
        """Display packing lists for this combined order."""
        from django.utils.html import format_html
        
        packing_lists = obj.packing_lists.all()
        if not packing_lists:
            return "No packing lists (single packer or not split)"
        
        lines = []
        for pl in packing_lists:
            lines.append(f"• {pl.packer.name}: {pl.orders.count()} orders")
        
        return format_html('<br>'.join(lines))
    
    display_packing_lists.short_description = 'Packing Lists'
    
    def order_count(self, obj):
        """Display count of orders in the combined order."""
        return obj.orders.count()
    
    order_count.short_description = 'Orders'
    
    def packing_list_count(self, obj):
        """Display count of packing lists."""
        return obj.packing_lists.count()
    
    packing_list_count.short_description = 'Packing Lists'

    # ------------------------
    # Custom URLs
    # ------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "create/",
                self.admin_site.admin_view(self.create_combined_order_view),
                name="orders_combinedorder_create",
            ),
            path(
                "preview/",
                self.admin_site.admin_view(self.preview_combined_order_view),
                name="orders_combinedorder_preview",
            ),
            path(
                "confirm/",
                self.admin_site.admin_view(self.confirm_combined_order_view),
                name="orders_combinedorder_confirm",
            ),
            path(
                "<int:pk>/success/",
                self.admin_site.admin_view(self.success_combined_order_view),
                name="orders_combinedorder_success",
            ),
        ]

        return custom_urls + urls
    
    def create_combined_order_view(self, request):
        """
        Step 1: Show form to select program and date range.
        """
        if request.method == 'POST':
            form = CreateCombinedOrderForm(request.POST)
            if form.is_valid():
                # Store form data in session for preview
                request.session['combined_order_form_data'] = {
                    'program_id': form.cleaned_data['program'].id,
                    'start_date': form.cleaned_data['start_date'].isoformat(),
                    'end_date': form.cleaned_data['end_date'].isoformat(),
                    'split_strategy_override': form.cleaned_data.get('split_strategy_override', ''),
                }
                return redirect('admin:orders_combinedorder_preview')
        else:
            form = CreateCombinedOrderForm()
        
        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Create Combined Order',
            'opts': self.model._meta,
        }
        return render(request, 'admin/orders/create_combined_order.html', context)
    
    def preview_combined_order_view(self, request):
        """
        Step 2: Show preview with validation, totals, and split preview.
        """
        from apps.lifeskills.models import Program
        from datetime import date
        
        # Get form data from session
        form_data = request.session.get('combined_order_form_data')
        if not form_data:
            messages.error(request, "No form data found. Please start over.")
            return redirect('admin:orders_combinedorder_create')
        
        try:
            program = Program.objects.get(id=form_data['program_id'])
            start_date = date.fromisoformat(form_data['start_date'])
            end_date = date.fromisoformat(form_data['end_date'])
            strategy_override = form_data.get('split_strategy_override', '')
        except (Program.DoesNotExist, ValueError) as e:
            messages.error(request, f"Invalid form data: {e}")
            return redirect('admin:orders_combinedorder_create')
        
        # Determine effective strategy
        if strategy_override:
            effective_strategy = strategy_override
        else:
            effective_strategy = program.default_split_strategy
        
        # Get eligible orders
        eligible_orders, excluded_orders, warnings = get_eligible_orders(
            program, start_date, end_date
        )
        
        # Check for critical errors
        errors = []
        if not eligible_orders:
            errors.append(
                f"No eligible orders found for {program.name} "
                f"between {start_date} and {end_date}."
            )
        
        # Validate split strategy
        strategy_valid, strategy_errors = validate_split_strategy(program, effective_strategy)
        if not strategy_valid:
            errors.extend(strategy_errors)
        
        # Get split preview if we have orders
        preview_data = {}
        if eligible_orders and strategy_valid:
            preview_data = get_split_preview(eligible_orders, program, effective_strategy)
        
        # Store order IDs in session for confirmation
        request.session['combined_order_preview'] = {
            'order_ids': [o.id for o in eligible_orders],
            'program_id': program.id,
            'strategy': effective_strategy,
            'start_date': form_data['start_date'],
            'end_date': form_data['end_date'],
        }
        request.session.modified = True  # Ensure session is saved
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Preview Combined Order',
            'opts': self.model._meta,
            'program': program,
            'start_date': start_date,
            'end_date': end_date,
            'effective_strategy': effective_strategy,
            'strategy_display': dict(CombinedOrder.SPLIT_STRATEGY_CHOICES).get(effective_strategy, effective_strategy),
            'eligible_orders': eligible_orders,
            'excluded_orders': excluded_orders,
            'warnings': warnings,
            'errors': errors,
            'preview_data': preview_data,
            'can_proceed': len(errors) == 0 and len(eligible_orders) > 0,
        }
        
        return render(request, 'admin/orders/preview_combined_order.html', context)
    
    def confirm_combined_order_view(self, request):
        """
        Step 3: Confirm and create the combined order.
        """
        from apps.lifeskills.models import Program
        
        if request.method != 'POST':
            return redirect('admin:orders_combinedorder_create')
        
        # Get preview data from session
        preview_data = request.session.get('combined_order_preview')
        if not preview_data:
            messages.error(request, "No preview data found. Please start over.")
            return redirect('admin:orders_combinedorder_create')
        
        try:
            program = Program.objects.get(id=preview_data['program_id'])
            order_ids = preview_data['order_ids']
            strategy = preview_data['strategy']
            
            # Get orders
            orders = list(Order.objects.filter(id__in=order_ids))
            
            if not orders:
                messages.error(request, "No orders found to combine.")
                return redirect('admin:orders_combinedorder_create')
            
            # Create the combined order
            combined_order, packing_lists = create_combined_order_with_packing(
                program=program,
                orders=orders,
                strategy=strategy,
            )
            
            # Clear session data
            request.session.pop('combined_order_form_data', None)
            request.session.pop('combined_order_preview', None)
            
            messages.success(
                request,
                f"Combined order created successfully with {len(orders)} orders."
            )
            
            return redirect('admin:orders_combinedorder_success', pk=combined_order.pk)
            
        except ValidationError as e:
            messages.error(request, f"Validation error: {e}")
            return redirect('admin:orders_combinedorder_preview')
        except Exception as e:
            messages.error(request, f"Error creating combined order: {e}")
            return redirect('admin:orders_combinedorder_create')
    
    def success_combined_order_view(self, request, pk):
        """
        Step 4: Show success page with download links.
        """
        try:
            combined_order = CombinedOrder.objects.get(pk=pk)
        except CombinedOrder.DoesNotExist:
            messages.error(request, "Combined order not found.")
            return redirect('admin:orders_combinedorder_changelist')
        
        packing_lists = list(combined_order.packing_lists.select_related('packer'))
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Combined Order Created',
            'opts': self.model._meta,
            'combined_order': combined_order,
            'packing_lists': packing_lists,
            'order_count': combined_order.orders.count(),
            'total_items': sum(
                sum(products.values())
                for products in combined_order.summarized_data.values()
            ) if combined_order.summarized_data else 0,
        }
        
        return render(request, 'admin/orders/success_combined_order.html', context)

    # ------------------------
    # Admin Actions
    # ------------------------

    @admin.action(description="Download Primary Order PDF")
    def download_primary_order_pdf(self, request, queryset):
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
        pdf_buffer.seek(0)

        # Wrap in HttpResponse for download
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="primary_order_{combined_order.id}.pdf"'
        )
        return response

    @admin.action(description="Download First Packing List PDF")
    def download_packing_list_pdf(self, request, queryset):
        """Generate and download first packing list PDF for the selected combined order."""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one combined order to download.",
                level='error'
            )
            return
        
        combined_order = queryset.first()
        packing_lists = combined_order.packing_lists.all()
        
        if packing_lists.exists():
            # Download first packing list
            from .utils.order_services import generate_packing_list_pdf
            packing_list = packing_lists.first()
            pdf_buffer = generate_packing_list_pdf(packing_list)
            pdf_buffer.seek(0)
            filename = f"packing_list_{combined_order.id}_{packing_list.packer.name.replace(' ', '_')}.pdf"
        else:
            # Single packer - use combined order as packing list
            pdf_buffer = generate_combined_order_pdf(combined_order)
            pdf_buffer.seek(0)
            filename = f"packing_list_{combined_order.id}.pdf"

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @admin.action(description="Download All Packing Lists (ZIP)")
    def download_all_packing_lists_zip(self, request, queryset):
        """Download all packing lists and primary order as a ZIP file."""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one combined order to download.",
                level='error'
            )
            return
        
        combined_order = queryset.first()
        packing_lists = combined_order.packing_lists.all()
        
        # If no packing lists, just download single PDF
        if not packing_lists.exists():
            return self.download_packing_list_pdf(request, queryset)
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add primary order PDF
            primary_pdf = generate_combined_order_pdf(combined_order)
            primary_pdf.seek(0)
            zip_file.writestr(
                f"primary_order_{combined_order.id}.pdf",
                primary_pdf.read()
            )
            
            # Add each packing list PDF
            from .utils.order_services import generate_packing_list_pdf
            for packing_list in packing_lists:
                pdf_buffer = generate_packing_list_pdf(packing_list)
                pdf_buffer.seek(0)
                filename = f"packing_list_{packing_list.packer.name.replace(' ', '_')}_{combined_order.id}.pdf"
                zip_file.writestr(filename, pdf_buffer.read())
        
        # Return ZIP as download
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="combined_order_{combined_order.id}_all_lists.zip"'
        return response

    @admin.action(description="Uncombine and Delete Selected Orders")
    def uncombine_orders_action(self, request, queryset):
        """Uncombine selected combined orders and delete them."""
        total_uncombined = 0
        combined_count = queryset.count()
        for combined_order in queryset:
            count = uncombine_order(combined_order)
            total_uncombined += count
            # Delete the combined order after uncombining
            combined_order.delete()
        
        self.message_user(
            request,
            f"Uncombined and deleted {combined_count} combined order(s), releasing {total_uncombined} order(s)."
        )


@admin.register(PackingSplitRule)
class PackingSplitRuleAdmin(admin.ModelAdmin):
    """Admin for configuring category-to-packer mappings."""
    list_display = ('program', 'packer', 'category_list', 'created_at')
    list_filter = ('program', 'packer')
    filter_horizontal = ('categories', 'subcategories')
    search_fields = ('program__name', 'packer__name')
    
    fieldsets = (
        (None, {
            'fields': ('program', 'packer')
        }),
        ('Category Assignments', {
            'fields': ('categories', 'subcategories'),
            'description': 'Select which categories/subcategories this packer is responsible for.'
        }),
    )
    
    def category_list(self, obj):
        """Display assigned categories."""
        categories = list(obj.categories.values_list('name', flat=True)[:5])
        if obj.categories.count() > 5:
            categories.append('...')
        return ', '.join(categories) if categories else 'None'
    category_list.short_description = 'Categories'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter packers to only show those assigned to programs."""
        if db_field.name == 'packer':
            from apps.pantry.models import OrderPacker
            kwargs['queryset'] = OrderPacker.objects.filter(programs__isnull=False).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PackingList)
class PackingListAdmin(admin.ModelAdmin):
    """Admin for viewing packing lists (read-only)."""
    list_display = ('combined_order', 'packer', 'order_count', 'created_at')
    list_filter = ('packer', 'combined_order__program', 'created_at')
    readonly_fields = ('combined_order', 'packer', 'display_orders', 'display_categories', 'summarized_data', 'created_at', 'updated_at')
    actions = ['download_packing_list_pdf_action']
    change_form_template = "admin/orders/packinglist/change_form.html"
    
    def order_count(self, obj):
        """Display count of orders."""
        return obj.orders.count()
    order_count.short_description = 'Orders'
    
    def display_orders(self, obj):
        """Display orders in this packing list."""
        from django.utils.html import format_html
        
        orders = obj.orders.all()[:10]
        lines = []
        for order in orders:
            customer_num = getattr(order.account.participant, 'customer_number', 'N/A')
            lines.append(f"#{order.order_number} - Customer #{customer_num}")
        
        if obj.orders.count() > 10:
            lines.append(f"... and {obj.orders.count() - 10} more")
        
        return format_html('<br>'.join(lines))
    display_orders.short_description = 'Orders'
    
    def display_categories(self, obj):
        """Display categories assigned to this packer."""
        categories = list(obj.categories.values_list('name', flat=True))
        return ', '.join(categories) if categories else 'All categories'
    display_categories.short_description = 'Categories'
    
    def get_urls(self):
        """Add custom URLs for print view."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:packing_list_id>/print/',
                self.admin_site.admin_view(self.print_packing_list),
                name='packinglist-print',
            ),
        ]
        return custom_urls + urls
    
    def print_packing_list(self, request, packing_list_id):
        """Render a printable view of the packing list."""
        from django.shortcuts import get_object_or_404
        
        packing_list = get_object_or_404(PackingList, pk=packing_list_id)
        
        # Get orders with related data
        orders = packing_list.orders.select_related(
            'account__participant'
        ).prefetch_related('items__product__category')
        
        context = {
            'packing_list': packing_list,
            'combined_order': packing_list.combined_order,
            'packer': packing_list.packer,
            'orders': orders,
            'now': timezone.now(),
            'program': packing_list.combined_order.program,
        }
        
        return render(request, "admin/orders/packinglist/print_packing_list.html", context)
    
    @admin.action(description="Download Packing List PDF")
    def download_packing_list_pdf_action(self, request, queryset):
        """Generate and download PDF for selected packing lists."""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one packing list to download.",
                level='error'
            )
            return
        
        packing_list = queryset.first()
        
        from .utils.order_services import generate_packing_list_pdf
        pdf_buffer = generate_packing_list_pdf(packing_list)
        pdf_buffer.seek(0)
        
        filename = f"packing_list_{packing_list.packer.name.replace(' ', '_')}_{packing_list.combined_order.id}.pdf"
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    def has_add_permission(self, request):
        """Packing lists are created automatically."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Packing lists are read-only."""
        return False
