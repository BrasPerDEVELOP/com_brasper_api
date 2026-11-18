# Descripción de la NFS-e

La vista previa genera `description` a partir del servicio configurado, código de
operación, `origin_amount` y `destination_amount`, y las monedas de la tasa.
Los importes se presentan con dos decimales y separadores brasileños.

`IncluirOS` recibe el mismo texto en `ServicosPrestados[0].cDescServ`. Se mantiene
`nCodServico` para conservar la configuración fiscal del catálogo. `nValUnit`
continúa usando Venta final; los montos transferidos solo forman parte de la descripción.

El backend valida `expected_description`, si se proporciona, antes de reservar o
enviar una orden. Así detecta cambios de montos entre vista previa y emisión.
La descripción y el cuerpo de la orden se guardan en el snapshot existente; no hay
migración. El listado y detalle leen ese texto guardado, sin reconstruirlo con
datos actuales ni alterar notas ya emitidas. Las notas anteriores sin `cDescServ`
guardado no muestran una descripción reconstruida.

Contrato oficial: https://app.omie.com.br/api/v1/servicos/os/ (ServicosPrestados,
`cDescServ`: descripción principal; sin valor explícito usa el catálogo del servicio).

Pruebas: `pytest tests/test_omie_description.py tests/test_omie_service.py`.
No se emitieron notas reales durante estas pruebas.
