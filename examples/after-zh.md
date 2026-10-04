**Agents-Zone**
- `4:12 PM` 新客户端的登录测试失败 => 阅读 `src/auth.ts`
- `4:15 PM` `verifyToken` 读取了自定义请求头 => 改为读取 `Authorization`
- `4:18 PM` 验证修复 => 运行 `npm test`

**Result-Zone**
- **原因:** `src/auth.ts:42` 中的 `verifyToken` 读取了自定义请求头。新客户端发送 `Authorization: Bearer <token>`。
- **修复:** `verifyToken` 现在读取 `Authorization` 请求头。

**Admin-Zone**

**Conclusion:** 登录测试已通过；一个支付测试仍然失败，原因未检查。

0. **Goals:**
   - **L1.** [~70%] [#######---] | 所有客户端都能登录。
   - **G1.** 修复新客户端的登录
1. **Done:**
   - **登录修复:** `verifyToken` 读取正确的请求头；`npm test` 运行 214 个测试，213 个通过。
2. **Doing:**
3. **Todos:**
   - **支付测试:** 查明 `payment.spec.ts:88` 失败的原因；我没有修改支付代码。
4. **Pending:**
5. **Quests:**
   - **Q1.** 合并前先检查 `payment.spec.ts:88` 吗？
     - `<a>` 是，现在检查。
     - (b) 合并之后再检查。
6. **Risks:**
   - **R1.** `jsonwebtoken` 8.5.1 早于 9.0.0 安全更新版本。
     - `<a>` 另开一个变更来更新 | (b) 跳过 | (c) 以后再说
7. **Ideas:**
   - **I1.** 添加一个发送 `Authorization: Bearer <token>` 的测试，防止这个问题再次出现。
     - `<a>` 列入计划 | (b) 跳过 | (c) 以后再说
