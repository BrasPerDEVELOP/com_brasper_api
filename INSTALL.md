# Instalación de Dependencias

## Instalación con pip

Si no tienes Poetry instalado, puedes instalar las dependencias directamente con pip:

```bash
cd com_brasper_api
pip install -r requirements.txt
```

O instalar las dependencias críticas manualmente:

```bash
pip install cryptography>=42.0.0 argon2-cffi>=23.1.0
```

## Instalación con Poetry (recomendado)

```bash
cd com_brasper_api
poetry install
```

## Verificar instalación

Para verificar que `cryptography` está instalado:

```bash
python -c "from cryptography.fernet import Fernet; print('✓ cryptography instalado correctamente')"
```

## Nota importante

El módulo `cryptography` requiere compilación de extensiones C, por lo que puede tardar unos minutos en instalarse. Asegúrate de tener las herramientas de compilación instaladas en tu sistema.

### macOS
```bash
xcode-select --install
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get install build-essential python3-dev libffi-dev
```
