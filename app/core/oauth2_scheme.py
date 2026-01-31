"""
Módulo para definir el esquema OAuth2 utilizado en toda la aplicación.
Se define aquí para evitar dependencias circulares entre main.py y dependencies.py
"""
from fastapi.security import OAuth2PasswordBearer

# Configurar el esquema OAuth2 para Swagger
# auto_error=False permite que sea opcional en el código, pero Swagger aún lo detectará
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login/",
    scheme_name="OAuth2PasswordBearer",
    auto_error=False  # No lanza error si no hay token, pero Swagger aún lo mostrará
)
