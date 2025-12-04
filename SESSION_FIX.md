# إصلاح خطأ SessionManager

## المشكلة

عند محاولة المستخدم إضافة جلسة عبر `/addsession`، ظهر الخطأ التالي:

```
'SessionManager' object has no attribute 'send_code'
```

## السبب

الكود في `user_session_handler.py` كان يحاول استدعاء دالة `send_code()` غير موجودة في `SessionManager`:

```python
await session_manager.send_code(phone, api_id, api_hash)  # ❌ خطأ
```

لكن الدوال الصحيحة في `SessionManager` هي:
- `create_session()` - لإنشاء جلسة وإرسال كود التحقق
- `verify_code()` - للتحقق من الكود وإكمال تسجيل الدخول

## الحل

تم تحديث `user_session_handler.py` لاستخدام الدوال الصحيحة:

### 1. إرسال كود التحقق

```python
# إرسال كود التحقق
result = await session_manager.create_session(phone, api_id, api_hash)

if result['status'] != 'code_sent':
    # معالجة الخطأ
    return ConversationHandler.END

# حفظ phone_code_hash للاستخدام لاحقاً
context.user_data['phone_code_hash'] = result['phone_code_hash']
```

### 2. التحقق من الكود

```python
# التحقق من الكود
result = await session_manager.verify_code(
    phone, code, phone_code_hash, api_id, api_hash
)

if result['status'] == 'password_required':
    # يحتاج كلمة مرور
    return USER_ADD_SESSION_PASSWORD

if result['status'] == 'success':
    session_string = result['session_string']
    # حفظ الجلسة...
```

### 3. التحقق مع كلمة المرور

```python
# التحقق مع كلمة المرور
result = await session_manager.verify_code(
    phone, code, phone_code_hash, api_id, api_hash, password
)

if result['status'] == 'success':
    session_string = result['session_string']
    # حفظ الجلسة...
```

## التغييرات

### الملفات المعدلة:
- `user_session_handler.py` - إصلاح استدعاءات SessionManager

### الدوال المحدثة:
1. `user_add_session_api()` - تستخدم `create_session()` بدلاً من `send_code()`
2. `user_add_session_code()` - تستخدم `verify_code()` بدلاً من `sign_in()`
3. `user_add_session_password()` - تستخدم `verify_code()` مع معامل password

## الاختبار

الآن يمكن للمستخدمين إضافة جلساتهم بنجاح:

1. `/addsession` - بدء العملية
2. إدخال رقم الهاتف
3. إدخال API ID
4. إدخال API Hash
5. إدخال كود التحقق
6. (اختياري) إدخال كلمة المرور إذا كان الحساب محمي
7. ✅ تم إضافة الجلسة بنجاح!

## الحالة

- ✅ تم إصلاح الخطأ
- ✅ تم رفع الإصلاح إلى GitHub
- ⏳ انتظر 2-3 دقائق حتى يتم نشر التحديث على Render.com
- ✅ النظام جاهز للاستخدام

---

تم الإصلاح: ديسمبر 2025
