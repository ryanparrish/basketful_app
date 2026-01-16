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

    name = factory.Sequence(lambda n: f'Participant {n}')
    email = factory.LazyAttribute(
        lambda obj: f"{obj.name.lower().replace(' ', '.')}@example.com"
    )
    user = factory.SubFactory(UserFactory)
    program = factory.SubFactory(ProgramFactory)
    
    @factory.post_generation
    def create_account_balance(obj, create, extracted, **kwargs):
        if create:
            # Use get_or_create to avoid conflicts with signal
            AccountBalance.objects.get_or_create(
                participant=obj,
                defaults={'base_balance': Decimal("100.00")}
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
