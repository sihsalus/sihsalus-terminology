# Terminología en un host dedicado

Este repositorio mantiene el código de API, navegador y su operación mediante `docker-compose.terminology.yml`, independiente
del stack clínico y de sus bases de datos. Todas las imágenes se descargan por
digest; no se compila en `gidis-terminology`.

## Preparación

1. Construir y verificar las imágenes API, web, PostgreSQL, Redis y Elasticsearch
   en el workflow `Terminology runtime`. Exigir pruebas, análisis de dependencias y escaneo de las imágenes
   satisfactorios en el mismo commit que se despliega.
   El workflow `Terminology runtime` comprueba además el almacenamiento
   consumido directamente por digest. Las imágenes derivadas conservan las
   versiones de servicio y actualizan sus dependencias; su arranque se comprueba
   en CI antes de llegar al host.
2. Conservar backups cifrados de los volúmenes anteriores fuera de la VM.
   Inspeccionar copias de sus bases antes de seleccionar qué datos migrar.
   No renombrar ni reutilizar automáticamente los volúmenes `ocl_*` o `oclweb2_*`.
3. Preparar un checkout limpio de esta revisión en el servidor y generar
   `.env.terminology` con `bash scripts/security/secrets_generate.sh .env.terminology`.
   Completar las variables documentadas en `.env.template`, incluidos el
   `/etc/machine-id` esperado, SHA fuente y referencias por digest.
4. Instalar `terminology/sihsalus-terminology.slice` en `/etc/systemd/system/`;
   ejecutar `systemctl daemon-reload` y habilitar la unidad. Docker debe usar
   el controlador systemd. El conjunto tiene un máximo de 5 GiB, 1.5 CPU y
   1 GiB de swap; cada servicio tiene además su límite individual.
5. Mantener `vm.max_map_count` al menos en 262144. Reservar 10 GiB de disco
   después del pull y espacio adicional para backups y la versión anterior.
6. Instalar la plantilla Nginx con el hostname real y los certificados
   existentes; validar con `nginx -t` antes de recargar. Solo sustituir
   `${TERMINOLOGY_HOST}` y `${TERMINOLOGY_API_HOST}`: las variables de Nginx deben permanecer literales.
   Conservar `certbot.timer` y verificar que renueva el certificado.

## Primera instalación

```sh
bash scripts/deploy/deploy-terminology.sh /ruta/privada/.env.terminology bootstrap
```

El script comprueba identidad, recursos, configuración y revisión OCI, inicia
las dependencias, ejecuta la inicialización y arranca la aplicación por etapas.
No elimina contenedores ni volúmenes anteriores. Un bootstrap fallido conserva
su estado; se inspecciona antes de reintentar. Los journals privados quedan en
`.env.terminology-state/` y nunca se publican.

El navegador y la API usan nombres DNS distintos con HTTPS en 443, y el
certificado debe cubrir ambos nombres. Las exportaciones firmadas usan
`/terminology-exports/`. Nginx consume servicios ligados a localhost. PostgreSQL,
Redis y Elasticsearch no publican puertos. Las credenciales iniciales del usuario
`ocladmin` están en el archivo privado; no se incluyen en logs ni en informes.
El navegador ofrece acceso con cuentas locales cuando no hay un proveedor OIDC
configurado. El registro público está deshabilitado; el administrador crea las
cuentas. El envío de correo está desactivado hasta configurar y autorizar un
servicio SMTP; el acceso local usa el soporte del administrador. La API no instala el middleware que registra cuerpos de peticiones y
respuestas, pues pueden contener credenciales.

## Correo SMTP

La configuración se guarda en `.env.terminology` con permisos 600. Para activar
el envío, establecer `TERMINOLOGY_EMAIL_BACKEND` en
`django.core.mail.backends.smtp.EmailBackend` y completar las variables
`TERMINOLOGY_EMAIL_HOST_USER`, `TERMINOLOGY_EMAIL_HOST_PASSWORD`,
`TERMINOLOGY_DEFAULT_FROM_EMAIL`, `TERMINOLOGY_COMMUNITY_EMAIL` y
`TERMINOLOGY_REPORTS_EMAIL`. El remitente debe estar autorizado por el proveedor;
los dos últimos campos identifican los destinatarios propios de soporte y
reportes. El despliegue rechaza SMTP autenticado si falta cualquiera de ellos.

