# Verificación operativa del 7 de octubre de 2026

Revisión técnica de la recuperación y del cambio de dominio. La instalación
ejecuta el commit `28fabfa2273124873aa5e9d33a946431e69ad5a7`, aprobado mediante
la [PR #7](https://github.com/sihsalus/sihsalus-terminology/pull/7) y contenido en
el merge `f042f08642613ad3a2a94521e8e59194aee1870d`. Los journals, respaldos y
claves permanecen en almacenamiento privado; no se adjuntan configuraciones,
tokens ni URLs firmadas.

Las nueve imágenes instaladas se cotejaron con sus digests y con el manifiesto
de la [construcción verificada](https://github.com/sihsalus/sihsalus-terminology/actions/runs/37696559376).
El SHA-256 del manifiesto es
`b1b12b3042b51d6761abaf0ea179b3346c639a77b7d58b20c42015fe0a550363`.
Los servicios están en ejecución, sin OOM ni reinicios, y pasan los cinco
healthchecks definidos. Worker, importer, scheduler y storage requieren además
comprobaciones funcionales; su estado de proceso no las sustituye. API,
navegador y servicios de datos empaquetados declaran la revisión mediante sus
etiquetas OCI.

## Resultado funcional

La interfaz está disponible en
[sih-terminology.inf.pucp.edu.pe](https://sih-terminology.inf.pucp.edu.pe), con API
en `api.gidis-terminology.duckdns.org`. El navegador muestra los 18 catálogos de
SIHSALUS, la versión original `medicamentos/2026-06-30` y el detalle de ABACAVIR.
Una descarga real del catálogo desde la interfaz produjo un ZIP de 280 185
bytes, con 1 001 conceptos y 17 mappings. Su SHA-256 es
`94d56b94fe320ccb869998f760a798d6ac156786bd076bd9e2df79888f892359`.

La revisión anterior y el clon restaurado verificaron mediante API una fuente
privada temporal con un único concepto identificado como sintético:

- Autenticación y rechazo de creación sin autorización.
- Ocultación de la fuente privada a una petición sin sesión.
- Creación, edición y lectura posterior del concepto.
- Búsqueda del concepto después de completar su indexación.
- Publicación de una versión y finalización de su tarea.
- Exportación ZIP y cotejo de fuente, versión y nombre editado dentro del JSON.
- Eliminación de la fuente de prueba y comprobación posterior de ausencia.

El journal API de la revisión anterior y el journal API del clon registran,
cada uno, `verified-and-clean` y 15 comprobaciones satisfactorias.
La descarga por API se efectuó sin reenviar el token al almacenamiento; esto
no acreditaba todavía la descarga desde la interfaz. Durante la aceptación del
clon se encontró el fallo de exportación descrito más abajo. No se modificaron
catálogos asistenciales ni se repitieron sus importaciones o publicaciones.

En el dominio institucional se repitió el flujo completo desde un navegador
real: creación de una fuente privada nueva, creación y edición del concepto,
persistencia después de recargar, búsqueda por su ID y publicación de
`browser-1`. La exportación de esa versión descargó un ZIP de 1 610 bytes con
un concepto y el nombre editado esperado. Tanto esta descarga como la del
catálogo original usaron el host institucional y no enviaron `Authorization`,
`Cookie`, `Content-Type` ni otros encabezados de API al almacenamiento.
La traza de ese flujo no contiene errores HTTP, CORS ni de consola.

La aceptación nueva terminó con 25 comprobaciones satisfactorias y journal
`verified-and-clean`. La fuente propia se eliminó con HTTP 204 y sus cuatro
URLs devolvieron 404. Los conteos de base regresaron exactamente a la línea
base; los 34 registros de fuentes/versiones originales y `bancosangre`
permanecieron iguales. Ambos workers y el broker quedaron sin tareas, Redis
respondió PONG y las sondas críticas devolvieron `working`. Los nueve
contenedores e imágenes permanecieron iguales durante la prueba. Este resultado
corresponde al dominio y código nuevos; no modifica el 15/16 histórico del clon.

## Recuperación comprobada

Se ejecutó el procedimiento existente `scripts/terminology/backup.sh` después
de comprobar que no había trabajo activo o reservado. Se reanudaron los
servicios y se conservó `PAUSE` del proceso histórico de migración.

El archivo cifrado `runtime-20261007T064500Z.tar.enc` tiene SHA-256
`b9e7675affb66050e8100f1f8d964bf4d03df01976c1025f1caa86efeadb9be1`.
La copia fuera de la VM se cotejó con ese hash y se verificó su descifrado con
la clave almacenada por separado y con permisos restrictivos.

Primero se restauraron PostgreSQL y archivos en recursos aislados. Después se
levantó una instalación completa de nueve servicios con las imágenes y la
configuración registradas en el mismo respaldo, sobre cinco volúmenes nuevos.
No se ejecutó `bootstrap`, no se cambió el tráfico público y no se reutilizaron
volúmenes de la instalación activa. Los conteos restaurados coinciden:

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
respectivamente. Los recursos del primer ensayo se retiraron después de
registrar el resultado `verified`.

En la instalación completa se reconstruyó Elasticsearch a partir de PostgreSQL:
67 484 conceptos y 40 632 mappings. La indexación finalizó el 7 de octubre a las
21:34:28 UTC. Se comprobaron las 17 fuentes originales, sus 17 versiones
publicadas, sus estados y descripciones, y búsquedas de conceptos canónicos en
cada catálogo. `bancosangre` también se conservó. La aceptación por API pasó las
15 comprobaciones del flujo sintético.

En un navegador real del clon pasaron 15 de 16 comprobaciones: autenticación,
catálogos, búsqueda, detalle, creación, edición persistente, publicación y
limpieza. Falló la descarga de la exportación en caché. La misma operación de
solo lectura falló en la instalación pública anterior: la redirección XHR desde
la API al almacenamiento enviaba `Origin: null`, rechazado por CORS. Por tanto,
el ensayo confirmó recuperación de datos, índices y aplicación, pero conservó
explícitamente esa aceptación de navegador incompleta.

La PR #7 corrigió el componente responsable: la API puede devolver el enlace
firmado con `noRedirect=true`, después de sus comprobaciones existentes de
permisos y estado. La interfaz lo descarga con una petición nueva sin token ni
encabezados de API; los clientes que usan la redirección HTTP 302 siguen siendo
compatibles. Se verificaron 46 pruebas de API, 7 de frontend, lint, build y CI.
No se amplió CORS a `Origin: null` ni se cambiaron estilos o modelos.

Después de conservar y cotejar los journals fuera de la VM se retiraron
únicamente los nueve contenedores, cinco volúmenes y cuatro archivos descifrados
del clon. Las cuatro URLs de sus recursos sintéticos devolvieron 404, los datos
originales permanecieron iguales y ambos workers y el broker quedaron sin
trabajo. Se preservaron el respaldo cifrado, la clave separada, `PAUSE` y todos
los recursos activos. La limpieza no transforma el fallo histórico en un pase;
la aceptación del código corregido se registra por separado en el dominio nuevo.

## Actualización y respaldo previo

La actualización siguió `deploy-terminology.sh ... update`: respaldo cifrado,
arranque por etapas y plan de migraciones registrado, sin recargar fixtures ni
restablecer cuentas. Terminó con código cero; `release.py verify` cotejó los
nueve servicios contra el manifiesto. La configuración instalada coincide con
`active.env` y conserva las credenciales anteriores.

El respaldo inmediatamente anterior a la actualización,
`runtime-20261007T224213Z.tar.enc`, tiene SHA-256
`a749b22133ddb0d412d2288e69f30aec2b20834b0591e48a80db00e7619fb0bd`.
Se copió fuera de la VM, se cotejó con el hash remoto y se verificó el descifrado
y el inventario tar en memoria, sin extraer secretos. Contiene base, uploads,
objetos, configuración y referencias de imágenes. La clave permanece separada.
El ensayo completo descrito arriba corresponde al respaldo de las 06:45 UTC;
no se presenta la inspección del respaldo nuevo como otra restauración completa.

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

## DNS, HTTPS y renovación

`sih-terminology.inf.pucp.edu.pe` resuelve a `200.16.7.139` en los servidores
autoritativos y los resolvers públicos comprobados. El hostname de navegador
se actualizó en la configuración instalada y en la Variable del entorno
`terminology` de GitHub; la API conserva su nombre existente. El alias
`gidis-hsc-terminology.inf.pucp.edu.pe` sigue devolviendo NXDOMAIN y requiere
revisión DNS si se decide usarlo; no bloquea el nombre institucional operativo.

El certificado emitido cubre el navegador nuevo, la API y el navegador anterior.
Los tres nombres pasan validación TLS estricta. Nginx redirige la interfaz
anterior al dominio institucional y mantiene lectura directa de sus
`/terminology-exports/` para conservar enlaces firmados anteriores. Se validaron
HTTP 200, la configuración del navegador y CORS del inicio de sesión desde el
origen nuevo; las URLs firmadas no se guardan en logs de acceso.

Se conservó fuera de la VM un respaldo cifrado de los certificados previos.
Ningún sitio activo referencia la línea de certificado anterior, que se retiró
localmente sin revocarla. La línea nueva es la única configurada para renovación;
un deploy hook restringido a ella comprueba y recarga Nginx. Pasó
`certbot renew --dry-run --run-deploy-hooks`; `certbot.timer` permanece activo y
habilitado y el timer de respaldo está activo. El certificado vence el
5 de enero de 2027 a las 20:37:00 UTC.

Esta revisión es aceptación técnica del servicio. No sustituye la validación
clínica de los catálogos ni la evaluación de usuarios de la tesis.
