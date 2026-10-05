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