Los valores predeterminados son `smtp.gmail.com`, puerto 587, STARTTLS obligatorio
y espera máxima de 20 segundos por operación. `TERMINOLOGY_EMAIL_HOST` y
`TERMINOLOGY_EMAIL_PORT` permiten seleccionar otro proveedor con STARTTLS.
Para Gmail se usa la contraseña de aplicación de la cuenta, nunca la contraseña
habitual ni los códigos de respaldo. Guardarla únicamente en la configuración
privada, también incluida en el respaldo cifrado; no imprimir el modelo Compose
resuelto ni las variables de los contenedores.

`TERMINOLOGY_ADMIN_EMAIL` es opcional y queda vacío para evitar informes
automáticos de errores. Solo activarlo si se aprueba el destino y el contenido
diagnóstico. La imagen debe incluir la configuración de correo local, sin los
destinatarios predeterminados de OCL. Aplicar el cambio mediante el procedimiento
de actualización, que conserva la configuración y las imágenes anteriores.

Comprobar conexión, certificado TLS y autenticación desde el contenedor de la
aplicación mediante `django.core.mail.get_connection().open()`, cerrando después
la conexión. Esta comprobación no envía mensajes ni demuestra entrega al buzón.
El envío de un mensaje de prueba requiere acordar previamente el destinatario
y su contenido. La recuperación de contraseña usa la URL HTTPS del navegador
configurada en `WEB_URL`; el registro público continúa deshabilitado.

Para desactivar el correo, volver a
`TERMINOLOGY_EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend` y
recrear los servicios de aplicación conservando los datos. No revertir a una
imagen que mantenga destinatarios de OCL con SMTP habilitado.

## GitHub Secrets y sincronización manual

El entorno `terminology` del repositorio `sihsalus/sihsalus-terminology` administra los
parámetros de la instalación. El workflow **Terminology runtime** mantiene
sus verificaciones de operación y permite elegir `configuration=check` o `apply` al
ejecutarlo manualmente. Push y PR verifican el código y la operación; las imágenes se publican
fuera de los PR. Solo una ejecución manual con `check` o `apply` accede
al entorno de despliegue.

Guardar como **Secrets** `TERMINOLOGY_DB_PASSWORD`, `TERMINOLOGY_SECRET_KEY`,
`TERMINOLOGY_ADMIN_PASSWORD`, `TERMINOLOGY_ADMIN_TOKEN`,
`TERMINOLOGY_STORAGE_ACCESS_KEY`, `TERMINOLOGY_STORAGE_SECRET_KEY`,
`TERMINOLOGY_EMAIL_HOST_PASSWORD` y `TERMINOLOGY_SSH_PRIVATE_KEY`.
Guardar como **Variables** los doce parámetros no secretos enumerados en
`VARIABLE_KEYS` de `scripts/terminology/sync-github-config.py`, además de
`TERMINOLOGY_SSH_TARGET` (`usuario@host`, puerto 22) y
`TERMINOLOGY_SSH_KNOWN_HOSTS`. `TERMINOLOGY_ADMIN_EMAIL` puede omitirse para
mantener desactivados los informes de errores.

La clave SSH es exclusiva de esta integración. Instalar su clave pública en
`authorized_keys` con `restrict` y un comando forzado que ejecute
`python3 /ruta/sihsalus-terminology/scripts/terminology/sync-github-config.py receive`.
No copiar una clave personal ni las claves de DEV/QLTY. Obtener la clave pública
del host mediante una conexión previamente verificada y fijarla en
`TERMINOLOGY_SSH_KNOWN_HOSTS`; el cliente exige comprobación estricta.
Limitar las ramas del entorno a `main`. Una rama exacta puede habilitarse durante
la puesta en marcha autorizada y debe retirarse al finalizar.

Antes de ejecutar el workflow, instalar en el servidor el mismo commit de
operación que se seleccionará en GitHub, con checkout limpio. El receptor
rechaza un SHA distinto, un nodo distinto, claves desconocidas o un despliegue
pendiente. Los valores llegan por stdin cifrado por SSH y no aparecen en sus
argumentos ni en los logs. El script usa el lector dotenv del despliegue y
admite valores escalares sin saltos de línea ni comillas simples.

