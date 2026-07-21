from services.firebase_service import init_firebase, save_memory_note
init_firebase()
result = save_memory_note('test_user', 'تجربة حفظ ملاحظة', 'تجربة', 'test')
print('Result:', result)