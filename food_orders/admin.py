# admin.py

from django.contrib import admin
from django import VERSION as DJANGO_VERSION , forms
from django.forms.models import BaseInlineFormSet
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
from .utils import generate_memorable_password, generate_unique_username, set_random_password_for_user,generate_username_if_missing
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin

User = get_user_model()
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass  # If not registered yet, ignore
from django import forms
from django.contrib.auth import get_user_model
 
@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    add_form = CustomUserCreationForm  # custom user creation form without password fields

    # Override add_fieldsets to exclude password fields since you handle passwords differently
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:  # when adding a new user, use custom add_form
            kwargs['form'] = self.add_form
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None

        if is_new:
            # Generate username if missing
            generate_username_if_missing(obj)

            # Set random password and flag user
            set_random_password_for_user(obj)

        super().save_model(request, obj, form, change)

        if is_new:
            # Send password reset email
            reset_form = PasswordResetForm({'email': obj.email})
            if reset_form.is_valid():
                reset_form.save(
                    request=request,
                    use_https=request.is_secure(),
                    email_template_name='registration/new_user_onboarding.html',
                )

            # Ensure UserProfile exists
            UserProfile.objects.get_or_create(user=obj)

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

# --- Admin for Order ---

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at', 'total_price','paid')
    readonly_fields=('paid',)
    inlines = [OrderItemInline]
    class Media:
        js = ('food_orders/js/orderitem_inline.js',)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        products = Product.objects.all().values('id', 'price')
        product_json = json.dumps({str(p['id']): float(p['price']) for p in products})
        script_tag = f'<script>window.productPrices = {product_json};</script>'
        context['additional_inline_script'] = script_tag  # this is safe
        return super().render_change_form(request, context, add, change, form_url, obj)

    def save_model(self, request, obj, form, change):
        # Save the Order instance normally
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        # Save inlines first
        super().save_related(request, form, formsets, change)

        # Then apply voucher logic
        order = form.instance
        used = False

        if order.status_type == "Confirmed":
            if not Voucher.objects.filter(account=order.account, active=True).exists():
                raise ValidationError("Cannot confirm order: no active vouchers available.")
        
        if not order.paid and order.total_price() > 0:
            used = order.used_voucher()

        if used:
            order.paid = True
            order.save(update_fields=["paid"])

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    readonly_fields = ['image_preview']

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

        super().save_model(request, obj, form, change)

        if is_new:
            obj.setup_account_and_vouchers()

            # Optional: email password reset if user exists
            if obj.user and obj.user.email:
                reset_form = PasswordResetForm({'email': obj.user.email})
                if reset_form.is_valid():
                    reset_form.save(
                        request=request,
                        use_https=request.is_secure(),
                        email_template_name='registration/new_user_onboarding.html'
                    )

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
