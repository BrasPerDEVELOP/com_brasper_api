# Zona telefónica de usuarios

La migración Alembic `090` agrega tres columnas opcionales en `"user"."user"`:

| Campo | Tipo | Ejemplo |
| --- | --- | --- |
| `local_area_code` | Texto de 1 a 6 dígitos | `11` (DDD de Brasil) |
| `local_area_name` | Texto, máximo 150 caracteres | `São Paulo — área DDD 11` |
| `country` | Texto, máximo 100 caracteres | `Brasil` |

Se reciben en los formularios de creación y actualización de `/user` y en el
JSON de actualización de `/auth/me`. Aparecen en las respuestas de usuario,
incluidas las listas generales. No requieren modificar las rutas existentes.

Ejemplo de campos de formulario para actualizar un usuario:

```text
id=<UUID del usuario>
code_phone=+55
phone=11987654321
local_area_code=11
local_area_name=São Paulo — área DDD 11
country=Brasil
```

`phone` conserva su significado actual: número nacional, incluido el DDD.
`local_area_code` guarda el DDD por separado como texto para conservar ceros.
No incluye `+55`. Los dos primeros dígitos del número nacional brasileño
identifican el DDD; sus últimos dígitos no identifican la zona.

Los campos omitidos al actualizar conservan su valor. JSON `null` permite
vaciar un campo; las cadenas de espacios se normalizan a `null`.
La migración deja estos campos en `NULL` en los registros existentes:
no asigna teléfonos de contactos ni deduce ciudades automáticamente.

El país y la zona describen la numeración telefónica; no acreditan residencia
ni nacionalidad. Un DDD puede abarcar varias ciudades o estados. Los nombres
de zona deben reflejar esa ambigüedad.

Aplicar con `python -m alembic upgrade head` usando la conexión configurada
para el entorno de destino.


## Métricas del directorio

`GET /user/metrics` requiere `users.view` y admite `role` (enum de roles).
Devuelve conteos agregados de usuarios no eliminados: total, habilitados,
Brasil, Brasil con DDD válido, Brasil sin DDD válido, países y áreas. Los
agregados se calculan en SQL sin transferir el directorio al navegador.
Brasil incluye los países Brasil/Brazil/BR/BRA; el prefijo +55 se usa solo
cuando no hay país registrado. La zona usa `local_area_code` y
`local_area_name` guardados; los datos faltantes se contabilizan aparte.
No se infieren ciudades ni se expone información personal en la respuesta.
Los porcentajes de cada DDD usan como denominador todos los usuarios de Brasil.
Los códigos válidos siguen la lista de códigos nacionales de Anatel:
https://www.gov.br/anatel/pt-br/regulado/numeracao/plano-de-numeracao-brasileiro

El backoffice lo presenta en `/app/usuarios?view=metrics`, junto al directorio.
Este cambio no añade columnas ni migraciones; requiere las columnas de zona
telefónica de la migración 090 ya existente.