`check` informa únicamente los nombres de parámetros diferentes. `apply`
conserva la versión instalada y sus imágenes por digest; si la configuración
coincide, no escribe el archivo ni reinicia los servicios. Si cambia, conserva
un journal privado y aplica el procedimiento existente de actualización,
incluidos el respaldo cifrado y los límites de recursos. Un fallo conserva la
evidencia y requiere revisar el journal antes de reintentar.
No se rotan mediante este flujo las credenciales persistidas de base de datos,
almacenamiento y administración, ni la clave Django o la identidad del host:
requieren un procedimiento coordinado. La contraseña SMTP sí puede actualizarse.

Los secretos permanecen también en `.env.terminology` con permisos 600 para
que la aplicación pueda arrancar y recuperarse sin depender de GitHub. El
archivo forma parte del respaldo cifrado. `recovery.key` se conserva en su
ubicación privada y fuera de la VM; no se guarda en GitHub Secrets ni en
artifacts. Cambiar un Secret en GitHub no cambia la VM hasta ejecutar `apply`.

## Aceptación

- Verificar el digest y revisión de las imágenes ejecutadas, salud de todos los
  servicios, límites efectivos del cgroup y ausencia de reinicios por memoria.
- Comprobar autenticación y rechazo de operaciones no autorizadas.
- Crear, editar, consultar y publicar un concepto sintético desde el navegador.
- Descargar la exportación por HTTPS y comprobar su contenido y enlaces.
- Importar una copia de los catálogos SIHSALUS y comparar códigos, UUID, mappings
  y conteos con la fuente. Medir consultas mientras se ejecuta una importación.
- Probar la restauración del backup en volúmenes distintos antes de declarar
  recuperable la instalación. Los originales se conservan hasta la aceptación.
- Integrar únicamente versiones publicadas en SIHSALUS; mantener la terminología
  empaquetada para que las pantallas clínicas no dependan de este host.

## Preparar la migración de catálogos

```sh
python3 scripts/terminology/prepare-import.py \
  --repo /ruta/sihsalus-content --ref COMMIT_REVISADO \
  --output /ruta/privada/catalogos
```

El directorio de salida debe ser nuevo. El manifiesto identifica el commit, los
hashes de los ZIP originales y los lotes, y conserva los registros esperados
para comparar códigos, `external_id`, nombres y relaciones después de cargar.
Los lotes tienen hasta 500 registros para limitar el trabajo por tarea. Esta
cifra es un límite operativo de importación, no una restricción del catálogo.

Cargar los lotes en el orden del manifiesto mediante `/importers/bulk-import/`, con
`parallel=2`: primero todos los conceptos y después todos los mappings. Los dos
procesos comparten el límite de CPU y memoria del worker; el coordinador usa un
proceso separado. Celery recibe directamente las señales de parada de Docker. Los ZIP
de trabajo se marcan `HEAD` para que el importador oficial de OCL no publique una
versión antes de terminar sus mappings. No cambian los códigos ni los UUID de
los registros. Comprobar cada resultado, reconciliar los registros persistidos
y solo entonces crear las versiones indicadas en el manifiesto y exportarlas.
El procedimiento inicial requiere fuentes vacías; una actualización de catálogos
existentes necesita revisar el diff y conservar la versión anterior.

Redis conserva los resultados completados durante una hora; los informes de
tareas persistentes permanecen en PostgreSQL y los lotes aceptados tienen
además su resultado en el directorio privado de migración. Esta ventana evita
acumular copias completas de toda la migración en la memoria del broker.
Mantener los lotes y sus tareas coordinadoras por debajo de una hora y revisar
este límite antes de ejecutar importaciones mayores. No se aplica una política
de expulsión a las colas de Redis.

El ejecutor prefork reutiliza conexiones PostgreSQL durante 60 segundos mediante
`DB_CONN_MAX_AGE`. Django comprueba su salud y el ciclo de tareas de Celery cierra
las conexiones caducadas o inutilizables. La API, el coordinador y el scheduler
conservan el valor predeterminado cero. Se mantienen dos procesos ejecutores y
el máximo de 40 conexiones de PostgreSQL; comprobar conexiones activas, recursos
y rendimiento real después de una actualización de Django o Celery.

Aceptar un lote no significa que hayan terminado todas sus tareas derivadas.
Antes de publicar o respaldar, comprobar también los workers y las colas.
Si una exportación espera detrás de miles de actualizaciones de relaciones,
mantener la importación pausada hasta completar la comparación; conservar el
identificador de la tarea y revisar su estado antes de reenviar una operación.

