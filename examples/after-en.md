**Agents-Zone**
- `4:12 PM` the login test fails for the new client => read `src/auth.ts`
- `4:15 PM` `verifyToken` reads a custom header => changed it to read `Authorization`
- `4:18 PM` check the fix => ran `npm test`

**Result-Zone**
- **Cause:** `verifyToken` in `src/auth.ts:42` read the token from a custom header. The new client sends `Authorization: Bearer <token>`.
- **Fix:** `verifyToken` now reads the `Authorization` header.

**Admin-Zone**

**Conclusion:** The login test passes now; one payment test still fails, and I did not check why.

0. **Goals:**
   - **L1.** Every client can log in.
   - **G1.** Fix login for the new client -> L1 `#######---` 2/3
1. **Done:**
   - **Login fix:** `verifyToken` reads the right header; `npm test` ran 214 tests and 213 pass.
2. **Doing:**
3. **Todos:**
   - **Payment test:** find why `payment.spec.ts:88` fails; I did not change payment code.
4. **Pending:**
5. **Quests:**
   - **Q1.** Check `payment.spec.ts:88` before this change is merged?
     - `<a>` Yes, check it now.
     - (b) After the merge.
6. **Risks:**
   - **R1.** `jsonwebtoken` 8.5.1 is older than the 9.0.0 security release.
     - `<a>` update it in a separate change | (b) skip | (c) later
7. **Ideas:**
   - **I1.** Add a test that sends `Authorization: Bearer <token>`, so this bug cannot come back.
     - `<a>` plan it | (b) skip | (c) later
