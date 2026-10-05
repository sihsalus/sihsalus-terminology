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

## Construcción y despliegue

El workflow **Terminology runtime** construye imágenes inmutables de API,
navegador, PostgreSQL, Redis y Elasticsearch en GitHub Actions; comprueba el
arranque y analiza vulnerabilidades antes de aceptarlas. La API separa las
dependencias de desarrollo y de IA de las necesarias para servir terminologías.
Los modelos de IA están deshabilitados por defecto; las búsquedas textuales y
los flujos de edición y publicación usan los servicios habituales de OCL.

La operación se mantiene en
[`sihsalus`](https://github.com/sihsalus/sihsalus/blob/feature/terminology-deployment/docs/operations/terminology.md):
Compose, límites de recursos, HTTPS, credenciales privadas, importación y
backups. `gidis-terminology` descarga imágenes por digest y no realiza builds.
La aceptación del despliegue requiere comprobar edición y publicación desde
el navegador, reconciliar los catálogos y restaurar un backup en volúmenes
aislados. No hay datos de pacientes ni credenciales en este repositorio.

Consulta [UPSTREAM.md](UPSTREAM.md) para las revisiones importadas y el proceso
de actualización. Los catálogos de terceros, incluidos los subconjuntos de
SNOMED CT, requieren sus propios permisos de uso y distribución.
