# Proyectos de origen

Los dos proyectos se importaron con `git subtree add` sin `--squash`. Sus
commits de origen son antepasados del historial de este monorepositorio. Las
licencias y atribuciones originales permanecen dentro de cada aplicación.

| Carpeta | Remoto | Rama | Revisión inicial |
| --- | --- | --- | --- |
| `apps/api` | `https://github.com/OpenConceptLab/oclapi2.git` | `master` | `526f115c541f3b0410bb88eac5ee55d485042298` |
| `apps/web` | `https://github.com/OpenConceptLab/oclweb3.git` | `main` | `2b831d5cd1824cb84d90dab3652e25aadda072df` |

Para actualizar una aplicación, configura sus remotos y trae su rama antes de
integrar el nuevo historial:

```sh
git remote add upstream-api https://github.com/OpenConceptLab/oclapi2.git
git remote add upstream-web https://github.com/OpenConceptLab/oclweb3.git
git fetch upstream-api master
git fetch upstream-web main
git subtree pull --prefix=apps/api upstream-api master
git subtree pull --prefix=apps/web upstream-web main
```

Los comandos `remote add` se ejecutan solo si los remotos aún no existen. Revisa
las diferencias y las licencias antes de cada actualización. Conserva los
archivos de atribución que acompañan al código de origen.

## Conversión de descripciones de ocldev

El 5 de octubre de 2026 se verificó que `ocldev==0.2.3`, la última versión
publicada consultada, y el archivo del mismo conversor en `master` iteran una
lista vacía al convertir las descripciones. Un ZIP puede informar una
importación satisfactoria y perder todas sus descripciones.

`apps/api/core/importers/export_converter.py` conserva la conversión de OCL y
corrige únicamente esa lista. Retiene texto, idioma, tipo, UUID externo y estado
de retirada; descarta los identificadores internos y checksums generados por el
servidor de origen, como hace el conversor con los nombres. La corrección vive
en el parser de la API y no modifica los catálogos originales.

Responsable: mantenimiento de SIHSALUS Terminología. Seguimiento: PR #1 de este
monorepositorio. Retirar la adaptación al fijar una versión de ocldev que
conserve las descripciones y comprobar nuevamente el recorrido ZIP → API →
exportación. Actualizar solo la dependencia no resuelve el fallo en la versión
consultada; copiar el conversor completo duplicaría lógica ajena a este cambio.

## Tipos de nombres en catálogos importados

La revisión inicial de la API acepta `Index-Term` en la validación de tipos de
nombres, pero su lista compartida de términos de índice omite esa representación.
Esto hace que la validación de unicidad trate algunos términos de búsqueda como
nombres completos y rechace categorías válidas al importar procedimientos.
Se añade esa representación a `LOCALES_SEARCH_INDEX_TERM`, sin cambiar nombres,
UUID ni las reglas que rechazan nombres completos o preferidos duplicados.

Responsable: mantenimiento de SIHSALUS Terminología. Seguimiento: PR #1.
Revisar la adaptación cuando upstream unifique las representaciones aceptadas
por la validación de tipos y por los consumidores de esa constante.

## Conexiones de base de datos en workers

La configuración importada no expone `CONN_MAX_AGE`. Con Django 5.2.17 y Celery
5.4.0, el cierre por defecto hace que cada tarea breve vuelva a abrir su conexión
PostgreSQL. Durante la migración, una muestra de cinco lecturas por modalidad
registró medianas de 493 ms con conexiones nuevas y 23 ms al reutilizarlas;
esta muestra identifica un coste y no demuestra el rendimiento de una cola
completa.

Se expone `DB_CONN_MAX_AGE` con valor predeterminado cero y se habilita la
comprobación de salud nativa de Django. El despliegue puede limitar la
reutilización a los workers prefork y conservar los límites de procesos,
conexiones, CPU y memoria. La reutilización usa el ciclo nativo de Django y
Celery. Referencia: [conexiones de Django 5.2](https://docs.djangoproject.com/en/5.2/ref/databases/#persistent-connections).

La tarea heredada `vacuum_and_analyze_db` modifica directamente el aislamiento
del driver. Se comprobó que al restaurar el valor original deja su autocommit
en `False` mientras Django conserva `True`. Antes de reutilizar conexiones,
la tarea pasa a usar `set_autocommit` de Django y restaura el valor anterior en
un bloque `finally`, también si el mantenimiento falla. Las transacciones
gestionadas conservan la protección nativa que impide cambiar su autocommit.

Responsable: mantenimiento de SIHSALUS Terminología. Seguimiento: PR #1.
Revisar esta configuración cuando upstream exponga una opción equivalente o
cambie el ciclo de conexiones del worker; conservar la verificación de
caducidad, recuperación tras desconexión y consumo antes de adoptarlo.
