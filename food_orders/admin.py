# admin.py
from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import (
    Product, Order, OrderItem, OrderPacker, Program, Participant,
    LifeSkillsCoach, CombinedOrder, Voucher, AccountBalance,
    VoucherSetting, ProgramPause,Category, Subcategory, ProductManager, UserProfile
)
import json
from .forms import OrderItemInlineForm, OrderItemInlineFormSet,CustomUserCreationForm,ParticipantAdminForm
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from .models import CombinedOrder
from django.contrib.auth.models import User
from .validators import validate_order_items
from .utils import set_random_password_for_user,generate_username_if_missing
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from food_orders.tasks import send_new_user_onboarding_email
from django.urls import path
from django.shortcuts import render
from .models import Order, Product, Voucher
from .inlines import OrderItemInline
import json
from django.urls import path
from .models import Order, Voucher
from . import utils
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
            # Add form
            return self.add_fieldsets

        # Edit form
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
            generate_username_if_missing(obj)
            set_random_password_for_user(obj)
        super().save_model(request, obj, form, change)
        if is_new:
            UserProfile.objects.get_or_create(user=obj)
            send_new_user_onboarding_email.delay(user_id=obj.id)

class SubcategoryInline(admin.StackedInline):
    model = Subcategory
    extra = 1
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [SubcategoryInline]

# --- Inline Admin ---

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    form = OrderItemInlineForm
    formset = OrderItemInlineFormSet
    extra = 1
    fields = ('product', 'quantity', 'price')
    readonly_fields = ('price',)

    class Media:
        js = ('food_orders/js/orderitem_inline.js',)
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        products = Product.objects.all().values('id', 'price')
        product_json = json.dumps({str(p['id']): float(p['price']) for p in products})
        formset.product_json = product_json  # no mark_safe
        return formset
    def clean(self):
        super().clean()
        participant = getattr(self.instance.account, 'participant', None)
        account_balance = self.instance.account
        validate_order_items(self.forms, participant, account_balance)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at', 'total_price', 'paid')
    readonly_fields = ('paid',)
    inlines = [OrderItemInline]
    change_form_template = "admin/food_orders/order/change_form.html"

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
        order = utils.get_order_or_404(order_id)
        context = utils.get_order_print_context(order)
        return render(request, "admin/food_orders/order/print_order.html", context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        product_json = utils.get_product_prices_json()
        script_tag = f'<script>window.productPrices = {product_json};</script>'
        context['additional_inline_script'] = script_tag
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        order = form.instance
        used = False

        if order.status_type == "Confirmed" and not Voucher.objects.filter(account=order.account, active=True).exists():
            raise ValidationError("Cannot confirm order: no active vouchers available.")

        if not order.paid and order.total_price() > 0:
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
    list_display = ('name', 'voucher_balance_display', 'hygiene_balance_display')
    readonly_fields = ('voucher_balance_display', 'hygiene_balance_display')

    def get_balance_display(self, obj, attr):
        try:
            balance = getattr(obj.accountbalance, attr)
            if balance and balance != 0:
                return f"${balance:.2f}"
            return "No Balance"
        except AccountBalance.DoesNotExist:
            return "No Balance"

    def voucher_balance_display(self, obj):
        return self.get_balance_display(obj, 'voucher_balance')
    voucher_balance_display.short_description = "Voucher Balance"

    def hygiene_balance_display(self, obj):
        return self.get_balance_display(obj, 'hygiene_balance')
    hygiene_balance_display.short_description = "Hygiene Balance"

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        create_user = form.cleaned_data.get("create_user", False)

        if is_new and create_user:
            # Only create a User if one doesn't exist
            if not obj.user:
                username = generate_username_if_missing(obj)
                password = set_random_password_for_user(obj)

                user = User.objects.create_user(username=username, password=password, email=obj.email)
                obj.user = user

        super().save_model(request, obj, form, change)


        if is_new and obj.user:
             # Send onboarding email via Celery
            send_new_user_onboarding_email.delay(user_id=obj.user.id)

        # Ensure UserProfile exists
        UserProfile.objects.get_or_create(user=obj.user)

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ('pk', 'voucher_type', 'created_at', 'account', 'voucher_amnt', 'active')
    readonly_fields = ('voucher_amnt', 'notes')  # or just 'amount' if you're using that as the field name

@admin.register(CombinedOrder)
class CombinedOrderAdmin(admin.ModelAdmin):
    actions = ['download_combined_order_pdf']
    readonly_fields = ('orders',)

    def download_combined_order_pdf(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one combined order to download.", level='error')
            return

        combined_order = queryset.first()

        # Create the HttpResponse object with PDF headers.
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="combined_order_{combined_order.id}.pdf"'

        # Create the PDF object, using the response as its "file."
        p = canvas.Canvas(response, pagesize=letter)
        width, height = letter

        # Start drawing
        y = height - 50
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, y, f"Combined Order #{combined_order.id}")
        y -= 20

        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Packed By: {combined_order.packed_by}")
        y -= 20
        p.drawString(50, y, f"Created At: {combined_order.created_at.strftime('%Y-%m-%d %H:%M')}")
        y -= 30

        summary = combined_order.summarized_items_by_category()

        for category, products in summary.items():
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y, f"{category}")
            y -= 20

            p.setFont("Helvetica", 12)
            for product, qty in products.items():
                p.drawString(70, y, f"{product}: {qty}")
                y -= 15

                if y < 100:
                    p.showPage()
                    y = height - 50

            y -= 10

        p.showPage()
        p.save()
        return response

    download_combined_order_pdf.short_description = "Download selected Combined Order as PDF"

admin.site.register(ProgramPause)
admin.site.register(VoucherSetting)
admin.site.register(OrderPacker)
admin.site.register(Program)
admin.site.register(LifeSkillsCoach)
admin.site.register(ProductManager)
