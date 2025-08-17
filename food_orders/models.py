from django.db import models
from django.utils.timezone import now
from decimal import Decimal
from django.core.validators import MinValueValidator
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from collections import defaultdict
from django.db.models import Sum
from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Subcategory(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')

    def __str__(self):
        return f"{self.category.name} > {self.name}"
# Class to represent a product in inventory
class Product(models.Model):
    is_meat = models.BooleanField(default=False)
    weight_lbs = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # e.g., 1.00 for beef, 2.00 for chicken
    category = models.ForeignKey(Category,on_delete=models.CASCADE, related_name="product",)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    quantity_in_stock = models.IntegerField(
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    active = models.BooleanField(default=True)
    @staticmethod
    def get_limit_for_product(product):
        subcat_limit = (
            ProductManager.objects
            .filter(subcategory=product.subcategory)
            .order_by('limit')
            .first()
        )
        cat_limit = (
            ProductManager.objects
            .filter(category=product.category, subcategory__isnull=True)
            .order_by('limit')
            .first()
        )

        limits = []
        if subcat_limit:
            limits.append(subcat_limit.limit)
        if cat_limit:
            limits.append(cat_limit.limit)

        return min(limits) if limits else None

    def __str__(self):
        return self.name
    
class ProductManager(models.Model):
    name= models.CharField(max_length=100)
    category = models.OneToOneField(
    Category,
    on_delete=models.CASCADE,
    related_name="product_manager", 
    help_text="If category is selected, limit will be enforced at the category level."
    )
    subcategory = models.ForeignKey(Subcategory, on_delete=models.CASCADE, help_text="If Sub-Category is selected limit will be applied at the subcategory level", null=True, blank=True) 
    notes = models.TextField(blank=True, null=True)
    limit = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of products allowed in this category per order."
    )
    limit_scope = models.CharField(
        max_length=20,
        choices=[
            ('per_adult', 'Per Adult'),
            ('per_child', 'Per Child'),
            ('per_infant', 'Per Infant'),
            ('per_household', 'Per Household'),
            ('per_order', 'Per Order'),
        ],
        default='per_household',
        null=True,
        blank=True,
        help_text="Scope of the limit: Adult, Child, Infant or Household."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
#Class to represent a calender of when there is no class 
class ProgramPause(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=45, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f" {self.reason or 'No Reason Provided'}"
    @classmethod
    def date_logic(cls):
        today = now().date()
        pause= cls.objects.first()
        if not pause:
            return 1
        if pause.start_date <= today + timedelta(days=14)<= pause.end_date:
            return 3    
        elif pause.start_date <= today + timedelta(days=7) <= pause.start_date + timedelta(days=5):
            return 2
        return 1 #Default value if no pause is active
    def clean(self):
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError("End date cannot be earlier than start date.")
        if self.end_date and self.start_date:
            delta = self.end_date - self.start_date
            if delta > timedelta(days=14):
                raise ValidationError("Program pause cannot be longer than 14 days.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensures validation is run on save
        super().save(*args, **kwargs)
# Class to represent a Life Skills coach
class LifeSkillsCoach (models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='coaches/', blank=True, null=True)
    def __str__(self):
        return self.name
   # Class to represent a Life Skills program
class Program(models.Model):
    name= models.CharField(max_length=100)
    meeting_time = models.TimeField()
    MeetingDay = models.CharField(
    blank=False,
    choices=[
            ('monday' ,'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
        ]      
    ,max_length=10
    )
    meeting_address= models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.name
# Class to represent a participant in the program
class Participant(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    adults = models.PositiveIntegerField(default=1)
    children = models.PositiveIntegerField(default=0)
    diaper_count= models.PositiveIntegerField(default=0, help_text="Count of Children in Diapers of Pull-Ups")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, null=True, blank=True)
    assigned_coach = models.ForeignKey(LifeSkillsCoach, on_delete=models.CASCADE, related_name='customers', null=True, blank=True)
    create_user = models.BooleanField(default=False, null=True,help_text="If checked this will create a user account.")
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name
    def setup_account_and_vouchers(self):
        from .models import AccountBalance, Voucher
        # Avoid duplicate account creation
        try:
            self.accountbalance
            return
        except AccountBalance.DoesNotExist:
            pass

        account = AccountBalance.objects.create(participant=self)
        Voucher.objects.create(account=account, voucher_type="Grocery")
        Voucher.objects.create(account=account, voucher_type="Grocery")
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new instance
        self.full_clean()  # Ensures validation is run on save
        super().save(*args, **kwargs)
        if is_new:
            self.setup_account_and_vouchers()
    def household_size(self):
        return self.adults + self.children 
# Class to represent account balance
class AccountBalance(models.Model):
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE)
    last_updated = models.DateTimeField(auto_now=True)
#sum of all vouchers for the participant
    @property
    def voucher_balance(self):
        multiplier = ProgramPause.date_logic()
        vouchers = self.vouchers.filter(active=True).order_by('id')[:2]
        return sum(v.voucher_amnt() for v in vouchers) * multiplier
    @property
    def hygiene_balance(self):
        return self.voucher_balance / Decimal(3)
    def __str__(self):
        return f"{self.participant.name} Balance "
# Class to represent an order
class Order(models.Model):
    account = models.ForeignKey(AccountBalance, on_delete=models.PROTECT, related_name='orders')   
    order_date = models.DateTimeField(auto_now_add=True)
    status_type = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('packing', 'Packing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        null=False,
    )
    paid = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Order {self.pk} by {self.account.participant.name}"
    # Method to calculate the total price of the order
    def total_price(self):
        if self.status_type == "cancelled":
            return 0
        items = self.items.all()
        return sum((item.total_price() or 0) for item in items)
    def used_voucher(self):
        print(f"Applying vouchers for order {self.id}")
        vouchers = list(Voucher.objects.filter(account=self.account, active=True).order_by('id')[:2])
        print(f"Found {len(vouchers)} active vouchers for order {self.id}")
        amount_needed = self.total_price()
        print(f"Total price for order {self.id} is ${amount_needed:.2f}, applying vouchers...")

        if not vouchers or amount_needed <= 0:
            print("No active vouchers found or no amount needed.")
            return False

        used_any = False
        for voucher in vouchers:
            value = voucher.voucher_amnt()
            if amount_needed <= 0:
                break

            applied_amount = min(value, amount_needed)
            amount_needed -= applied_amount

            voucher.active = False
            note_type = "Fully" if applied_amount == value else "Partially"
            voucher.notes = (voucher.notes or "") + f"{note_type} used on order {self.id} for ${applied_amount:.2f}; "
            print(f"Marking voucher {voucher.id} as inactive, applied amount: ${applied_amount:.2f}, remaining amount needed: ${amount_needed:.2f}")
            voucher.save()
            used_any = True

        return used_any

    def calculate_hygiene_total(self, item_data_list):
        """
        Accepts a list of dicts with 'product' and 'quantity',
        like form.cleaned_data, to calculate hygiene subtotal.
        """
        total = Decimal(0)
        for data in item_data_list:
            product = data.get("product")
            quantity = data.get("quantity", 0)
            if product and product.is_hygiene:
                total += (product.price or Decimal(0)) * quantity
        return total
  
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        used = False
        if self.status_type == "Confirmed":
            active_vouchers = Voucher.objects.filter(account=self.account, active=True)
            if not active_vouchers.exists():
                raise ValidationError("Cannot confirm order: no active vouchers available.")
        if not self.paid and self.total_price() > 0:
            used = self.used_voucher()
        if used:
            self.paid = True
            super().save(update_fields=["paid"])

class OrderItem(models.Model):
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    # Current product price reference (useful for comparisons/reports)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    # Historical price locked at time of order
    price_at_order = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Only set once (don’t overwrite if it already exists)
        if self.price_at_order is None and self.product_id:
            self.price_at_order = self.product.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} × {self.product.name} (Order #{self.order_id})"
    def total_price(self):
        return self.quantity * self.price
    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Order #{self.order.id})"
    def save(self, *args, **kwargs):
        if self.product:
            self.price = self.product.price
        super().save(*args, **kwargs)

class CombinedOrder(models.Model):
    program = models.OneToOneField('Program', on_delete=models.CASCADE, related_name='combined_order')
    orders = models.ManyToManyField('Order', related_name='combined_orders')
    packed_by = models.ForeignKey('OrderPacker', on_delete=models.CASCADE, related_name='combined_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def summarized_items_by_category(self):
        """
        Summarize items grouped by category and product,
        only for orders in this combined order and in this program.
        Returns:
        dict: {category_name: {product_name: total_quantity}}
        """
        summary = defaultdict(lambda: defaultdict(int))

        orders_qs = self.orders.select_related(
            'account__participant__program'
        ).prefetch_related(
            'items__product__category'
        )

        for order in orders_qs:
            participant = getattr(order.account, 'participant', None)
            if not participant or participant.program != self.program:
                continue  # Skip if participant doesn't match program

        for item in order.items.all():
            product = item.product
            category_name = product.category.name if product.category else "Uncategorized"
            summary[category_name][product.name] += item.quantity

        return summary  
  
    def __str__(self):
        return f"{self.program.name} Combined Order"

# Class to represent who packed the order
class OrderPacker(models.Model):
    name= models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.name

#Class to represent voucher settings
class VoucherSetting(models.Model):
    adult_amount = models.PositiveIntegerField(default=40)
    child_amount = models.PositiveIntegerField(default=25)
    infant_modifier = models.PositiveIntegerField(default=5)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Voucher Setting (Updated: {self.updated_at.strftime('%Y-%m-%d')})"
    def save(self, *args, **kwargs):
        if self.active:
            VoucherSetting.objects.exclude(id=self.id).update(active=False)
        super().save(*args, **kwargs)
    # Ensure only one active setting at a time

    class Meta:
        verbose_name_plural = "Voucher Settings"

#Class to represent voucher payments
class Voucher(models.Model):
    account= models.ForeignKey(AccountBalance, on_delete=models.CASCADE, related_name='vouchers')
    active = models.BooleanField(default=True)
    voucher_type = models.CharField(
        blank=False,
        choices=[
            ('life', 'Life'),
            ('grocery', 'Grocery'),
        ],
        default='grocery',
        max_length=20,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, default=" ")
   
    def __str__(self):
        return f"Voucher ({self.pk})"
    # Calculate the voucher amount based on the number of adults and children
    # If the participant has an infant, add the infant modifier to the total
    @property
    def adult_count(self):
        return self.account.participant.adults
    @property
    def child_count(self):
        return self.account.participant.children
    @property
    def diaper_modifier(self):
        return self.account.participant.diaper_count
    def voucher_amnt(self):
        setting = VoucherSetting.objects.filter(active=True).first()
        # Get the active voucher setting, if it exists
        # If no active setting is found, return 0
        if not setting:
            return 0
        if self.voucher_type == "Life":
            return 0
        elif self.diaper_modifier == True and self.voucher_type == "Grocery":
            return (self.adult_count * setting.adult_amount) + (self.child_count * setting.child_amount) + (setting.infant_modifier*self.diaper_modifier)
        else: 
            return (self.adult_count * setting.adult_amount) + (self.child_count * setting.child_amount)
  