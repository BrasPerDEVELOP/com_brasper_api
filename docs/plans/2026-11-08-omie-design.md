# Omie en Contabilidad

BRL a PEN/USD usa Omie con Venta final en BRL. SUNAT conserva sus rutas y series.
Empresa: BRASPER 21 CORRETORA DE CAMBIO LTDA. Servicio existente: Remessa internacional.
Cuenta elegida por el usuario: Banco do Brasil. Impuestos heredados del servicio de Omie.

Vista previa resuelve el cliente registrado en Omie por CPF/CNPJ, muestra emisor,
cuenta, servicio y total. La emisión manual confirma el total y documento vigentes.
Un registro único persistido por transacción precede cualquier llamada de creación.
Orden: IncluirOS, ValidarOS, FaturarOS. No se reintentan escrituras automáticamente.
Ante fallos inciertos, consultar la orden por código de integración antes de cualquier
intervención; la interfaz permite consultar, pero no duplicar la solicitud.
Las notas se consultan por OS y se validan emisor e importe. PDF oficial de Omie.

El cliente debe estar registrado en Omie: no crear personas fiscales con direcciones
inventadas ni sobrescribir sus fichas desde la integración. Los fallos de validación
se corrigen en Omie; completar allí la OS existente y consultar estado en Brasper.
La numeración NFS-e pertenece a Omie y es independiente de BB02/FF02.
Credenciales únicamente en variables de entorno del backend, sin endpoints públicos.
Pruebas de red con transportes simulados; producción se valida solo con consultas.
