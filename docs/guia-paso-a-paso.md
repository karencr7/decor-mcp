# Guía paso a paso (Windows) · Entregables del Módulo 3

Checklist para completar y evidenciar los 10 entregables de la actividad. Marca cada paso al terminarlo.

## A. Ejecutar el proyecto (entregables 2, 3, 6 y 8)

- [ ] Descomprimir `decor-mcp.zip` en una carpeta sin espacios raros, por ejemplo `C:\proyectos\decor-mcp`.
- [ ] Abrir la carpeta en VS Code → menú **Terminal → New Terminal**.
- [ ] `copy .env.example .env` y luego `notepad .env`: cambiar las 7 claves y tokens (solo letras y números, todos distintos). Guardar.
- [ ] Docker Desktop abierto con **Engine running**.
- [ ] `docker compose up --build` y esperar `Application startup complete`.
- [ ] 📸 Captura: terminal con los dos contenedores arriba (`decor-db` y `decor-mcp`).
- [ ] 📸 Captura: http://localhost:8000/api/salud mostrando `"base_datos":"ok"`.
- [ ] 📸 Captura: Docker Desktop → *Containers* con `decor-mcp` corriendo.

## B. Documentación y pruebas de la API (entregables 3 y 4)

- [ ] Abrir http://localhost:8000/docs → **Authorize** → pegar `DECOR_TOKEN_COMERCIAL`.
- [ ] Probar `POST /api/consultas/analitica` con el ejemplo → 📸 respuesta 200.
- [ ] Probar `POST /api/consultas/detalle` con `{"sql": "DELETE FROM zventas"}` → 📸 respuesta 403.
- [ ] Postman → **Import** → `postman/Decor_MCP.postman_collection.json`.
- [ ] En la colección → pestaña **Variables** → pegar los 3 tokens en *Current value* → **Save**.
- [ ] Clic derecho en la colección → **Run collection** → **Run** → 📸 resultado con todas las pruebas en verde.

## C. Persistencia (entregable 3)

- [ ] MySQL Workbench no se usa (el proyecto usa PostgreSQL). Para ver los datos: en la terminal
      `docker exec -it decor-db psql -U decor_admin -d decor`
- [ ] Dentro de psql: `SELECT fecha, correo, canal, herramienta, resultado FROM mcp.auditoria ORDER BY id DESC LIMIT 10;`
      → 📸 la auditoría guardada en la base. Salir con `\q`.

## D. Integración con IA (entregable 7)

- [ ] VS Code → abrir `.vscode/mcp.json` → clic en **Start** sobre `decor-supabases` → pegar el token comercial.
- [ ] Copilot Chat → modo **Agent** → 🛠 verificar las 8 herramientas → 📸.
- [ ] Preguntar: *¿Cuántas facturas emitió cada oficina en septiembre de 2026?* → permitir la herramienta → 📸 respuesta.
- [ ] Preguntar: *Dame el correo de los clientes* → 📸 Copilot informa que la tabla no está autorizada.
- [ ] Con el token admin: `GET /api/auditoria` → 📸 llamadas con canal `MCP`.

## E. Git, rama y Pull Request (entregables 1 y 5)

**Karen (dueña del repositorio):**
- [ ] GitHub → **New repository** → nombre `decor-mcp` → **Private** → sin README → **Create**.
- [ ] **Settings → Collaborators → Add people** → agregar el usuario de GitHub de María José (y del profesor si lo pide).
- [ ] En la terminal de VS Code (carpeta del proyecto), commits por partes:

```powershell
git init
git branch -M main
git add database
git commit -m "Agregar esquema PostgreSQL, datos ficticios y roles de solo lectura"
git add app/dominio app/aplicacion app/__init__.py
git commit -m "Implementar núcleo hexagonal: política de acceso y caso de uso Ejecutar consulta"
git add app
git commit -m "Agregar adaptadores MCP, REST y PostgreSQL"
git add tests postman requirements-dev.txt
git commit -m "Agregar pruebas pytest y colección Postman"
git add .
git status
git commit -m "Agregar Docker, configuración segura y documentación"
git remote add origin https://github.com/karencr7/decor-mcp.git
git push -u origin main
```
- [ ] Antes del último commit, confirmar en `git status` que **NO** aparece `.env`.

**María José (colaboradora):**
- [ ] Aceptar la invitación que llega a su correo.
- [ ] Clonar: `git clone https://github.com/karencr7/decor-mcp.git` y `cd decor-mcp`.
- [ ] Configurar su autoría: `git config user.name "María José Vargas"` y `git config user.email "<su correo de GitHub>"`.
- [ ] Crear rama: `git switch -c feature/uso-de-ia`.
- [ ] Completar `docs/uso-de-ia.md` con lo que hicieron (qué aceptaron y corrigieron de la IA).
- [ ] `git add docs/uso-de-ia.md` → `git commit -m "Documentar uso responsable de IA"` → `git push -u origin feature/uso-de-ia`.
- [ ] En GitHub: **Compare & pull request** → base `main` ← `feature/uso-de-ia` → describir el cambio → **Create pull request**.

**Karen:**
- [ ] Revisar el PR (**Files changed**), dejar un comentario y **Merge pull request** → 📸 PR fusionado.
- [ ] En su PC: `git switch main` y `git pull`.
- [ ] 📸 **Insights → Contributors** o el historial de commits mostrando a las dos autoras.

## F. Video y PDF (entregables 9 y 10)

- [ ] Video (3–5 min): `docker compose up` → `/api/salud` → Swagger (200 y 403) → Postman *Run collection* → Copilot respondiendo con datos → auditoría.
- [ ] Subir el video (YouTube *no listado* o Drive con enlace) y copiar el enlace.
- [ ] Armar el PDF con portada, MVP, tecnologías, enlaces (repo, PR, video) y las capturas 📸.
