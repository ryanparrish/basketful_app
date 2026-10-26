"""
The balance rules every order path applies: the participant's live cart
check (validate-cart), order creation (OrderValidation) and Order.clean().
Keeping them in one place is what lets a participant trust the cart: if it
says they can check out, submitting the order agrees.

- Food balance (available_balance) is the voucher total. It pays for the
  whole cart: food, hygiene and Go Fresh items alike, which is what
  Order._consume_vouchers() charges at confirmation.
- Hygiene balance caps how much of that hygiene items may use.
- Go Fresh budget caps how much of it Go Fresh items may use. It only
  applies while Go Fresh is enabled (budget above zero).

All three follow the program's grace setting the same way. Going over by
no more than the grace amount, while grace is enabled, is a warning: the
participant sees the grace message and the order goes through. Any other
overage, or any overage at all with grace off, is an error that blocks
the order.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Tuple

from django.utils.translation import gettext as _

from apps.pantry.models import Product


@dataclass(frozen=True)
class BalanceViolation:
    """One balance a cart goes over, and whether that blocks the order."""
    balance: str         # Product.BUDGET_FOOD, BUDGET_HYGIENE or BUDGET_GO_FRESH
    total: Decimal       # what the cart spends against this balance
    limit: Decimal       # what the balance allows
    grace_allowed: bool
    message: str
    product_ids: Tuple[int, ...]  # the cart lines to flag for the participant

    @property
    def amount_over(self) -> Decimal:
        return self.total - self.limit

    @property
    def severity(self) -> str:
        return "warning" if self.grace_allowed else "error"

    @property
    def is_blocking(self) -> bool:
        return not self.grace_allowed

    def as_cart_violation(self) -> dict:
        """The shape validate-cart returns to the participant frontend."""
        return {
            "type": "balance",
            "severity": self.severity,
            "message": self.message,
            "amount_over": str(self.amount_over),
            "grace_allowed": self.grace_allowed,
            "budget": self.balance,
            "product_ids": list(self.product_ids),
        }


def line_total(line) -> Decimal:
    """Price × quantity for an OrderItem (its stored price) or OrderItemData."""
    price = getattr(line, "price", None)
    if price is None:
        price = line.product.price
    return price * line.quantity


def budget_total(lines, budget) -> Decimal:
    """What the lines paid from one budget (Product.budget) cost."""
    return sum((line_total(line) for line in lines if line.product.budget == budget), Decimal("0"))


def check_cart_balances(lines: Iterable, account, program_settings) -> List[BalanceViolation]:
    """
    Every balance the cart goes over, with grace already applied.

    `lines` are OrderItems or OrderItemData (anything with .product and
    .quantity). `program_settings` is the ProgramSettings singleton.
    """
    lines = list(lines)

    def product_ids(budget=None):
        return tuple(sorted({
            line.product.id for line in lines
            if budget is None or line.product.budget == budget
        }))

    violations = []

    cart_total = sum((line_total(line) for line in lines), Decimal("0"))
    available_balance = account.available_balance
    if cart_total > available_balance:
        # Every line spends the food balance, but food lines are the ones to
        # point at; flag them all only when the cart has no food lines
        violations.append(_balance_violation(
            Product.BUDGET_FOOD, cart_total, available_balance, program_settings,
            _("Food balance exceeded by $%(amount)s"),
            product_ids(Product.BUDGET_FOOD) or product_ids(),
        ))

    hygiene_total = budget_total(lines, Product.BUDGET_HYGIENE)
    hygiene_balance = account.hygiene_balance
    if hygiene_total > hygiene_balance:
        violations.append(_balance_violation(
            Product.BUDGET_HYGIENE, hygiene_total, hygiene_balance, program_settings,
            _("Hygiene balance exceeded by $%(amount)s"),
            product_ids(Product.BUDGET_HYGIENE),
        ))

    go_fresh_total = budget_total(lines, Product.BUDGET_GO_FRESH)
    go_fresh_balance = account.go_fresh_balance
    if go_fresh_balance > 0 and go_fresh_total > go_fresh_balance:
        violations.append(_balance_violation(
            Product.BUDGET_GO_FRESH, go_fresh_total, go_fresh_balance, program_settings,
            _("Go Fresh balance exceeded by $%(amount)s"),
            product_ids(Product.BUDGET_GO_FRESH),
        ))

    return violations


def _balance_violation(balance, total, limit, program_settings, over_message, product_ids) -> BalanceViolation:
    amount_over = total - limit
    grace_allowed = (
        program_settings.grace_enabled
        and amount_over <= program_settings.grace_amount
    )
    return BalanceViolation(
        balance=balance,
        total=total,
        limit=limit,
        grace_allowed=grace_allowed,
        message=(
            program_settings.grace_message if grace_allowed
            else over_message % {"amount": f"{amount_over:.2f}"}
        ),
        product_ids=product_ids,
    )
