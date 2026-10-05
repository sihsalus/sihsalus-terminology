# SIHSALUS Terminology

Monorepositorio para adaptar Open Concept Lab (OCL) a SIHSALUS, OpenMRS y los
catálogos clínicos usados en Perú. La primera versión está destinada solo a
SIHSALUS e incluirá edición y publicación de conceptos desde una interfaz.

| Carpeta | Proyecto de origen | Función |
| --- | --- | --- |
| [`apps/api`](apps/api) | [OpenConceptLab/oclapi2](https://github.com/OpenConceptLab/oclapi2) | API y gestión de terminologías |
| [`apps/web`](apps/web) | [OpenConceptLab/oclweb3](https://github.com/OpenConceptLab/oclweb3) | Navegador e interfaz de edición |

Ambos proyectos se importaron con el historial de su rama principal y mantienen
sus licencias y atribuciones en cada carpeta. La composición en un solo
repositorio no reduce por sí sola los requisitos de memoria o disco del sistema:
la simplificación y la adaptación a Perú serán cambios posteriores. No hay un
despliegue de producción ni datos de pacientes en este repositorio.

Consulta [UPSTREAM.md](UPSTREAM.md) para las revisiones importadas y el proceso
de actualización. Los catálogos de terceros, incluidos los subconjuntos de
SNOMED CT, requieren sus propios permisos de uso y distribución.
