**Agents-Zone**
- `4:12 PM` the login test fails for the new client => read `src/auth.ts`
- `4:15 PM` `verifyToken` reads a custom header => changed it to read `Authorization`
- `4:18 PM` check the fix => ran `npm test`
- `4:21 PM` the fix needs staging => deployed to staging

**Result-Zone**
- **Cause:** `verifyToken` in `src/auth.ts:42` read a custom header. The new client sends `Authorization: Bearer <token>`.
- **Fix:** `verifyToken` now reads the `Authorization` header.

**Admin-Zone**

**Conclusion:** Login is fixed and on staging; one payment test still fails, cause not checked.

0. **Goals:**
   - **L1.** Every client can log in.
   - **G1.** Fix login for the new client -> L1 `#######---` 2/3
1. **Done:**
   - **Login fix:** `npm test` ran 214 tests and 213 pass; staging is deployed.
2. **Doing:**
3. **Todos:**
   - **Payment test:** find why `payment.spec.ts:88` fails; I did not change payment code.
4. **Pending:**
5. **Quests:**
   - **Q1.** Approve: deploy the login fix to production?
     - `<a>` Yes, after I check `payment.spec.ts:88`.
     - (b) Yes, now.
6. **Risks:**
   - **R1.** `jsonwebtoken` 8.5.1 is older than the 9.0.0 security release.
     - `<a>` update it after the deploy | (b) skip | (c) later
7. **Ideas:**
