with open('userbot_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('openai/gpt-oss-20b', 'llama-3.1-70b-versatile')
with open('userbot_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('openai/gpt-oss-20b', 'llama-3.1-70b-versatile')

old_logic = '''async def btn_link_profile(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, status_text, days_left, tariff = await check_user_access(user_id)'''

new_logic = '''async def btn_link_profile(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check if already connected
    user = await get_user(user_id)
    if user and user.get('session_string'):
        try:
            from userbot_manager import active_userbots
            if user_id in active_userbots:
                await message.answer("✅ <b>Sizning profilingiz allaqachon botga muvaffaqiyatli ulangan!</b>\\nAI hozir xabarlaringizga javob bermoqda.\\n\\nAgar boshqa raqam ulamoqchi bo'lsangiz yoki muammo bo'lsa, adminga murojaat qiling.")
                return
        except Exception:
            pass

    has_access, status_text, days_left, tariff = await check_user_access(user_id)'''

text = text.replace(old_logic, new_logic)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(text)
