#!/usr/bin/env python3
"""
Pytest configuration and fixtures for Doris MCP Server tests
"""

import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Provide test configuration"""
    return {
        "doris_host": "localhost",
        "doris_port": 9030,
        "doris_user": "test_user",
        "doris_password": "test_password",
        "doris_database": "test_db",
        "blocked_keywords": ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE"],
        "sensitive_tables": {
            "user_info": "confidential",
            "payment_records": "secret",
            "employee_data": "confidential",
            "public_reports": "public"
        },
        "max_query_complexity": 100
    }


@pytest.fixture
def sample_data():
    """Provide sample test data"""
    return [
        {
            "id": 1,
            "name": "张三",
            "phone": "13812345678",
            "email": "zhangsan@example.com",
            "id_card": "110101199001011234",
            "salary": 50000
        },
        {
            "id": 2,
            "name": "李四",
            "phone": "13987654321",
            "email": "lisi@example.com",
            "id_card": "110101199002022345",
            "salary": 60000
        }
    ]


@pytest.fixture
def test_sql_queries():
    """Provide test SQL queries"""
    return {
        "safe_select": "SELECT name, email FROM users WHERE department = 'sales'",
        "dangerous_drop": "DROP TABLE users",
        "sql_injection": "SELECT * FROM users WHERE id = 1; DROP TABLE users;",
        "union_injection": "SELECT name FROM users UNION SELECT password FROM admin_users",
        "comment_injection": "SELECT * FROM users WHERE id = 1 -- AND password = 'secret'",
        "complex_query": """
            SELECT u.name, u.email, d.department_name
            FROM users u
            JOIN departments d ON u.department_id = d.id
            WHERE u.status = 'active'
            ORDER BY u.created_at DESC
        """
    }
