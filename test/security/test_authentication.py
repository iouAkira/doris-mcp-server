#!/usr/bin/env python3
"""
Authentication module tests
"""

import pytest
from datetime import datetime

from doris_mcp_server.utils.security import (
    AuthenticationProvider,
    AuthContext,
    SecurityLevel
)


class TestAuthenticationProvider:
    """Authentication provider tests"""

    @pytest.fixture
    def auth_provider(self, test_config):
        """Create authentication provider instance"""
        return AuthenticationProvider(test_config)

    @pytest.mark.asyncio
    async def test_token_authentication_success(self, auth_provider):
        """Test successful token authentication"""
        auth_info = {
            "type": "token",
            "token": "valid_token_123"
        }
        
        result = await auth_provider.authenticate(auth_info)
        
        assert isinstance(result, AuthContext)
        assert result.user_id == "test_user"
        assert "data_analyst" in result.roles
        assert result.security_level == SecurityLevel.INTERNAL

    @pytest.mark.asyncio
    async def test_token_authentication_failure(self, auth_provider):
        """Test failed token authentication"""
        auth_info = {
            "type": "token",
            "token": "invalid_token"
        }
        
        with pytest.raises(Exception):
            await auth_provider.authenticate(auth_info)

    @pytest.mark.asyncio
    async def test_basic_authentication_success(self, auth_provider):
        """Test successful basic authentication"""
        auth_info = {
            "type": "basic",
            "username": "admin",
            "password": "admin123"
        }
        
        result = await auth_provider.authenticate(auth_info)
        
        assert isinstance(result, AuthContext)
        assert result.user_id == "admin_user"
        assert "data_admin" in result.roles
        assert result.security_level == SecurityLevel.SECRET

    @pytest.mark.asyncio
    async def test_basic_authentication_failure(self, auth_provider):
        """Test failed basic authentication"""
        auth_info = {
            "type": "basic",
            "username": "admin",
            "password": "wrong_password"
        }
        
        with pytest.raises(Exception):
            await auth_provider.authenticate(auth_info)

    @pytest.mark.asyncio
    async def test_unsupported_auth_type(self, auth_provider):
        """Test unsupported authentication type"""
        auth_info = {
            "type": "oauth",
            "token": "oauth_token"
        }
        
        with pytest.raises(Exception):
            await auth_provider.authenticate(auth_info) 