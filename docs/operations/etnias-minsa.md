# Etnias: códigos MINSA y catálogo local

Revisión: 21 de octubre de 2026. Seguimiento: [sihsalus/sihsalus#400](https://github.com/sihsalus/sihsalus/issues/400).

Estado: versiones `etnias/2026-10-21-01` y `MINSA-ETNIAS/2026-10-21-01`
publicadas en el OCL local por solicitud del usuario. La candidata
[content `1.25.41`](https://github.com/sihsalus/sihsalus-content/pull/277)
incorpora el export; la revisión institucional y el despliegue siguen
pendientes.

## Identidad y mecanismo

`SIHSALUS/etnias` conserva las identidades clínicas de OpenMRS. Su `id` es
interno: Aimara sigue siendo `etnias:4`, UUID
`c79ac7a1-1cef-4524-bbc4-bb21fd5d5331`. Su código MINSA es `2`.

`SIHSALUS/MINSA-ETNIAS` contiene una copia local de referencia de los 60 códigos
HIS publicados por MINSA. El origen y la edición figuran en sus metadatos;
la curación de esta copia corresponde a SIHSALUS. Sus códigos son cadenas.
Los mappings `SAME-AS` de `etnias` apuntan al concepto oficial de esa fuente.
Los mappings nuevos se identifican como `MINSA-HIS-<código>`. El código está
vinculado a la edición HIS citada; cada integración debe confirmar la tabla
que exige su propio contrato.

OCL ya indexa códigos de mappings y sinónimos nativos. Esta corrección
reutiliza esos mecanismos y las operaciones nativas de fuentes, conceptos,
nombres y mappings. El catálogo no necesita un índice propio ni otra tabla
manual de equivalencias en el frontend. No se cambian los identificadores
internos para hacerlos coincidir con MINSA.

## Fuentes y alcance

La tabla de códigos procede del **Anexo 1, página PDF 55**, de MINSA,
*Atención Materna*, segunda edición, marzo de 2023, disponible en el
[servidor oficial de GERESA Arequipa](https://saludarequipa.gob.pe/HIS/Manuales_y_Sintaxis/2023/Manual-atenci%C3%B3n_materna-2023.pdf).
El documento identifica también su edición nacional como
[MINSA/7499.pdf](https://bvs.minsa.gob.pe/local/MINSA/7499.pdf).
SHA-256 de la copia consultada: `e3397b4671ff2962fd9494ece2919f514e95cf659cce0b52a893f9fe47bf141c`.

Las cinco denominaciones alternativas se contrastaron con las páginas PDF 8–9
del [manual de pueblos indígenas publicado por MINSA en 2022](https://www.gob.pe/institucion/minsa/informes-publicaciones/2727239-manual-de-registro-y-codificacion-segun-grupo-etnico-de-la-actividades-de-la-direccion-de-pueblos-indigenas-u-originarios).
SHA-256 de su PDF: `762e026891723a2964b11c83605dc4117fe91349a5c2f9ff0162a5a3e054f975`.
Ese manual omite Secoya y numera Resígaro como 42. Para los códigos se utiliza
la tabla completa de 2023: **41 Resígaro, 42 Secoya**.

Estas referencias documentan la edición utilizada. La aceptación del responsable
de terminología y codificación HIS del hospital sigue pendiente, incluida la
confirmación de la edición requerida por cada integración.

## Correspondencia observada

La tabla es una fotografía para revisión. La fuente operativa es OCL.

| Código MINSA | Denominación oficial | ID clínico en `SIHSALUS/etnias` |
| --- | --- | --- |
| 1 | ACHUAR | 3 |
| 2 | AIMARA | 4 |
| 3 | AMAHUACA | 5 |
| 4 | ARABELA | 6 |
| 5 | ASHANINKA | Sin concepto clínico equivalente |
| 6 | ASHENINKA | 7 |
| 7 | AWAJÚN | 8 |
| 8 | BORA | 9 |
| 9 | CAPANAHUA | 10 |
| 10 | CASHINAHUA | 11 |
| 11 | CHAMICURO | 12 |
| 12 | CHAPRA | 13 |
| 13 | CHITONAHUA | 14 |
| 14 | ESE EJA | 15 |
| 15 | HARAKBUT | 16 |
| 16 | IKITU | 17 |
| 17 | IÑAPARI | 18 |
| 18 | ISCONAHUA | 19 |
| 19 | JAQARU | 20 |
| 20 | JÍBARO | 21 |
| 21 | KAKATAIBO | 22 |
| 22 | KAKINTE | 23 |
| 23 | KANDOZI | 24 |
| 24 | KICHWA | 25 |
| 25 | KUKAMA KUKAMIRIA | 26 |
| 26 | MADIJA | 27 |
| 27 | MAIJUNA | 28 |
| 28 | MARINAHUA | 29 |
| 29 | MASHCO PIRO | 30 |
| 30 | MASTANAHUA | 31 |
| 31 | MATSÉS | 32 |
| 32 | MATSIGENKA | 33 |
| 33 | MUNICHE | 34 |
| 34 | MURUI-MUINANI | 35 |
| 35 | NAHUA | 36 |
| 36 | NANTI | 37 |
| 37 | NOMATSIGENGA | 38 |
| 38 | OCAINA | 39 |
| 39 | OMAGUA | 40 |
| 40 | QUECHUAS | 41 |
| 41 | RESÍGARO | 42 |
| 42 | SECOYA | 43 |
| 43 | SHARANAHUA | 44 |
| 44 | SHAWI | 45 |
| 45 | SHIPIBO-KONIBO | 46 |
| 46 | SHIWILU | 47 |
| 47 | TIKUNA | 48 |
| 48 | URARINA | 49 |
| 49 | URO | 50 |
| 50 | VACACOCHA | 51 |
| 51 | WAMPIS | 52 |
| 52 | YAGUA | 53 |
| 53 | YAMINAHUA | 54 |
| 54 | YANESHA | 55 |
| 55 | YINE | 56 |
| 56 | AFROPERUANO | 57 |
| 57 | BLANCO | 58 |
| 58 | MESTIZO | 59 |
| 59 | ASIATICODESCENDIENTE | 60 |
| 60 | OTRO | Sin concepto clínico equivalente |

Hay 58 correspondencias directas entre las denominaciones y los conceptos
clínicos existentes. Ashaninka (`5`) y Otro (`60`) están en la referencia MINSA;
su incorporación como opciones clínicas y respuestas del formulario requiere
una decisión del dominio. No se añaden automáticamente a la pregunta Etnia.

Los agrupadores existentes Andino (`2`), Afro Descendiente (`61`) e Indígena
Amazónico (`62`) se conservan sin mapping MINSA. No se demostró una equivalencia
única para ellos; requieren revisión clínica. Una integración debe presentar
esa falta de equivalencia y solicitar su resolución, sin inferir códigos por
nombre, posición o cercanía numérica.

## Sinónimos de búsqueda

Se conservan las denominaciones preferidas y se añaden estas variantes como
nombres sin tipo (`name_type: null`), idioma `es`, sin preferencia de idioma:

| Concepto clínico | Variante |
| --- | --- |
| Awajún (`8`) | Aguaruna |
| Shawi (`45`) | Chayawita |
| Tikuna (`48`) | Ticuna |
| Yanesha (`55`) | Amuesha |
| Shiwilu (`47`) | Jebero |

La búsqueda ayuda a localizar la opción. La pertenencia étnica se registra
mediante la identificación declarada por la persona; encontrar un sinónimo no
autoriza una asignación automática.

## Consulta por código

Un código se interpreta junto con su fuente. Para resolver MINSA `2` hacia la
identidad clínica, consultar el mapping exacto de `etnias`:

```http
GET /orgs/SIHSALUS/sources/etnias/mappings/MINSA-HIS-2/
```

El mapping `SAME-AS` devuelve como origen clínico `SIHSALUS/etnias:4`.
Comprobar también su destino: fuente `MINSA-ETNIAS`, código `2`. La definición
oficial se consulta en `/orgs/SIHSALUS/sources/MINSA-ETNIAS/concepts/2/`.
Para leer el código de una identidad clínica existente:

```http
GET /orgs/SIHSALUS/sources/etnias/concepts/4/?includeMappings=true&targetRepoUrls=/orgs/SIHSALUS/sources/MINSA-ETNIAS/
```

Las búsquedas textuales ordinarias también incluyen IDs internos. Consultar
`q=4` no establece que se trate del código MINSA `4`; la resolución exacta usa
el recurso de referencia o el mapping identificado por fuente y código.
La consulta inversa con `includeInverseMappings` en la referencia no devuelve
estos mappings entre fuentes en la versión instalada; usar el recurso exacto
mostrado arriba.

## Validación y promoción

La lectura posterior a los cambios y las consultas a la API verificaron:

- Los 60 códigos de referencia coinciden con la tabla oficial consultada;
  58 tienen un mapping `SAME-AS` hacia la identidad clínica correspondiente.
- Se conservan los 62 IDs y UUID clínicos, las denominaciones originales y las
  identidades, tipos y extremos de los 64 mappings anteriores. La nueva versión
  tiene 122 mappings.
- Cada uno de los cinco sinónimos devuelve la identidad clínica esperada.
  El índice nativo encuentra Aimara al buscar el código mapeado `2`; esa misma
  búsqueda numérica también devuelve el ID interno `2` y no es una resolución
  exacta del código oficial.
- Las consultas exactas de códigos `2`, `41`, `42`, `56` y `58` devuelven los
  mappings esperados. El código desconocido `99999` devuelve HTTP 404.
- La versión publicada `2026-06-30` conserva sus 62 conceptos, nombres y
  64 mappings. Ambas fuentes tienen ahora la versión publicada `2026-10-21-01`.

Antes de publicar se registró en OCL el `sort_weight` de las 62 respuestas
`Q-AND-A`: del `1` al `62`, contrastados por UUID y destino mediante consultas
de solo lectura en DEV y QLTY. El export anterior omitía esos pesos; el
importador podía convertirlos en `NULL` al actualizar. La nueva versión conserva
el orden persistido mediante metadata explícita en la fuente canónica.

Se descargaron y compararon los exports nativos publicados con los recursos
verificados, incluidos nombres, UUID, relaciones y pesos:

| Fuente y versión | Conceptos | Mappings | SHA-256 del ZIP nativo |
| --- | --- | --- | --- |
| `etnias/2026-10-21-01` | 62 | 122 | `6c5728c4e521159b371aafb3bbd65d772176ebd69b70a57ce26716ec82ec5c14` |
| `MINSA-ETNIAS/2026-10-21-01` | 60 | 0 | `5bec1789937bee9bd36419d52eb7d6b03c56bac2fd6008fa4bf9e58ee7f08d68` |

Se utilizaron operaciones nativas de la API y su índice existente. El cambio
en Git documenta el catálogo y su consumo; no introduce código de aplicación,
loaders, SQL ni un índice adicional.

La candidata content `1.25.41` actualiza únicamente los dos ZIP de etnias. El loader crea los
términos MINSA y sus equivalencias nativas; los 60 conceptos de referencia no se
añaden como otros conceptos clínicos. DEV/QLTY aún consumen content `1.25.40`.
El [pendiente de transición de OCL](https://github.com/sihsalus/sihsalus-content/blob/main/docs/audits/2026-10-16-ocl-institutional-transition.md)
conserva los requisitos de orden de respuestas y conjuntos.

La adopción en OpenMRS requiere revisión del catálogo y evidencia de instalación
nueva, actualización y reinicio preservando UUID, observaciones y pesos.
Frontend y consumidores deben usar el mapping para los códigos oficiales.
Los casos de aceptación incluyen
buscar por código y sinónimo, guardar/reabrir una selección existente y hacer
visible una identidad sin equivalencia. La aceptación clínica e integrada
requiere evidencia propia; el issue #400 mantiene ese alcance pendiente.

El respaldo privado conserva los recursos anteriores, los documentos fuente,
el plan de peticiones y cada respuesta de la API. Para recuperar una edición,
usar las versiones y operaciones nativas de OCL: retirar únicamente los mappings
y sinónimos añadidos tras revisar su uso, preservando la historia y las
identidades clínicas. No se usan SQL directo ni borrados de catálogos.
