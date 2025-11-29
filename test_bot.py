#!/usr/bin/env python3
"""
اختبار شامل للبوت
"""
import asyncio
import sys
from database import Database
from session_manager import SessionManager
from task_manager import CardFileManager, TaskRunner

async def test_database():
    """اختبار قاعدة البيانات"""
    print("🔍 اختبار قاعدة البيانات...")
    try:
        db = Database()
        print("✅ قاعدة البيانات تعمل بشكل صحيح")
        return True
    except Exception as e:
        print(f"❌ خطأ في قاعدة البيانات: {e}")
        return False

async def test_session_manager():
    """اختبار مدير الجلسات"""
    print("\n🔍 اختبار مدير الجلسات...")
    try:
        sm = SessionManager()
        print("✅ مدير الجلسات تم تهيئته بنجاح")
        return True
    except Exception as e:
        print(f"❌ خطأ في مدير الجلسات: {e}")
        return False

async def test_card_manager():
    """اختبار مدير البطاقات"""
    print("\n🔍 اختبار مدير البطاقات...")
    try:
        cm = CardFileManager()
        
        # اختبار حفظ ملف
        test_content = "1234567890123456|12|2025|123\n9876543210987654|01|2026|456"
        filepath = cm.save_cards_file(test_content, "test_cards.txt")
        
        # اختبار قراءة البطاقات
        cards = cm.read_cards(filepath)
        
        if len(cards) == 2:
            print(f"✅ مدير البطاقات يعمل بشكل صحيح ({len(cards)} بطاقات)")
            return True
        else:
            print(f"❌ خطأ في عدد البطاقات: {len(cards)}")
            return False
    except Exception as e:
        print(f"❌ خطأ في مدير البطاقات: {e}")
        return False

async def test_text_formatter():
    """اختبار منسق النصوص"""
    print("\n🔍 اختبار منسق النصوص...")
    try:
        from text_formatter import TextFormatter
        
        # اختبار تنسيق جلسة
        session = {
            'id': 1,
            'name': 'Test Session',
            'phone': '+1234567890',
            'is_active': True
        }
        
        text, parse_mode = TextFormatter.format_session_details(session, use_html=False)
        
        if text and parse_mode is None:
            print("✅ منسق النصوص يعمل بشكل صحيح")
            return True
        else:
            print("❌ خطأ في تنسيق النصوص")
            return False
    except Exception as e:
        print(f"❌ خطأ في منسق النصوص: {e}")
        return False

async def main():
    """الاختبار الرئيسي"""
    print("=" * 50)
    print("🚀 بدء الاختبار الشامل للبوت")
    print("=" * 50)
    
    results = []
    
    # اختبار المكونات
    results.append(await test_database())
    results.append(await test_session_manager())
    results.append(await test_card_manager())
    results.append(await test_text_formatter())
    
    # النتيجة النهائية
    print("\n" + "=" * 50)
    print("📊 نتائج الاختبار:")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ نجح: {passed}/{total}")
    print(f"❌ فشل: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 جميع الاختبارات نجحت! البوت جاهز للعمل.")
        return 0
    else:
        print("\n⚠️ بعض الاختبارات فشلت. يرجى مراجعة الأخطاء.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
