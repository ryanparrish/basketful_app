"""Integration tests for search + cart functionality."""
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.account.models import Participant
from apps.lifeskills.models import LifeskillsCoach
from apps.pantry.models import Product, Category
from apps.voucher.models import Voucher
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


class SearchCartIntegrationTest(TestCase):
    """Test that cart items persist when using search functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        # Create coach
        self.coach = LifeskillsCoach.objects.create(
            name='Test Coach',
            email='coach@test.com',
            phone_number='555-1234'
        )
        
        # Create participant
        user = User.objects.create_user(
            username='testuser',
            password='test_password_123',
            email='test@test.com'
        )
        self.participant = Participant.objects.create(
            user=user,
            name='Test User',
            email='test@test.com',
            assigned_coach=self.coach
        )
        
        # Create categories
        self.fruit_category = Category.objects.create(
            name='Fruits'
        )
        self.veggie_category = Category.objects.create(
            name='Vegetables'
        )
        self.dairy_category = Category.objects.create(
            name='Dairy'
        )
        
        # Create products
        self.apple = Product.objects.create(
            name='Apple',
            description='Fresh apple',
            price=2.50,
            category=self.fruit_category,
            quantity_in_stock=100
        )
        self.banana = Product.objects.create(
            name='Banana',
            description='Fresh banana',
            price=3.00,
            category=self.fruit_category,
            quantity_in_stock=100
        )
        self.carrot = Product.objects.create(
            name='Carrot',
            description='Fresh carrot',
            price=1.00,
            category=self.veggie_category,
            quantity_in_stock=100
        )
        self.milk = Product.objects.create(
            name='Milk',
            description='Fresh milk',
            price=4.50,
            category=self.dairy_category,
            quantity_in_stock=100
        )
        
        # Create active voucher
        self.voucher = Voucher.objects.create(
            account=self.participant.accountbalance,
            voucher_type='grocery',
            active=True,
            state='applied'
        )
        
        # Login
        self.client.login(username='testuser', password='test_password_123')

    def test_template_has_all_products_json(self):
        """Test that template receives all_products_json variable."""
        response = self.client.get('/pantry/products/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('all_products_json', response.context)
        self.assertIn('products_json', response.context)
        
    def test_all_products_json_contains_all_products(self):
        """Test that all_products_json contains all active products."""
        response = self.client.get('/pantry/products/')
        
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        # Should have all 4 products
        self.assertEqual(len(all_products), 4)
        self.assertIn(str(self.apple.id), all_products)
        self.assertIn(str(self.banana.id), all_products)
        self.assertIn(str(self.carrot.id), all_products)
        self.assertIn(str(self.milk.id), all_products)
        
    def test_search_filters_products_json_but_not_all_products_json(self):
        """Test that search filters products_json but all_products_json stays complete."""
        # Search for "apple"
        response = self.client.get('/pantry/products/?q=apple')
        
        self.assertEqual(response.status_code, 200)
        
        # products_json should be filtered (only Apple)
        products_json = response.context['products_json']
        products = json.loads(products_json)
        
        # Should only have Apple
        self.assertIn(str(self.apple.id), products)
        # Note: Trigram search might include similar items, so we check Apple is there
        
        # all_products_json should have ALL products
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        # Should have all 4 products regardless of search
        self.assertEqual(len(all_products), 4)
        self.assertIn(str(self.apple.id), all_products)
        self.assertIn(str(self.banana.id), all_products)
        self.assertIn(str(self.carrot.id), all_products)
        self.assertIn(str(self.milk.id), all_products)
        
    def test_template_renders_allProducts_variable(self):
        """Test that template contains allProducts JavaScript variable."""
        response = self.client.get('/pantry/products/')
        
        content = response.content.decode('utf-8')
        
        # Check that both variables are in the template
        self.assertIn('const products = JSON.parse', content)
        self.assertIn('const allProducts = JSON.parse', content)
        
    def test_template_renderCart_uses_allProducts(self):
        """Test that renderCart function uses allProducts."""
        response = self.client.get('/pantry/products/')
        
        content = response.content.decode('utf-8')
        
        # Check that renderCart uses allProducts
        self.assertIn('allProducts[productId]', content)
        
    def test_cart_persistence_with_search(self):
        """Test that cart items persist when searching."""
        # Add items to cart
        session = self.client.session
        session['cart'] = {
            str(self.apple.id): 2,
            str(self.banana.id): 3,
            str(self.carrot.id): 5
        }
        session.save()
        
        # Now search for "apple" (should filter products)
        response = self.client.get('/pantry/products/?q=apple')
        
        # Get the rendered HTML
        content = response.content.decode('utf-8')
        
        # all_products_json should still have all products
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        # Verify all cart items are in allProducts
        self.assertIn(str(self.apple.id), all_products)
        self.assertIn(str(self.banana.id), all_products)
        self.assertIn(str(self.carrot.id), all_products)
        
        # Verify products are available with correct prices
        self.assertEqual(all_products[str(self.apple.id)]['price'], 2.50)
        self.assertEqual(all_products[str(self.banana.id)]['price'], 3.00)
        self.assertEqual(all_products[str(self.carrot.id)]['price'], 1.00)
        
    def test_empty_search_shows_all_products_in_both_lists(self):
        """Test that empty search returns all products in both lists."""
        response = self.client.get('/pantry/products/?q=')
        
        products_json = response.context['products_json']
        products = json.loads(products_json)
        
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        # Both should have all 4 products
        self.assertEqual(len(products), 4)
        self.assertEqual(len(all_products), 4)
        
        # Should be identical
        self.assertEqual(set(products.keys()), set(all_products.keys()))
        
    def test_search_with_no_results(self):
        """Test search with no results still provides all_products_json."""
        response = self.client.get('/pantry/products/?q=nonexistentproduct12345')
        
        # products_json might be empty
        products_json = response.context['products_json']
        products = json.loads(products_json)
        
        # all_products_json should still have all products
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        self.assertEqual(len(all_products), 4)
        
    def test_all_products_json_has_required_fields(self):
        """Test that all_products_json has name and price for each product."""
        response = self.client.get('/pantry/products/')
        
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        for product_id, product_data in all_products.items():
            self.assertIn('name', product_data)
            self.assertIn('price', product_data)
            self.assertIsInstance(product_data['name'], str)
            self.assertIsInstance(product_data['price'], (int, float))
            
    def test_search_cart_total_calculation(self):
        """Test that cart total can be calculated with all_products_json during search."""
        # Add items to cart
        session = self.client.session
        session['cart'] = {
            str(self.apple.id): 2,    # 2 * 2.50 = 5.00
            str(self.banana.id): 1,   # 1 * 3.00 = 3.00
            str(self.carrot.id): 4    # 4 * 1.00 = 4.00
        }
        session.save()
        
        # Search for "apple"
        response = self.client.get('/pantry/products/?q=apple')
        
        all_products_json = response.context['all_products_json']
        all_products = json.loads(all_products_json)
        
        # Calculate total using all_products
        cart = session['cart']
        total = sum(
            all_products[str(pid)]['price'] * qty 
            for pid, qty in cart.items()
        )
        
        # Should equal 12.00 (all items, not just Apple)
        self.assertEqual(total, 12.00)
