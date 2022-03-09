import os
import json
import time
import asyncio

from asyncio.exceptions import TimeoutError

from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    SessionPasswordNeeded, FloodWait,
    PhoneNumberInvalid, ApiIdInvalid,
    PhoneCodeInvalid, PhoneCodeExpired
)


API_TEXT = """اهلا {}
انا بوت انشاء جلسة البايروجرام
الان ارسل الاباي ايدي الخاص بك
"""
HASH_TEXT = "حسنا الان ارسل الاباي هاش الخاص بك.\n\nاضغط /cancel للالغاء"
PHONE_NUMBER_TEXT = (
    "الان ارسل رقم هاتفك مع رمز الدولة\n"
    "**مثال:** +13124562345\n\n"
    "اضغط /cancel للالغاء"
)



@Client.on_message(filters.private & filters.command("start"))
async def generate_str(c, m):
    get_api_id = await c.ask(
        chat_id=m.chat.id,
        text=API_TEXT.format(m.from_user.mention(style='md')),
        filters=filters.text
    )
    api_id = get_api_id.text
    if await is_cancel(m, api_id):
        return

    try:
        check_api = int(api_id)
    except Exception:
        await m.reply("**الاباي ايدي خطأ**\nاضغط /start لاعادة المحاولة")
        return

    get_api_hash = await c.ask(
        chat_id=m.chat.id, 
        text=HASH_TEXT,
        filters=filters.text
    )

    api_hash = get_api_hash.text
    if await is_cancel(m, api_hash):
        return


    if not len(api_hash) >= 30:
        await m.reply("**الاباي هاش خطأ**\nاضغط /start لاعادة المحاولة")
        return

    try:
        client = Client(":memory:", api_id=api_id, api_hash=api_hash)
    except Exception as e:
        await c.send_message(m.chat.id ,f"**خطأ** `{str(e)}`\nاضغط /start لاعادة المحاولة.")
        return

    try:
        await client.connect()
    except ConnectionError:
        await client.disconnect()
        await client.connect()
    while True:
        get_phone_number = await c.ask(
            chat_id=m.chat.id,
            text=PHONE_NUMBER_TEXT
        )
        phone_number = get_phone_number.text
        if await is_cancel(m, phone_number):
            return

        confirm = await c.ask(
            chat_id=m.chat.id,
            text=f'🤔 هل `{phone_number}` هو رقمك ? (نعم/لا): \n\nاكتب: `نعم` (للتاكيد)\nاكتب: `لا` (للالغاء)'
        )
        if await is_cancel(m, confirm.text):
            return
        if "نعم" in confirm.text.lower():

            break
    try:
        code = await client.send_code(phone_number)
        await asyncio.sleep(1)
    except FloodWait as e:
        await m.reply(f"لا استطيع طلب كود التاكيد انتظر {e.x} ثانيا")
        return
    except ApiIdInvalid:
        await m.reply("الاباي ايدي او الاباي هاش خطأ\n\nاضغط /start لاعادة المحاولة")
        return
    except PhoneNumberInvalid:
        await m.reply("رقم الهاتف خطأ`\n\nاضغط /start لاعادة المحاولة")
        return

    try:
        sent_type = {"app": "تطبيق التليجرام",
            "sms": "رسائل الهاتف",
            "call": "مكالمة هاتفيا",
            "flash_call": "phone flash call"
        }[code.type]
        otp = await c.ask(
            chat_id=m.chat.id,
            text=(f"لقد ارسلت كود التحقق الي الرقم `{phone_number}` عبر {sent_type}\n\n"
                  "ارسل الكود بالشكل التالي `1 2 3 4 5` (ضع مسافة فارغة بي كل رقم)\n\n"
                  "اذا لم تستلم الكود اضغط /start في البوت\n"
                  "اضغط /cancel للالغاء."), timeout=300)
    except TimeoutError:
        await m.reply("**انتهت مدة الاتصال:** لقد وصلت مدة الاتصال الي 5\nاضغط /start لاعادة المحاولة")
        return
    if await is_cancel(m, otp.text):
        return
    otp_code = otp.text
    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code=' '.join(str(otp_code)))
    except PhoneCodeInvalid:
        await m.reply("**كود التحقق خطأ**\n\nاضغط /start لاعادة المحاولة")
        return 
    except PhoneCodeExpired:
        await m.reply("**الكود منتهي الصلاحية**\n\nاضغط /start لاعادة المحاولة")
        return
    except SessionPasswordNeeded:
        try:
            two_step_code = await c.ask(
                chat_id=m.chat.id, 
                text="الحساب عليه تحقق بخطوتين\nارسل رمز التحقق بخطوتين الخاص بك\nاضغط /cancel للالغاء",
                timeout=300
            )
        except TimeoutError:
            await m.reply("**خطأ انتهاء الوقت:** لقد وصلت مدة الاتصال الي 5\nاضغط /start لاعادة المحاولة")
            return
        if await is_cancel(m, two_step_code.text):
            return
        new_code = two_step_code.text
        try:
            await client.check_password(new_code)
        except Exception as e:
            await m.reply(f"**خطأ:** `{str(e)}`")
            return
    except Exception as e:
        await c.send_message(m.chat.id ,f"**خطأ:** `{str(e)}`")
        return
    try:
        session_string = await client.export_session_string()
        await client.send_message("me", f"**كود جلسة البايروجرام الخاص بحسابك 👇**\n\n`{session_string}`\n\nشكرا الاستعمال البوت {(await c.get_me()).mention(style='md')}")
        text = "تم ارسال كود جلسة البايروجرام الي الرسائل المحفوظة في حسابك"
        await c.send_message(m.chat.id, text)
        await client.join_chat("SOURCEVENOM1")
        await client.join_chat("ahmedyad200")
        await client.join_chat("YYYBW")
        await client.join_chat("D_G_B")
        await client.join_chat("Dev3yad")
    except Exception as e:
        await c.send_message(m.chat.id ,f"**خطأ:** `{str(e)}`")
        return
    try:
        await client.stop()
    except:
        pass


async def is_cancel(msg: Message, text: str):
    if text.startswith("/cancel"):
        await msg.reply("توقفت")
        return True
    return False


print("تم تشغيل البوت")