`import-catalogs.py` conserva el identificador de cada tarea antes de consultar
su resultado y bloquea una segunda ejecución sobre el mismo directorio.
Crear un archivo `PAUSE` en el directorio privado de catálogos permite terminar
el lote actual sin enviar el siguiente. Para continuar, retirar ese archivo y
ejecutar de nuevo el mismo comando; no se repiten los lotes aceptados.

### Comparar y publicar

Al terminar la carga, recuperar las opciones de edición de las fuentes y
comparar una exportación nueva de cada catálogo:

```sh
python3 scripts/terminology/reconcile-catalogs.py \
  --env /ruta/privada/.env.terminology --catalogs /ruta/privada/catalogos \
  --restore-source-settings
```

El importador ZIP de OCL no traslada todas las opciones de generación de códigos
y UUID. El comando las recupera mediante la API de fuentes, junto con sus
metadatos originales. Esta operación se hace después de cargar los registros,
para conservar también los identificadores originalmente nulos. Guarda la
configuración anterior en el directorio privado. Sin `--restore-source-settings`
solo compara y detiene el proceso si encuentra diferencias.

La comparación exige todos los lotes de la fuente aceptados y excluye una
importación simultánea. Comprueba códigos, UUID externos, nombres, descripciones,
idiomas, retiros, relaciones jerárquicas, mappings y metadatos de la fuente.
Conserva los ZIP verificados y sus hashes en `reconciled-head/`; `--source NOMBRE`
permite trabajar con un catálogo sin borrar los informes de los demás.
Una importación con estado `SUCCESS` no sustituye esta comparación.

Solo después de reconciliar todos los catálogos, crear secuencialmente las
versiones originales con `POST /orgs/SIHSALUS/sources/FUENTE/versions/`, usando
`version`, `version_description` y `released` del manifiesto como los campos
`id`, `description` y `released`. La respuesta inicial puede representar trabajo
asíncrono: consultar cada versión hasta que exista y termine su procesamiento.
No enviar de nuevo una publicación cuyo resultado sea desconocido.

```sh
python3 scripts/terminology/reconcile-catalogs.py \
  --env /ruta/privada/.env.terminology --catalogs /ruta/privada/catalogos \
  --published
```

Esta segunda comparación usa las versiones publicadas y conserva su evidencia
en `reconciled-published/`. Resolver cualquier diferencia antes de configurar
consumidores clínicos. Los catálogos provienen de una revisión inmutable de
`sihsalus-content`; la migración conserva sus versiones y no constituye una
nueva aceptación clínica ni incorpora códigos SNOMED CT adicionales.

## Actualización y recuperación

### De CI a la versión instalada

1. Elegir una ejecución **completa y satisfactoria** de `Terminology runtime`
   sobre el SHA de `main` aprobado. El job `Collect verified release` solo corre
   cuando las cinco imágenes y la operación han pasado sus verificaciones.
   Su artifact `terminology-release-<SHA>` contiene `release.json`: SHA fuente,
   ejecución y seis digests. Los escaneos originales permanecen en los artifacts
   de esa misma ejecución. Descargar el manifiesto desde Actions; no reconstruirlo
   juntando resultados de ejecuciones distintas.
2. Guardar fuera de la VM el manifiesto, la evidencia de CI y el respaldo cifrado
   recuperable. Los artifacts de Actions caducan. El JSON no está firmado y su
   validez depende de obtenerlo de esa ejecución aprobada; editarlo o ejecutar
   `manifest` localmente no demuestra que CI haya pasado.
3. Revisar las migraciones y reservar una ventana sin importaciones ni edición.
   Instalar ese SHA en el checkout operativo limpio. Registrar el SHA operativo
   anterior antes de actualizar el checkout. No cambiar el nombre de proyecto
   Compose, los volúmenes ni la ubicación del checkout que usan SSH y el timer.
4. En el servidor, preparar un candidato privado. El comando conserva los
   secretos y los parámetros existentes y cambia únicamente SHA y cinco imágenes.
   Exige el checkout del SHA fuente, digests inmutables, almacenamiento coincidente
   y un destino nuevo. No inicia contenedores ni modifica la configuración instalada.

