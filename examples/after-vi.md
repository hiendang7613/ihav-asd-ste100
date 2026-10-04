**Agents-Zone**
- `4:12 PM` test đăng nhập lỗi với client mới => đọc `src/auth.ts`
- `4:15 PM` `verifyToken` đọc một header riêng => sửa để đọc `Authorization`
- `4:18 PM` kiểm tra bản sửa => chạy `npm test`

**Result-Zone**
- **Nguyên nhân:** `verifyToken` trong `src/auth.ts:42` đọc token từ một header riêng. Client mới gửi `Authorization: Bearer <token>`.
- **Cách sửa:** `verifyToken` nay đọc header `Authorization`.

**Admin-Zone**

**Conclusion:** Test đăng nhập đã đạt; còn một test thanh toán lỗi, chưa kiểm tra nguyên nhân.

0. **Goals:**
   - **L1.** Mọi client đều có thể đăng nhập.
   - **G1.** Sửa đăng nhập cho client mới -> L1 `#######---` 2/3
1. **Done:**
   - **Sửa đăng nhập:** `verifyToken` đọc đúng header; `npm test` chạy 214 test, 213 test đạt.
2. **Doing:**
3. **Todos:**
   - **Test thanh toán:** tìm nguyên nhân `payment.spec.ts:88` lỗi; tôi không sửa mã thanh toán.
4. **Pending:**
5. **Quests:**
   - **Q1.** Kiểm tra `payment.spec.ts:88` trước khi gộp thay đổi này?
     - `<a>` Có, kiểm tra ngay.
     - (b) Sau khi gộp.
6. **Risks:**
   - **R1.** `jsonwebtoken` 8.5.1 cũ hơn bản vá bảo mật 9.0.0.
     - `<a>` cập nhật trong một thay đổi riêng | (b) bỏ qua | (c) để sau
7. **Ideas:**
   - **I1.** Thêm test gửi `Authorization: Bearer <token>`, để lỗi này không quay lại.
     - `<a>` lên kế hoạch | (b) bỏ qua | (c) để sau
