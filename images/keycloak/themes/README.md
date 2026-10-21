# Tema SIHSALUS para Keycloak

`sihsalus/login` hereda `keycloak.v2` de Keycloak 26.8.1. Conserva sus
plantillas, scripts, accesibilidad y formularios; carga primero `css/styles.css`
del padre y después `css/sihsalus.css`. El color primario `#4836ff` coincide con
`apps/web/src/common/colors.jsx`. El fondo usa gradientes CSS, sin descargas
externas, imágenes ni dependencias. La variante es clara (`darkMode=false`).

`sihsalus/email` hereda `keycloak`. Solo reemplaza los mensajes en español de
verificación, recuperación y acciones de cuenta. El parámetro `{3}` de los dos
primeros y `{4}` del último ya incluyen la unidad de tiempo; añadir «minutos»
duplicaría la unidad. Los enlaces `{0}`, el nombre de la instalación `{2}` y
la lista de acciones `{3}` se conservan.

El Dockerfile incluye estos recursos en `/opt/keycloak/themes`. El realm inicial
y `keycloak-setup.py reconcile` seleccionan `sihsalus` como `loginTheme` y
`emailTheme`; un realm existente se actualiza sin volver a importar identidades.

## Comprobación en la imagen construida

1. Abrir el login desde la web y comprobar que el HTML incluye, en este orden,
   `/login/sihsalus/css/styles.css` y `/login/sihsalus/css/sihsalus.css`.
   Ambos deben responder 200. Los recursos heredados se resuelven bajo el nombre
   del tema hijo mediante el proveedor nativo de Keycloak.
2. Comprobar `body#keycloak-bg`, `.pf-v5-c-login__container` y
   `.pf-v5-c-login__main`, que pertenecen a la plantilla `keycloak.v2` 26.8.1.
   El fondo calculado debe contener `radial-gradient`; el botón principal debe
   tener el color `rgb(72, 54, 255)`. Comprobar también con preferencia de modo
   oscuro: esta variante mantiene su tarjeta clara.
3. Revisar login, registro, recuperación, verificación y creación de contraseña
   a 390 px y a 1440 px, con zoom al 200 % y navegación por teclado. No debe
   existir desplazamiento horizontal ni quedar oculto el botón de continuar.
4. En la prueba nativa de CI, usar el SMTP sintético existente para comprobar
   texto y HTML de verificación/recuperación: una única unidad de tiempo y
   enlaces válidos. Una captura con CSS aplicado sobre HTML público confirma
   presentación, pero no sustituye esta comprobación del servidor y del correo.

## Reversión a una imagen sin el tema

La selección `loginTheme`/`emailTheme` queda persistida en la base de Keycloak.
Antes de volver a una imagen anterior que no contiene `sihsalus`, guardar una
copia privada de esos dos valores actuales junto con el SHA y los digests de
origen y destino, y obtener aprobación de esa reversión concreta.

Con la reversión aprobada y antes de retirar la imagen que contiene el tema,
usar la API administrativa nativa por el acceso interno para actualizar
`PUT /auth/admin/realms/ocl` con este cuerpo acotado:

```json
{"loginTheme": "keycloak.v2", "emailTheme": "keycloak"}
```

Confirmar ambos valores mediante `GET` del mismo endpoint y continuar con el
procedimiento aprobado para la imagen anterior. Usar los scripts de la revisión
de destino: el `reconcile` de esta versión volvería a seleccionar `sihsalus`.
Comprobar después los formularios, sus recursos y los flujos de acceso y correo
previstos en la aceptación. Esta actualización conserva las identidades y
credenciales del realm.

El código oficial de [DefaultThemeManager en 26.8.1](https://github.com/keycloak/keycloak/blob/26.8.1/services/src/main/java/org/keycloak/theme/DefaultThemeManager.java#L73-L90)
intenta cargar el tema predeterminado si no encuentra el solicitado. Esa ruta no
se ha ensayado en la imagen anterior y no acredita continuidad del acceso ni
de todos los recursos y correos. La reversión descrita configura los temas
incluidos explícitamente.

## Origen y mantenimiento

Keycloak y sus temas originales son del proyecto [Keycloak](https://www.keycloak.org/)
y se distribuyen bajo [Apache License 2.0](https://github.com/keycloak/keycloak/blob/26.8.1/LICENSE.txt).
Los recursos upstream se heredan de la imagen oficial, sin copiar ni modificar
sus plantillas. Consultar la [guía oficial de temas](https://www.keycloak.org/ui-customization/themes)
y la [plantilla 26.8.1](https://github.com/keycloak/keycloak/blob/26.8.1/themes/src/main/resources/theme/keycloak.v2/login/template.ftl)
al actualizar la versión.