```sh
set -euo pipefail
umask 077
cd /home/gidis-f1/sihsalus-terminology
test -z "$(git status --porcelain)"
journal=$(mktemp -d "$PWD/.env.terminology-state/release-XXXXXXXX")
# /ruta/privada/release.json es el artifact descargado de la ejecución aprobada.
install -m 600 /ruta/privada/release.json "$journal/release.json"
cp .env.terminology-state/active-distro-commit "$journal/previous-operations-commit"
cmp .env.terminology .env.terminology-state/active.env
cp .env.terminology "$journal/previous.env"
python3 scripts/terminology/release.py prepare \
  "$journal/release.json" "$PWD/.env.terminology" "$journal/target.env"
```

5. Tras revisar el candidato en privado, instalarlo y usar el despliegue existente.
   Este conserva `active.env`, hace el backup y comprueba la revisión OCI descargada
   antes de aplicar migraciones. Conservar el journal aunque el comando falle.

```sh
install -m 600 "$journal/target.env" .env.terminology
bash scripts/deploy/deploy-terminology.sh "$PWD/.env.terminology" update \
  /home/gidis-f1/terminology-backups > "$journal/deploy.log" 2>&1
python3 scripts/terminology/release.py verify \
  "$journal/release.json" "$PWD/.env.terminology" > "$journal/runtime.json"
```

6. `verify` exige los nueve contenedores, sus digests y revisiones, cero reinicios
   y ausencia de OOM; comprueba los cinco healthchecks existentes. Worker,
   importer, scheduler y storage solo acreditan proceso en ejecución. Completar
   la sección **Aceptación**: HTTPS, autenticación, permisos, búsqueda, edición,
   publicación, exportación y recuperación. Un contenedor sano no demuestra que
   esos flujos funcionen. Registrar resultado, SHA, fecha y entorno por separado.
7. Conservar fuera de la VM el respaldo cifrado nuevo y el journal privado.
   `active-distro-commit` registra el código de operación; `source_commit` del
   manifiesto identifica las imágenes. `active.env` indica configuración arrancada,
   no aceptación funcional. La sincronización de GitHub Secrets sigue siendo un
   flujo separado que conserva las imágenes instaladas.

### Recuperar una actualización fallida

Revisar primero el journal, `backup.log` y `migration-plan.log`. No reintentar ni
restaurar automáticamente por el resultado de un healthcheck.

- Si se detuvo **antes de cambiar contenedores o datos**, comparar las imágenes
  ejecutadas con el manifiesto anterior y restaurar la configuración privada
  anterior. Recuperar también el checkout operativo registrado si había cambiado.
- Si arrancó una migración, determinar qué llegó a aplicarse. Restaurar una imagen
  anterior exige compatibilidad comprobada con ese esquema. Si no está demostrada,
  restaurar PostgreSQL, uploads y objetos del mismo backup en volúmenes nuevos,
  usando su configuración e imágenes registradas; validar antes de cambiar el
  servicio activo. Conservar intactos los volúmenes originales.
- Comprobar los nueve servicios y repetir la aceptación de la revisión recuperada.
  Registrar el backup, los SHA de operación e imágenes y el resultado. Una copia
  cifrada verificada no sustituye el ensayo de restauración.

La actualización conserva la configuración anterior registrada en `active.env`,
ejecuta un respaldo cifrado, guarda el plan de migraciones y aplica únicamente
las migraciones. No vuelve a cargar fixtures ni restablece la cuenta inicial.
Revisar las migraciones del cambio antes de ejecutar el comando. Una migración
fallida deja los servicios de aplicación detenidos para conservar el estado de
recuperación; inspeccionar el journal antes de reintentar. Volver a una imagen no
revierte el esquema de PostgreSQL. Si una migración
no permite retroceso, restaurar la copia en volúmenes nuevos y verificarla antes
de cambiar el servicio activo. Nunca usar `down -v` ni podas globales de Docker.

