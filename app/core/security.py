# app/core/security.py
import secrets
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

# Bytes de aleatoriedad para tokens opacos (48 bytes → ~64 caracteres base64url)
opaque_token_bytes = 48


class SecurityUtils:
    """Utilities for security operations including token and password management"""

    def __init__(self, settings):
        self.settings = settings
        self.redis_client = None

    def hash_password_advanced(self, password: str) -> str:
        """
        Hash de contraseña usando Argon2 (más seguro que PBKDF2).
        Si Argon2 no está disponible, usa PBKDF2 con más iteraciones.
        """
        try:
            from argon2 import PasswordHasher
            ph = PasswordHasher(
                time_cost=3,      # Número de iteraciones
                memory_cost=65536,  # 64 MB de memoria
                parallelism=4,    # 4 hilos paralelos
                hash_len=32,      # Longitud del hash
                salt_len=16       # Longitud del salt
            )
            return ph.hash(password)
        except ImportError:
            # Fallback a PBKDF2 con más iteraciones
            logger.warning("Argon2 not available, using PBKDF2 with increased iterations")
            salt = secrets.token_hex(32)
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                bytes.fromhex(salt),
                200000  # Más iteraciones para mayor seguridad
            )
            return f"{salt}${pwd_hash.hex()}"
    
    def set_redis_client(self, redis_client):
        """Inyectar cliente Redis (deprecated, no se usa)"""
        self.redis_client = redis_client

    def generate_opaque_token(self, user_id: UUID, username: str) -> str:
        """
        Genera un token opaco: cadena aleatoria criptográfica (base64url).
        No lleva payload; la sesión se asocia al token en la base de datos.
        Validación: buscar el token en auth_login (get_by_token).
        """
        return secrets.token_urlsafe(opaque_token_bytes)

    def generate_encrypted_token(self, user_id: UUID, username: str) -> str:
        """Alias para compatibilidad; ahora genera token opaco."""
        return self.generate_opaque_token(user_id, username)

    def store_token_in_redis(
        self,
        token: str,
        user_id: UUID,
        username: str,
        ttl_minutes: int = 1440
    ) -> bool:
        if not self.redis_client:
            logger.error("Redis client not configured")
            return False
        
        try:
            token_key = f"token:{token}"
            token_data = {
                "user_id": str(user_id),
                "username": username,
                "created_at": datetime.utcnow().isoformat(),
                "valid": "true"
            }
            
            self.redis_client.hset(token_key, mapping=token_data)
            self.redis_client.expire(token_key, ttl_minutes * 60)
            
            user_tokens_key = f"user_tokens:{user_id}"
            self.redis_client.sadd(user_tokens_key, token)
            self.redis_client.expire(user_tokens_key, ttl_minutes * 60)
            
            logger.info(f"Token stored in Redis for user: {username}")
            return True
        except Exception as e:
            logger.error(f"Error storing token in Redis: {str(e)}")
            return False
    
    def revoke_token(self, token: str) -> bool:
        """Invalida un token específico (actualiza en base de datos)"""
        # Los tokens se revocan actualizando el campo token en la tabla auth_login a NULL
        # Esta función se mantiene para compatibilidad pero retorna True
        # La revocación real se hace en el repositorio
        logger.debug("Token revocation should be done via database")
        return True
    
    def revoke_all_user_tokens(self, user_id: UUID) -> bool:
        """Invalida todos los tokens de un usuario (actualiza en base de datos)"""
        # Los tokens se revocan actualizando el campo token en la tabla auth_login a NULL
        # Esta función se mantiene para compatibilidad pero retorna True
        # La revocación real se hace en el repositorio
        logger.debug("All tokens revocation should be done via database")
        return True
    
    def hash_password(self, password: str) -> str:
        """
        Hash de contraseña usando método avanzado (Argon2 si está disponible, 
        sino PBKDF2 con más iteraciones).
        """
        return self.hash_password_advanced(password)
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verifica contraseña contra hash. Soporta Argon2, bcrypt y PBKDF2.
        """
        try:
            # Detectar Argon2 (formato: $argon2id$v=19$m=...)
            if hashed.startswith('$argon2'):
                try:
                    from argon2 import PasswordHasher
                    ph = PasswordHasher()
                    ph.verify(hashed, password)
                    return True
                except ImportError:
                    logger.error("Argon2 not installed but Argon2 hash detected")
                    return False
                except Exception:
                    return False
            
            # Detectar si es bcrypt (empieza con $2a$, $2b$, $2y$)
            if hashed.startswith(('$2a$', '$2b$', '$2y$')):
                try:
                    import bcrypt
                    return bcrypt.checkpw(
                        password.encode('utf-8'),
                        hashed.encode('utf-8')
                    )
                except ImportError:
                    logger.error("bcrypt not installed but bcrypt hash detected")
                    return False
            
            # Formato PBKDF2 custom: "salt$hash"
            parts = hashed.split('$')
            
            if len(parts) == 2:
                # Formato simple: salt$hash
                salt, pwd_hash = parts
                # Intentar con diferentes números de iteraciones
                for iterations in [200000, 100000, 50000]:
                    test_hash = hashlib.pbkdf2_hmac(
                        'sha256',
                        password.encode(),
                        bytes.fromhex(salt),
                        iterations
                    )
                    if test_hash.hex() == pwd_hash:
                        return True
                return False
            
            elif len(parts) >= 3:
                # Posible formato werkzeug: pbkdf2:sha256:iterations$salt$hash
                # O formato con prefijo: algorithm$iterations$salt$hash
                logger.warning(f"Unsupported hash format with {len(parts)} parts")
                return False
            
            else:
                logger.error(f"Invalid hash format: expected 'salt$hash', got {len(parts)} parts")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False
    
    def is_password_strong(self, password: str) -> bool:
        """Valida que contraseña cumpla requisitos mínimos"""
        return (
            len(password) >= 8 and
            any(c.isupper() for c in password) and
            any(c.islower() for c in password) and
            any(c.isdigit() for c in password) and
            any(c in '!@#$%^&*()' for c in password)
        )
    
    def generate_recovery_code(self) -> str:
        """Genera código de recuperación"""
        return secrets.token_hex(16)
    
    def secure_compare(self, a: str, b: str) -> bool:
        """Comparación segura contra timing attacks"""
        return secrets.compare_digest(a, b)
