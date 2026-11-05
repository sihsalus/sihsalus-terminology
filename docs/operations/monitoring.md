# Monitoreo externo de terminología

Candidato preparado el 4 de noviembre de 2026. **No está activo hasta aprobar e
integrar este cambio en main.** La integración activa la agenda y el primer aviso.
No despliega imágenes ni cambia el servidor. El workflow runtime existente
también se ejecuta al integrar en main y publica sus artifacts habituales.

## Alcance y avisos

GitHub Actions ejecuta monitor.yml a los minutos 7, 22, 37 y 52 de cada hora,
desde fuera de la VM. Cada comprobación reintenta tres veces con diez segundos
entre intentos. Comprueba:

- Entrada web y HTTPS.
- Salud real de base de datos, Elasticsearch y ocho workers de OCL, leyendo JSON
  además del estado HTTP; Redis mediante su endpoint nativo.
- Emisor OIDC y claves públicas del inicio de sesión.
- Certificados válidos, con al menos catorce días antes del vencimiento.
- Conexión SMTP, STARTTLS y autenticación, sin enviar correos de prueba periódicos.

Flower está ausente por diseño en esta instalación y no es un criterio de salud.
El monitor no lee conceptos, datos clínicos, usuarios, sesiones ni enlaces de
verificación. Solo usa la contraseña SMTP existente del entorno terminology;
no necesita SSH ni credenciales administrativas de OCL o Keycloak.

Los avisos van exclusivamente a la dirección revisada de
TERMINOLOGY_MONITOR_RECIPIENT, variable del entorno terminology, desde la cuenta
SMTP existente. Se envían al inicio, al cambiar entre correcto e incidencia,
y al reintentar un aviso que no se pudo enviar. Una incidencia persistente con
aviso aceptado no genera un correo cada quince minutos. El historial nativo
de ejecuciones y sus jobs conserva el estado; no se añaden bases de datos,
issues ni cachés de estado.

Ejemplo de asunto: [SIHSALUS Terminología] INCIDENCIA.
El cuerpo identifica cada comprobación, su resultado y duración total con
reintentos, además del portal y el enlace a la ejecución. El mismo detalle
queda visible en el resumen nativo de GitHub Actions.
No incluye destinatarios de registros, trazas SMTP ni cuerpos de la API.

## Verificación y activación

Antes de integrar, ejecutar la suite de operaciones y el diagnóstico HTTPS:

    python3 -B -m unittest discover -s tests/deploy -p 'test_*.py' -v
    TERMINOLOGY_HOST=sih-terminology.inf.pucp.edu.pe \
    TERMINOLOGY_API_HOST=api.gidis-terminology.duckdns.org \
      python3 -B scripts/terminology/monitor.py probe --skip-smtp

El diagnóstico anterior es de solo lectura y no envía mensajes.
Antes de activar, configurar TERMINOLOGY_MONITOR_RECIPIENT con la dirección
exacta autorizada por el usuario. El workflow usa los valores y la contraseña SMTP ya registrados en el entorno
terminology; una prueba local no verifica que ese secreto remoto siga vigente.
La primera ejecución aprobada debe verificarlo y confirmar recepción del aviso
en el grupo. Los nombres de las variables coinciden con los del workflow runtime.
El entorno admite main; no abrir sus secretos a ramas no revisadas para probar.

Para detener los avisos, deshabilitar Terminology availability en Actions.
Conservar historial para investigar; deshabilitar no cambia la aplicación.

## Límites operativos

La agenda de GitHub puede retrasarse; quince minutos es la frecuencia nominal,
no un SLA. En repositorios públicos, GitHub desactiva las agendas tras sesenta
días sin actividad. Revisar periódicamente la última ejecución; este monitor
no puede detectar su propia ausencia cuando GitHub no lo ejecuta.

Si falla Gmail/SMTP, ese mismo canal no podrá enviar el aviso: el fallo queda
visible en GitHub Actions y se reintenta en la siguiente ejecución. Para garantizar
avisos de una avería del correo hace falta un segundo canal independiente,
no configurado en este candidato.

SMTP aceptado no prueba recepción en bandeja de entrada, ni ausencia de spam.
Tampoco se prueba una importación real, permisos de edición, entrega de correos
de Keycloak o la corrección clínica de un catálogo. La autenticación SMTP comprueba
las credenciales compartidas, no cada envío realizado por la aplicación.
