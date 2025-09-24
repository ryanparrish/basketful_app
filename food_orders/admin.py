# admin.py
from django.contrib import admin,messages
from django.utils.safestring import mark_safe
from .models import (
    Product, Order, OrderPacker, Program, Participant,
    LifeSkillsCoach, CombinedOrder, Voucher,
    VoucherSetting, ProgramPause,Category, Subcategory, ProductManager, EmailLog,UserProfile, OrderValidationLog
)
from .forms import CustomUserCreationForm,ParticipantAdminForm
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from .models import CombinedOrder,AccountBalance
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.urls import path
from django.shortcuts import render
from .inlines import OrderItemInline
from . import utils
from django.http import HttpResponseRedirect
from .tasks import create_weekly_combined_orders
from .user_utils import _generate_admin_username
from .inlines import VoucherLogInline
from .models import Participant
from .balance_utils import calculate_base_balance  
from decimal import Decimal
from food_orders import order_utils  
User = get_user_model()
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass  # If not registered yet, ignore 

@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    add_form = CustomUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'is_staff'),
        }),
    )

    # Default fieldsets for editing users
    base_fieldsets = (
        (None, {
            'fields': ('email', 'first_name', 'last_name', 'is_staff', 'is_active'),
        }),
    )

    staff_extra_fieldsets = (
        ('Permissions', {
            'fields': ('groups', 'user_permissions', 'is_superuser'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """
        Show additional fields if the user is staff.
        """
        if obj is None:
            return self.add_fieldsets

        fieldsets = list(self.base_fieldsets)
        if obj.is_staff:
            fieldsets += list(self.staff_extra_fieldsets)
        return fieldsets

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.add_form
        return super().get_form(request, obj, **kwargs)
    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None

        if is_new:
            # Generate a username based on first+last name
            base_name = f"{obj.first_name}_{obj.last_name}".strip() or "user"
            for candidate in _generate_admin_username(base_name):
                if not User.objects.filter(username=candidate).exists():
                    obj.username = candidate
                    break

        super().save_model(request, obj, form, change)

        if is_new:
            # Ensure profile exists and set must_change_password
            profile, _ = UserProfile.objects.get_or_create(user=obj)
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])

class SubcategoryInline(admin.StackedInline):
    model = Subcategory
    extra = 1
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [SubcategoryInline]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at', 'total_price', 'paid')
    readonly_fields = ('paid',)
    inlines = [OrderItemInline]
    change_form_template = "admin/food_orders/order/change_form.html"
    exclude = ('user',)

    class Media:
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
        order = order_utils.get_order_or_404(order_id)
        context = order_utils.get_order_print_context(order)
        return render(request, "admin/food_orders/order/print_order.html", context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        product_json = order_utils.get_product_prices_json()
        script_tag = f'<script>window.productPrices = {product_json};</script>'
        context['additional_inline_script'] = script_tag
        return super().render_change_form(request, context, add, change, form_url, obj)


    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        order = form.instance
        used = False

        if order.status_type == "Confirmed" and not Voucher.objects.filter(account=order.account, active=True).exists():
            raise ValidationError("Cannot confirm order: no active vouchers available.")

        if not order.paid and order.total_price > 0:
            used = order.used_voucher()

        if used:
            order.paid = True
            order.save(update_fields=["paid"])

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    readonly_fields = ['image_preview']
    search_fields = ['name', 'description', 'category__name']

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" style="max-height: 200px;" />')
        return "(No image uploaded)"

    image_preview.short_description = "Current Image"

    class Media:
        js = ('food_orders/js/admin_image_preview.js',)
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    form = ParticipantAdminForm
    list_display = (
        'name',
        'full_balance_display',
        'available_balance_display',
        'hygiene_balance_display',
        'get_base_balance',
    )
    readonly_fields = (
        'full_balance_display',
        'available_balance_display',
        'hygiene_balance_display',
        'get_base_balance',
    )
    actions = ['calculate_base_balance_action']

    def full_balance_display(self, obj):
        balance = obj.balances().get('full_balance', 0)
        return f"${balance:.2f}" if balance else "No Balance"
    full_balance_display.short_description = "Full Balance"

    def available_balance_display(self, obj):
        balance = obj.balances().get('available_balance', 0)
        return f"${balance:.2f}" if balance else "No Balance"
    available_balance_display.short_description = "Available Balance"

    def hygiene_balance_display(self, obj):
        balance = obj.balances().get('hygiene_balance', 0)
        return f"${balance:.2f}" if balance else "No Balance"
    hygiene_balance_display.short_description = "Hygiene Balance"

    def get_base_balance(self, obj):
        if hasattr(obj, 'accountbalance'):
            return f"${obj.accountbalance.base_balance:,.2f}"
        return Decimal(0)
    get_base_balance.short_description = "Base Balance"

    def calculate_base_balance_action(self, request, queryset):
        updated_count = 0
        for participant in queryset:
            base = calculate_base_balance(participant)
            # Ensure AccountBalance exists
            account_balance, created = AccountBalance.objects.get_or_create(participant=participant)
            account_balance.base_balance = base
            account_balance.save()
            updated_count += 1
        self.message_user(request, f"Base balance calculated and saved for {updated_count} participants.")
    calculate_base_balance_action.short_description = "Calculate and save base balance for selected participants"

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    # Fields to show in the list view
    list_display = ('pk', 'voucher_type', 'created_at', 'account', 'voucher_amnt', 'active')
    
    # Make some fields read-only
    readonly_fields = ('voucher_amnt', 'notes')
    
    # Fields to hide from the admin form entirely
    exclude = ('program_pause_flag','multiplier')
    
    # Add filters in the right sidebar
    list_filter = ('voucher_type', 'account', 'active', 'created_at')
    
    # Add search functionality
    search_fields = ('voucher_type__name', 'account__name', 'notes')  # adjust according to your field names
    
    inlines = [VoucherLogInline]

@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('id', 'user', 'status', 'sent_at','email_type')

    # Fields that are read-only in the change form
    readonly_fields = ('user', 'email_type', 'status', 'sent_at')

    # Make searchable by these fields
    search_fields = ('user','email_type','sent_at')

    # Add filters in the right-hand sidebar
    list_filter = ('status', 'user','email_type')

    # Disable add and delete
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(CombinedOrder)
class CombinedOrderAdmin(admin.ModelAdmin):
    actions = ['download_combined_order_pdf']
    readonly_fields = ('orders',)
    change_list_template = "admin/program_changelist.html"
    list_display = ('program', 'created_at', 'updated_at')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "run-weekly-task/",
                self.admin_site.admin_view(self.run_weekly_task),
                name="food_orders_combinedorder_run_weekly_task",
            ),
        ]
        return custom_urls + urls
    
    def run_weekly_task(self, request):
        create_weekly_combined_orders.delay()  # run asynchronously
        self.message_user(request, "Weekly combined orders task has been triggered!")
        return HttpResponseRedirect("../")
    
    def download_combined_order_pdf(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one combined order to download.", level='error')
            return
        combined_order = queryset.first()
        pdf_buffer = utils.generate_combined_order_pdf(combined_order)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="combined_order_{combined_order.id}.pdf"'
        return response

@admin.register(ProgramPause)
class ProgramPauseAdmin(admin.ModelAdmin):
    list_display = ("reason", "pause_start", "pause_end", "is_active_gate")

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)

        all_pauses = ProgramPause.objects.all()
        active_pauses = [p for p in all_pauses if p.is_active_gate]
        if active_pauses:
            self.message_user(
                request,
                f"{active_pauses[0].reason} — This Pause Is Active",
                level=messages.INFO
            )

        return response

admin.site.register(VoucherSetting)
admin.site.register(OrderPacker)
admin.site.register(Program)
admin.site.register(LifeSkillsCoach)
admin.site.register(ProductManager)
admin.site.register(OrderValidationLog)

