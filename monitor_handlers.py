"""
معالجات واجهة مراقبة القروبات
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def show_monitors_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db, group_monitor) -> int:
    """عرض قائمة المراقبات"""
    monitors = db.get_monitors()
    
    text = "👁️ **مراقبة القروبات/القنوات**\n\n"
    text += "📡 مراقبة تلقائية 24/7 لاستخراج البطاقات\n\n"
    
    if monitors:
        text += "المراقبات النشطة:\n\n"
        keyboard = []
        
        for monitor in monitors:
            status = "🟢 نشط" if monitor['is_active'] else "🔴 متوقف"
            stats = db.get_monitor_stats(monitor['id'])
            
            text += f"**{monitor['name']}** - {status}\n"
            text += f"   📊 البطاقات: {stats['total_cards']}\n"
            text += f"   ✅ النجاح: {stats['success_cards']}\n"
            text += f"   📅 {monitor['created_at'][:10]}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"👁️ {monitor['name']}", 
                    callback_data=f"monitor_{monitor['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("➕ إضافة مراقبة جديدة", callback_data="add_monitor")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        text += "لا توجد مراقبات مضافة.\n\n"
        text += "💡 **كيف تعمل؟**\n"
        text += "1. أضف مراقبة لقروب/قناة\n"
        text += "2. البوت يراقب الرسائل 24/7\n"
        text += "3. يستخرج البطاقات تلقائياً\n"
        text += "4. يرسلها للبوت المستهدف فوراً\n\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مراقبة جديدة", callback_data="add_monitor")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return context.user_data.get('current_state', 0)


async def handle_monitor_callback(query, data, db, group_monitor):
    """معالجة callbacks المراقبة"""
    
    if data == "add_monitor":
        # TODO: إضافة مراقبة جديدة
        await query.edit_message_text(
            "🚧 ميزة إضافة مراقبة جديدة قيد التطوير...\n\n"
            "قريباً ستتمكن من:\n"
            "✅ إضافة قروب/قناة للمراقبة\n"
            "✅ تحديد البوت المستهدف\n"
            "✅ تفعيل الإرسال التلقائي"
        )
    
    elif data.startswith("monitor_"):
        monitor_id = int(data.split("_")[1])
        monitor = db.get_monitor(monitor_id)
        
        if not monitor:
            await query.edit_message_text("❌ المراقبة غير موجودة.")
            return
        
        stats = db.get_monitor_stats(monitor_id)
        
        text = f"👁️ **{monitor['name']}**\n\n"
        text += f"📱 القروب/القناة: `{monitor['chat_id']}`\n"
        text += f"🤖 البوت المستهدف: {monitor['target_bot']}\n"
        text += f"⚡ الأمر: {monitor['target_command']}\n"
        text += f"🔄 إرسال تلقائي: {'✅ نعم' if monitor['auto_send'] else '❌ لا'}\n\n"
        text += f"📊 **الإحصائيات:**\n"
        text += f"   📥 إجمالي البطاقات: {stats['total_cards']}\n"
        text += f"   📤 المرسلة: {stats['sent_cards']}\n"
        text += f"   ✅ النجاح: {stats['success_cards']}\n"
        text += f"   ❌ الفشل: {stats['failed_cards']}\n\n"
        text += f"📅 تاريخ الإنشاء: {monitor['created_at']}\n"
        
        keyboard = []
        if monitor['is_active']:
            keyboard.append([InlineKeyboardButton("⏸️ إيقاف", callback_data=f"stop_monitor_{monitor_id}")])
        else:
            keyboard.append([InlineKeyboardButton("▶️ تشغيل", callback_data=f"start_monitor_{monitor_id}")])
        
        keyboard.append([InlineKeyboardButton("📋 البطاقات المستخرجة", callback_data=f"monitor_cards_{monitor_id}")])
        keyboard.append([InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_monitor_{monitor_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_monitors")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("start_monitor_"):
        monitor_id = int(data.split("_")[2])
        result = await group_monitor.start_monitor(monitor_id)
        
        if result:
            await query.answer("✅ تم تشغيل المراقبة!")
        else:
            await query.answer("❌ فشل تشغيل المراقبة!")
    
    elif data.startswith("stop_monitor_"):
        monitor_id = int(data.split("_")[2])
        await group_monitor.stop_monitor(monitor_id)
        await query.answer("⏸️ تم إيقاف المراقبة!")
    
    elif data.startswith("monitor_cards_"):
        monitor_id = int(data.split("_")[2])
        cards = db.get_extracted_cards(monitor_id, limit=10)
        
        if cards:
            text = f"📋 **آخر 10 بطاقات مستخرجة:**\n\n"
            for card in cards:
                status_emoji = "✅" if card['status'] == 'success' else "❌" if card['status'] == 'failed' else "❓"
                card_preview = card['card_data'][:4] + "****" + card['card_data'][-4:]
                text += f"{status_emoji} {card_preview}\n"
                text += f"   📅 {card['created_at']}\n\n"
        else:
            text = "لا توجد بطاقات مستخرجة بعد."
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"monitor_{monitor_id}")]]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("delete_monitor_"):
        monitor_id = int(data.split("_")[2])
        await group_monitor.stop_monitor(monitor_id)
        db.delete_monitor(monitor_id)
        await query.edit_message_text("✅ تم حذف المراقبة بنجاح!")
