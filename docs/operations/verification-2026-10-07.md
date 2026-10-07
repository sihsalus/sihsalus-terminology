# Verificación operativa del 7 de octubre de 2026

Revisión técnica de la instalación correspondiente al commit
`db58689951faa8895c1755d633dd903a46c0fd13`. Los journals, respaldos y claves
permanecen en almacenamiento privado; no se adjuntan configuraciones ni tokens.

Las nueve imágenes instaladas se cotejaron con las referencias por digest
seleccionadas y con el manifiesto de la [construcción verificada](https://github.com/sihsalus/sihsalus-terminology/actions/runs/37405828682).
Los servicios están en ejecución, sin OOM. API, navegador y servicios de datos
empaquetados declaran la revisión indicada mediante sus etiquetas OCI.

## Resultado funcional

La interfaz y la API siguen disponibles mediante sus nombres HTTPS DuckDNS.
La prueba autenticada se realizó sobre una fuente privada temporal del usuario
de prueba, con un único concepto identificado como sintético. Se verificaron:

- Autenticación y rechazo de creación sin autorización.
- Ocultación de la fuente privada a una petición sin sesión.
- Creación, edición y lectura posterior del concepto.
- Búsqueda del concepto después de completar su indexación.
- Publicación de una versión y finalización de su tarea.
- Exportación ZIP y cotejo de fuente, versión y nombre editado dentro del JSON.
- Eliminación de la fuente de prueba y comprobación posterior de ausencia.

El journal final registra `verified-and-clean`, con 15 comprobaciones
satisfactorias. La descarga de la exportación se efectuó sin reenviar el token
de API al destino de descarga. No se modificaron catálogos asistenciales ni se
repitieron sus importaciones o publicaciones.

## Recuperación comprobada

Se ejecutó el procedimiento existente `scripts/terminology/backup.sh` después
de comprobar que no había trabajo activo o reservado. Se reanudaron los
servicios y se conservó `PAUSE` del proceso histórico de migración.

El archivo cifrado `runtime-20261007T064500Z.tar.enc` tiene SHA-256
`b9e7675affb66050e8100f1f8d964bf4d03df01976c1025f1caa86efeadb9be1`.
La copia fuera de la VM se cotejó con ese hash y se verificó su descifrado con
la clave almacenada por separado y con permisos restrictivos.

Se restauró PostgreSQL en un contenedor aislado, sin red ni puertos publicados.
Los conteos restaurados coinciden con el respaldo recién tomado:

| Entidad | Registros |
| --- | ---: |
| Fuentes | 48 |
| Conceptos | 67 484 |
| Mapeos | 40 632 |
| Nombres | 156 534 |
| Descripciones | 36 708 |

Se cotejaron los 17 catálogos del manifiesto de migración. Existe además
`bancosangre`; por tanto, no debe confundirse «17 importados» con el total de
fuentes de la organización ni eliminar fuentes adicionales. Los archivos de
uploads y objetos se extrajeron a otros dos volúmenes aislados y se compararon
por contenido, modo, UID y GID, incluido el directorio raíz: 1 y 166 entradas,
respectivamente. Los tres volúmenes y el contenedor de la prueba se retiraron
después de registrar el resultado `verified`.

Esta prueba acredita lectura del backup y restauración de base y archivos.
No acredita un cambio de DNS, una conmutación completa de tráfico ni el tiempo
de reconstrucción de Elasticsearch; el índice continúa reconstruyéndose según
el procedimiento de recuperación y no se restaura desde ese archivo.

## Salud y Flower

La consulta autenticada a `healthcheck/?format=json` devuelve HTTP 200 y
`working` para base de datos, Elasticsearch y las ocho colas de Celery. Flower
devuelve `unavailable` porque no forma parte de los servicios desplegados.
Se comprobó que `FlowerHealthCheck.critical_service` es `False`: el panel
agregado incluye esta sonda opcional aunque el servicio no exista.

Este aviso no demuestra caída de la API ni justifica restaurar automáticamente
el servidor. Deben distinguirse las sondas críticas y las del diagnóstico
opcional. Las dos instancias de worker respondieron con cero tareas activas,
reservadas o programadas al finalizar la revisión. No se añadió Flower ni se
ocultó su aviso mediante una modificación del contenedor.

## DNS institucional pendiente

El 7 de octubre, `sih-terminology.inf.pucp.edu.pe` resuelve al servidor vigente.
`gidis-hsc-terminology.inf.pucp.edu.pe` devuelve NXDOMAIN tanto en Google como
en Cloudflare. Esto contradice la disponibilidad pública indicada en la
comunicación del día anterior y requiere revisión del administrador DNS.

Se preparó una respuesta para revisión, con destinatario y copia verificados
mediante Gmail, guardada en Drafts y sin enviar. Antes de migrar deben
confirmarse los nombres de navegador y API, su resolución
pública e interna y la emisión satisfactoria del certificado para ambos.
Mientras tanto se conserva la instalación HTTPS funcional.
