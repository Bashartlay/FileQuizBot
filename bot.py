import os
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# إنشاء البوت
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("مرحبًا! أرسل لي ملف PDF أو Word وسأقوم بإنشاء أسئلة اختيار من متعدد بناءً على محتواه.")

# قراءة محتوى ملف PDF
def read_pdf(file_path):
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading PDF file: {e}")
    return text

# قراءة محتوى ملف Word
def read_docx(file_path):
    text = ""
    try:
        doc = DocxDocument(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        print(f"Error reading Word file: {e}")
    return text

# تلخيص النص لتقليل حجمه عبر تقسيمه إلى أجزاء صغيرة
def summarize_text(text):
    part_length = 3000  # الطول الأقصى لكل جزء من النص
    summaries = []

    # تقسيم النص إلى أجزاء صغيرة وتلخيص كل جزء على حدة
    while len(text) > part_length:
        part = text[:part_length]
        text = text[part_length:]

        prompt = f"أعطني ملخصًا قصيرًا للنص التالي:\n\n{part}"
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                timeout=15
            )
            summary = response['choices'][0]['message']['content']
            summaries.append(summary)
        except Exception as e:
            print(f"Error summarizing part of the text: {e}")
            summaries.append(part)  # إذا فشل التلخيص، أضف الجزء الأصلي

    # تلخيص الجزء الأخير إذا كان النص قصيرًا
    if text:
        prompt = f"أعطني ملخصًا قصيرًا للنص التالي:\n\n{text}"
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                timeout=15
            )
            summary = response['choices'][0]['message']['content']
            summaries.append(summary)
        except Exception as e:
            print(f"Error summarizing the last part of the text: {e}")
            summaries.append(text)

    # جمع الملخصات في نص واحد
    final_summary = "\n".join(summaries)
    return final_summary

# إنشاء أسئلة اختيار من متعدد باستخدام ChatGPT
def generate_questions(text):
    parts = []
    max_length = 3000  # الطول الأقصى لكل جزء من النص

    while len(text) > max_length:
        parts.append(text[:max_length])
        text = text[max_length:]

    parts.append(text)  # إضافة الجزء الأخير

    all_questions = ""
    for part in parts:
        prompt = f"أنشئ 4 أسئلة اختيار من متعدد بناءً على النص التالي:\n\n{part}\n\n" \
                 "يجب أن يكون لكل سؤال 4 خيارات، ويكون الخيار الصحيح واضحًا."
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
                timeout=20
            )
            questions = response['choices'][0]['message']['content']
            all_questions += questions + "\n\n"
        except Exception as e:
            print(f"Error generating questions: {e}")
            all_questions += "عذرًا، حدث خطأ أثناء إنشاء الأسئلة.\n\n"
    
    return all_questions

# معالجة الملفات المرسلة من المستخدم
async def handle_file(update: Update, context: CallbackContext) -> None:
    # التأكد من أن مجلد 'downloads' موجود
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    file = update.message.document
    if file.mime_type not in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        await update.message.reply_text("يرجى إرسال ملف PDF أو Word فقط.")
        return

    # تحميل الملف باستخدام get_file
    file_object = await file.get_file()
    file_path = os.path.join("downloads", file.file_name)
    await file_object.download_to_drive(file_path)

    # قراءة النص من الملف
    if file.mime_type == "application/pdf":
        text = read_pdf(file_path)
    elif file.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = read_docx(file_path)

    if not text:
        await update.message.reply_text("عذرًا، لم أتمكن من استخراج النص من الملف.")
        return

    # تلخيص النص إذا كان كبيرًا
    if len(text) > 4000:
        text = summarize_text(text)

    # إنشاء الأسئلة باستخدام ChatGPT
    questions = generate_questions(text)
    
    # إرسال الأسئلة للمستخدم
    await update.message.reply_text(f"الأسئلة:\n\n{questions}")

    # حذف الملف بعد الانتهاء
    os.remove(file_path)

# تهيئة وتشغيل البوت
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    application.run_polling()

if __name__ == "__main__":
    main()
