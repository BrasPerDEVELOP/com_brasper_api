"""
Models Registry Module

This module imports all SQLAlchemy models to ensure they are registered
in the SQLAlchemy registry before any other modules try to use them.
"""

# Auth models
from app.modules.auth.domain.models import AuthModel

# User models
from app.modules.users.domain.models import User

# Coin models
from app.modules.coin.domain.models import TaxRate, TaxRateTrial, Commission

# Transaction models
from app.modules.transactions.domain.models import Transaction, Bank, BankAccount, Coupon

print("  All SQLAlchemy models imported and registered successfully")
