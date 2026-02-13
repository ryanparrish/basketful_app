from decimal import Decimal
from apps.pantry.models import Category, Product
from apps.voucher.models import Voucher, VoucherSetting
from apps.account.models import User, Participant, AccountBalance
from apps.lifeskills.models import Program
from apps.orders.models import Order, OrderItem
import factory


class ProgramFactory(factory.django.DjangoModelFactory):
    """Factory for creating Program instances."""
    class Meta:
        model = Program

    name = factory.Sequence(lambda n: f'Program {n}')
    meeting_time = '10:00:00'
    MeetingDay = 'monday'
    meeting_address = factory.Sequence(
        lambda n: f'{n} Test Street'
    )


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'password123')


class AccountBalanceFactory(factory.django.DjangoModelFactory):
    """Factory for creating AccountBalance instances."""
    class Meta:
        model = AccountBalance

    participant = factory.SubFactory(
        'apps.orders.tests.factories.ParticipantFactory'
    )
    base_balance = Decimal("100.00")


class ParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Participant
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f'Participant {n}')
    email = factory.LazyAttribute(
        lambda obj: f"{obj.name.lower().replace(' ', '.')}@example.com"
    )
    user = factory.SubFactory(UserFactory)
    program = factory.SubFactory(ProgramFactory)
    
    @factory.post_generation
    def create_account_balance(obj, create, extracted, **kwargs):
        if create:
            # Calculate expected balance from VoucherSetting based on actual household size
            from apps.account.utils.balance_utils import calculate_base_balance
            calculated_balance = calculate_base_balance(obj)
            
            # Use get_or_create to avoid conflicts with signal
            account, created = AccountBalance.objects.get_or_create(
                participant=obj,
                defaults={'base_balance': calculated_balance}
            )
            if not created:
                account.base_balance = calculated_balance
                account.save()
            
            # CRITICAL: Refresh from database to clear caches
            obj.refresh_from_db()
    
    @factory.post_generation
    def high_balance(obj, create, extracted, **kwargs):
        """
        Optional hook to create high-multiplier vouchers for sufficient test balance.
        Use ParticipantFactory(high_balance=True) to enable.
        """
        if not create or not extracted:
            return
        
        # Get the account
        account = AccountBalance.objects.get(participant=obj)
        
        # Ensure vouchers have sufficient balance for testing, but only when explicitly requested.
        # Only create vouchers if participant has no user (signals won't create them).
        # With base_balance=20 and multiplier=50, 2 vouchers = 2 * (20*50) = 2000 available.
        if not obj.user:
            existing_vouchers = list(account.vouchers.filter(state="applied", voucher_type="grocery"))
            
            # Only create high-multiplier vouchers if none exist
            # (avoid interfering with explicit test voucher setup)
            if not existing_vouchers:
                for i in range(2):
                    Voucher.objects.create(
                        account=account,
                        voucher_type="grocery",
                        state="applied",
                        active=True,
                        multiplier=50
                    )


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f'Category {n}')


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f'Product {n}')
    price = Decimal("10.00")
    category = factory.SubFactory(CategoryFactory)
    quantity_in_stock = 100
    active = True


class VoucherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Voucher
        skip_postgeneration_save = True

    account = factory.SubFactory(AccountBalanceFactory)
    voucher_type = 'grocery'
    state = 'applied'
    active = True
    multiplier = 1


class VoucherSettingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VoucherSetting

    adult_amount = Decimal("50.00")
    child_amount = Decimal("25.00")
    infant_modifier = Decimal("0.50")
    active = True


class OrderFactory(factory.django.DjangoModelFactory):
    """Factory for creating Order instances."""
    class Meta:
        model = Order

    account = factory.SubFactory(AccountBalanceFactory)
    status = 'pending'
    order_number = factory.Sequence(lambda n: f'ORD-{n:08d}')


class OrderItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating OrderItem instances."""
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 1
    price_at_order = factory.LazyAttribute(
        lambda obj: obj.product.price
    )
