# SIHSALUS Terminology

Monorepositorio para adaptar Open Concept Lab (OCL) a SIHSALUS, OpenMRS y los
catálogos clínicos usados en Perú. La primera versión está destinada solo a
SIHSALUS, con edición y publicación de conceptos desde una interfaz.

| Carpeta | Proyecto de origen | Función |
| --- | --- | --- |
| [`apps/api`](apps/api) | [OpenConceptLab/oclapi2](https://github.com/OpenConceptLab/oclapi2) | API y gestión de terminologías |
| [`apps/web`](apps/web) | [OpenConceptLab/oclweb3](https://github.com/OpenConceptLab/oclweb3) | Navegador e interfaz de edición |

Ambos proyectos se importaron con el historial de su rama principal y mantienen
sus licencias y atribuciones en cada carpeta y en el pie de la interfaz.
La instalación propia usa la identidad SIHSALUS y no presenta los avisos de
suscripción de OCL Online ni enlaces a un navegador clásico que no está instalado.

Las descargas de exportaciones nativas y externas consultan primero la API
autenticada con `GET export/?noRedirect=true`, que devuelve `{"url": "..."}`
cuando el archivo está disponible. El navegador descarga esa URL firmada sin
credenciales ni cabeceras de la API. La consulta tradicional conserva su
redirección HTTP 302; la nueva opción mantiene los permisos y los estados de
exportación existentes. Actualizar la API antes del navegador al instalar este
cambio.

## Construcción y despliegue

### Correo de la instalación

El envío SMTP usa `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`
y `EMAIL_HOST_PASSWORD`. Configurar `DEFAULT_FROM_EMAIL` con un remitente
autorizado por el proveedor. `EMAIL_TIMEOUT` limita la espera de conexión y
operaciones SMTP a 20 segundos por defecto. `SERVER_EMAIL` hereda el remitente;
`COMMUNITY_EMAIL` y `REPORTS_EMAIL` heredan la cuenta SMTP si no se especifican.
No se incluyen destinatarios de OCL en estos valores predeterminados.
Los informes automáticos de errores están deshabilitados salvo que se configure
`ADMIN_EMAIL` explícitamente. Las credenciales se administran en GitHub Secrets y en el
archivo privado del servidor; para desactivar el envío se utiliza
`EMAIL_BACKEND=django.core.mail.backends.dummy.EmailBackend`.

### Imágenes

El workflow **Terminology runtime** construye imágenes inmutables de API,
navegador, PostgreSQL, Redis y Elasticsearch en GitHub Actions; comprueba el
arranque y analiza vulnerabilidades antes de aceptarlas. La API separa las
dependencias de desarrollo y de IA de las necesarias para servir terminologías.
Los modelos de IA están deshabilitados por defecto; las búsquedas textuales y
los flujos de edición y publicación usan los servicios habituales de OCL.
`CELERY_RESULT_EXPIRES` permite limitar la caché de resultados completados en
Redis (72 horas por defecto), conservando los informes de tareas persistentes
en PostgreSQL. La ventana elegida debe superar el tiempo durante el cual una
tarea coordinadora necesita los resultados de sus subtareas.

`DB_CONN_MAX_AGE` permite reutilizar conexiones PostgreSQL durante un número
limitado de segundos. Su valor predeterminado es cero. Los workers prefork pueden
usar una ventana corta para reducir el coste de abrir una conexión por tarea;
Django comprueba su salud y Celery cierra las conexiones caducadas o inutilizables
entre tareas. El proceso web conserva el valor cero. Antes de habilitar esta
opción, comprobar que PostgreSQL admite las conexiones de todos los procesos y
hilos y medir el resultado con el mismo presupuesto de CPU y memoria.

La construcción y operación se mantienen en este repositorio. El workflow
**Terminology runtime** verifica y publica imágenes; su opción manual
`configuration=check|apply` sincroniza la configuración de la instalación.
Cada ejecución completa entrega un artifact `terminology-release-<SHA>` con los
digests de las cinco imágenes y del almacenamiento, vinculados a sus escaneos.
El [procedimiento de actualización](docs/operations/terminology.md#actualización-y-recuperación)
usa ese manifiesto para preparar la configuración y comprobar los contenedores.
Publicar el artifact no despliega la versión.
La [guía de operación](docs/operations/terminology.md) cubre Compose, HTTPS,
límites, importación y backups. `gidis-terminology` descarga imágenes por digest.

Validar la operación sin iniciar contenedores:

```sh
python3 -B -m unittest discover -s tests/deploy -p 'test_*.py' -v
python3 -B tests/deploy/terminology-compose.py
```

El segundo comando requiere Docker Compose, sin daemon. Los Compose dentro de
`apps/` pertenecen a los proyectos upstream; la instalación SIHSALUS usa
`docker-compose.terminology.yml` en la raíz.

Consulta [UPSTREAM.md](UPSTREAM.md) para las revisiones importadas y el proceso
de actualización. Los catálogos de terceros, incluidos los subconjuntos de
SNOMED CT, requieren sus propios permisos de uso y distribución.
