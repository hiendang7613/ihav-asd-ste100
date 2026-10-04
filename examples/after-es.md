**Agents-Zone**
- `4:12 PM` la prueba de login falla con el cliente nuevo => leer `src/auth.ts`
- `4:15 PM` `verifyToken` lee una cabecera propia => cambiarlo para leer `Authorization`
- `4:18 PM` comprobar la corrección => ejecutar `npm test`

**Result-Zone**
- **Causa:** `verifyToken` en `src/auth.ts:42` leía el token de una cabecera propia. El cliente nuevo envía `Authorization: Bearer <token>`.
- **Corrección:** `verifyToken` ahora lee la cabecera `Authorization`.

**Admin-Zone**

**Conclusion:** La prueba de login ya pasa; una prueba de pagos sigue fallando y no revisé la causa.

0. **Goals:**
   - **L1.** Todos los clientes pueden iniciar sesión.
   - **G1.** Corregir el login del cliente nuevo -> L1 `#######---` 2/3
1. **Done:**
   - **Login:** `verifyToken` lee la cabecera correcta; `npm test` ejecutó 214 pruebas y pasan 213.
2. **Doing:**
3. **Todos:**
   - **Prueba de pagos:** buscar por qué falla `payment.spec.ts:88`; no cambié el código de pagos.
4. **Pending:**
5. **Quests:**
   - **Q1.** ¿Reviso `payment.spec.ts:88` antes de fusionar este cambio?
     - `<a>` Sí, ahora.
     - (b) Después de fusionar.
6. **Risks:**
   - **R1.** `jsonwebtoken` 8.5.1 es anterior a la versión de seguridad 9.0.0.
     - `<a>` actualizarlo en un cambio aparte | (b) omitir | (c) más tarde
7. **Ideas:**
   - **I1.** Añadir una prueba que envíe `Authorization: Bearer <token>`, para que este error no vuelva.
     - `<a>` planificarlo | (b) omitir | (c) más tarde