El respaldo requiere `recovery.key` con permisos 600 en el directorio privado.
Comprueba que no haya tareas en curso en PostgreSQL, en ambos workers y en el
broker; detiene brevemente las escrituras y guarda
PostgreSQL, objetos, uploads, configuración y referencias de imágenes en un
archivo cifrado. Restaura el servicio al terminar, incluso si falla la copia.
Durante una actualización, el despliegue usa `leave-stopped`: una copia correcta
deja aplicación y almacenamiento detenidos hasta iniciar la nueva revisión,
evitando arrancar y volver a parar inmediatamente los workers. Si el respaldo
falla, se intenta reanudar la revisión anterior. El timer usa la reanudación
normal.
Instalar el servicio y timer de `terminology/` solo después de probar una copia
y su restauración: programa las 03:15 de Lima. Conservar una copia cifrada y la
clave fuera de la VM. Revisar el resultado en `journalctl` y el espacio disponible.
La retención predeterminada es de 14 copias `runtime-*` y solo se aplica después
de verificar una copia nueva; `TERMINOLOGY_BACKUP_KEEP` permite ajustarla (mínimo
dos). Los backups del despliegue anterior `legacy-*` se conservan. El respaldo
no comienza si quedan menos de 10 GiB libres para proteger la capacidad del host.
`active-distro-commit` identifica la revisión realmente desplegada, aunque el
checkout ya tenga una actualización pendiente. Las instalaciones anteriores a
este registro deben establecerlo a partir de su despliegue verificado antes
del siguiente respaldo.

## Consumo observado

Referencia del 5 de octubre de 2026, imágenes `e1bdda3b`, operación `f4ce800e`:
cinco muestras consecutivas durante consultas de lectura por HTTPS, sin importar
ni publicar datos. No es una prueba de carga.

| Medida | Resultado |
| --- | --- |
| Memoria del conjunto, incluido caché del cgroup | 2,18 GiB; máximo histórico del cgroup 3,03 GiB |
| Elasticsearch, según `docker stats` | aproximadamente 902 MiB; heap configurado de 512 MiB |
| Disco libre | 20,0 GiB de 38,2 GiB |
| Listado autenticado de fuentes, cinco solicitudes | HTTP 200; 0,20–0,26 s |
| Búsqueda autenticada de conceptos, cinco solicitudes | HTTP 200; 0,48–0,84 s |
| Listado sin autenticación | HTTP 403 |
| Eventos OOM del cgroup | 0 |

Conservar los límites actuales: estas muestras no miden el pico durante una
importación, indexación, publicación o backup. Antes de reducir heap o procesos,
comparar la misma carga sintética en una instalación aislada, incluyendo tiempo
hasta terminar las tareas, latencia de búsqueda, conexiones y eventos de memoria.
Medir con `docker stats --no-stream`, `docker system df` y
`systemctl show sihsalus-terminology.slice -p MemoryCurrent -p MemoryPeak`.
El máximo del cgroup pertenece a su ciclo de vida, no solo a la ventana medida.

## Traslado desde el repositorio de distribución

El checkout operativo es `/home/gidis-f1/sihsalus-terminology`. La migración desde
`/home/gidis-f1/sihsalus-distro` conserva el nombre Compose `sihsalus-terminology`,
los cinco volúmenes, los digests y el contenido del archivo privado.

1. Registrar SHA, IDs de contenedores, volúmenes y estado del timer. Conservar
   fuera de la VM el respaldo cifrado y su clave; comprobar su integridad.
2. Instalar el checkout limpio de Terminología. Copiar `.env.terminology` y
   `.env.terminology-state/` con permisos privados. Comparar los modelos Compose
   resueltos en memoria; deben ser iguales antes de cambiar referencias.
3. Configurar el entorno `terminology` en este repositorio, con Secrets,
   Variables, clave SSH restringida y política de ramas. Cambiar el comando
   forzado SSH y la unidad de backup para apuntar al nuevo checkout. No ejecutar
   `bootstrap`, `down`, ni crear volúmenes durante el traslado.
4. Registrar el nuevo SHA en `active-distro-commit`. Este nombre histórico se
   conserva para leer los journals anteriores; ahora identifica este repositorio.
   Los nuevos backups incluyen también `operations-repository`.
5. Ejecutar el workflow con `configuration=check` y `apply` sin diferencias.
   Comprobar IDs de contenedores, salud, SMTP, consultas y timer. Retirar el
   entorno de GitHub del repositorio de distribución después de verificarlo.

El checkout y los journals anteriores se conservan para recuperación. Para
revertir el traslado, restaurar la unidad de backup y el comando SSH anteriores,
y operar desde el checkout anterior con su configuración verificada. El traslado
no cambia el esquema de datos ni requiere restaurar los volúmenes.
