"""
API Authentication Tests using DRF's APITestCase.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User


class JWTAuthenticationTests(APITestCase):
    """Test JWT token authentication."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cls.admin_user = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123'
        )

    def test_obtain_token_valid_credentials(self):
        """Test obtaining JWT token with valid credentials."""
        url = reverse('api:token_obtain_pair')
        data = {'username': 'testuser', 'password': 'testpass123'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_token_invalid_credentials(self):
        """Test obtaining JWT token with invalid credentials."""
        url = reverse('api:token_obtain_pair')
        data = {'username': 'testuser', 'password': 'wrongpassword'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        """Test refreshing JWT token."""
        # First obtain tokens
        url = reverse('api:token_obtain_pair')
        data = {'username': 'testuser', 'password': 'testpass123'}
        response = self.client.post(url, data, format='json')
        refresh_token = response.data['refresh']

        # Now refresh
        url = reverse('api:token_refresh')
        data = {'refresh': refresh_token}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_verify_token(self):
        """Test verifying JWT token."""
        # First obtain tokens
        url = reverse('api:token_obtain_pair')
        data = {'username': 'testuser', 'password': 'testpass123'}
        response = self.client.post(url, data, format='json')
        access_token = response.data['access']

        # Verify token
        url = reverse('api:token_verify')
        data = {'token': access_token}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_access_protected_endpoint_with_token(self):
        """Test accessing protected endpoint with valid token."""
        # Obtain token
        url = reverse('api:token_obtain_pair')
        data = {'username': 'adminuser', 'password': 'adminpass123'}
        response = self.client.post(url, data, format='json')
        access_token = response.data['access']

        # Access protected endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api:user-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_access_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without token."""
        url = reverse('api:user-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class APIPermissionTests(APITestCase):
    """Test API permission levels."""

    @classmethod
    def setUpTestData(cls):
        cls.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        cls.staff_user = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )

    def _get_token(self, username, password):
        """Helper to get JWT token."""
        url = reverse('api:token_obtain_pair')
        response = self.client.post(
            url,
            {'username': username, 'password': password}
        )
        return response.data['access']

    def test_staff_can_list_users(self):
        """Test that staff users can list users."""
        token = self._get_token('staff', 'staffpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        url = reverse('api:user-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_read_only_access(self):
        """Test that regular users have read-only access."""
        token = self._get_token('regular', 'regularpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Should be able to read
        url = reverse('api:category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_cannot_create(self):
        """Test that regular users cannot create resources."""
        token = self._get_token('regular', 'regularpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        url = reverse('api:category-list')
        data = {'name': 'Test Category'}
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create(self):
        """Test that staff users can create resources."""
        token = self._get_token('staff', 'staffpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        url = reverse('api:tag-list')
        data = {'name': 'Test Tag', 'slug': 'test-tag'}
        response = self.client.post(url, data, format='json')

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_200_OK]
        )
