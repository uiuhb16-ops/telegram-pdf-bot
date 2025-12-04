#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot v2 - AI-Powered PDF Generator with Smart Chat
Features:
- Intelligent conversation using Gemini AI
- Comprehensive symbol correction (chemical, mathematical, physical)
- Professional PDF generation
"""

import os
import logging
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from weasyprint import HTML, CSS
from PIL import Image
import PyPDF2
from pdf2image import convert_from_path
import tempfile

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API Keys
TELEGRAM_TOKEN = "8228116020:AAHcAIBw8zvAq5LYb-5TcJ4I7QgE9SRauaI"
GEMINI_API_KEY = "AIzaSyAmXjXYbZLZ1yvl61m_7BY9XZf5uFNmnf8"

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

class PDFGenerator:
    """Generate formatted PDF with proper mathematical and chemical notation using WeasyPrint"""
    
    def __init__(self):
        self.css_style = """
            @page {
                size: letter;
                margin: 1in;
            }
            
            body {
                font-family: 'Times New Roman', Times, serif;
                font-size: 12pt;
                line-height: 1.6;
                color: #000000;
            }
            
            h1 {
                color: #CC0000;
                font-size: 16pt;
                font-weight: bold;
                margin-top: 16pt;
                margin-bottom: 12pt;
            }
            
            p {
                margin-bottom: 6pt;
                text-align: left;
            }
            
            ul {
                margin-left: 20pt;
                margin-bottom: 10pt;
            }
            
            li {
                margin-bottom: 4pt;
            }
            
            .normal-text {
                margin-bottom: 10pt;
            }
        """
    
    def text_to_html(self, text_content):
        """Convert text content to HTML with proper formatting"""
        
        html_parts = ['<!DOCTYPE html>', '<html>', '<head>', 
                     '<meta charset="UTF-8">', '</head>', '<body>']
        
        lines = text_content.split('\n')
        in_list = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                if in_list:
                    html_parts.append('</ul>')
                    in_list = False
                html_parts.append('<br>')
                continue
            
            # Check if it's a numbered heading
            if line and len(line) > 0 and line[0].isdigit() and '. ' in line[:10]:
                if in_list:
                    html_parts.append('</ul>')
                    in_list = False
                html_parts.append(f'<h1>{line}</h1>')
            
            # Check if it's a bullet point
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                clean_line = line[1:].strip()
                if not in_list:
                    html_parts.append('<ul>')
                    in_list = True
                html_parts.append(f'<li>{clean_line}</li>')
            
            else:
                if in_list:
                    html_parts.append('</ul>')
                    in_list = False
                html_parts.append(f'<p class="normal-text">{line}</p>')
        
        if in_list:
            html_parts.append('</ul>')
        
        html_parts.extend(['</body>', '</html>'])
        
        return '\n'.join(html_parts)
    
    def create_pdf(self, text_content, output_path):
        """Create formatted PDF from text content"""
        
        html_content = self.text_to_html(text_content)
        
        # Create PDF using WeasyPrint
        HTML(string=html_content).write_pdf(
            output_path,
            stylesheets=[CSS(string=self.css_style)]
        )
        
        logger.info(f"PDF created successfully: {output_path}")


class GeminiProcessor:
    """Process images, text, and chat using Gemini AI"""
    
    def __init__(self):
        self.model_vision = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.model_text = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.model_chat = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Chat history per user
        self.chat_sessions = {}
    
    async def chat(self, user_id, message):
        """Handle intelligent conversation with user"""
        
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = self.model_chat.start_chat(history=[])
        
        chat = self.chat_sessions[user_id]
        
        system_context = """أنت مساعد ذكي في بوت تلغرام متخصص في معالجة المستندات العلمية.

مهامك:
1. الإجابة على أسئلة المستخدم بذكاء
2. مساعدته في استخدام البوت
3. تنفيذ أوامره المتعلقة بالملفات والمستندات
4. التحدث بطريقة ودية واحترافية

قدراتك:
- استخراج النص من الصور وملفات PDF
- تصحيح الأخطاء الإملائية
- معالجة الرموز الكيميائية والرياضية
- إنشاء ملفات PDF منسقة

تحدث بالعربية بشكل طبيعي وودي."""
        
        try:
            response = chat.send_message(f"{system_context}\n\nالمستخدم: {message}")
            return response.text
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "عذراً، حدث خطأ في المحادثة. حاول مرة أخرى."
    
    async def extract_text_from_image(self, image_path):
        """Extract text from image using Gemini Vision with comprehensive symbol handling"""
        
        try:
            image = Image.open(image_path)
            
            prompt = """Extract ALL text from this image in English with PERFECT symbol accuracy.

CRITICAL: Use proper Unicode for ALL symbols:

CHEMICAL FORMULAS:
- H₂O, CO₂, O₂, N₂, Cl₂
- H₂SO₄, HNO₃, NaOH, KOH
- CH₄, C₂H₅OH, C₆H₁₂O₆
- NAD⁺, NADH, NAD⁺/NADH
- FAD, FADH₂
- ATP, ADP, AMP
- Ca²⁺, Mg²⁺, Fe²⁺, Fe³⁺, Na⁺, K⁺, Cl⁻
- NH₃, NH₄⁺, NO₃⁻, SO₄²⁻, PO₄³⁻

MATHEMATICAL SYMBOLS:
- Subscripts: ₀₁₂₃₄₅₆₇₈₉
- Superscripts: ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ
- Arrows: → ← ↔ ⇌ ⇒ ⇐
- Greek: α β γ δ ε ζ η θ λ μ π ρ σ τ φ χ ψ ω Δ Σ Π Ω
- Math: ± × ÷ ≈ ≠ ≤ ≥ ∞ √ ∫ ∑ ∏ ∂
- Fractions: ½ ⅓ ⅔ ¼ ¾ ⅕ ⅖ ⅗ ⅘ ⅙ ⅚ ⅛ ⅜ ⅝ ⅞

PHYSICS SYMBOLS:
- °C, °F, K (temperature)
- m/s, km/h, m/s²
- J, kJ, kcal, eV
- Pa, kPa, atm, mmHg
- mol, mmol, μmol
- Å, nm, μm, mm, cm, m, km

EXAMPLES:
✓ H₂O (correct)
✗ H2O, HPO (wrong)
✓ E + S → ES → E + P (correct)
✗ E + S -> ES -> E + P (wrong)
✓ ΔG° = -RT ln K (correct)
✗ delta G = -RT ln K (wrong)
✓ pH = -log[H⁺] (correct)
✗ pH = -log[H+] (wrong)

REQUIREMENTS:
1. Extract EVERY word, number, symbol
2. Preserve structure (headings, bullets, spacing)
3. Use ONLY proper Unicode symbols
4. Do NOT add explanations
5. Output ONLY the extracted text

Extract now:"""
            
            response = self.model_vision.generate_content([prompt, image])
            extracted_text = response.text.strip()
            
            logger.info(f"Extracted text length: {len(extracted_text)}")
            return extracted_text
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            raise
    
    async def correct_and_format_text(self, text):
        """Correct spelling and ensure ALL symbols are properly formatted"""
        
        prompt = f"""You are an expert scientific text formatter. Fix ALL errors and ensure PERFECT Unicode symbols.

INPUT TEXT:
{text}

COMPREHENSIVE SYMBOL CORRECTION:

1. CHEMICAL FORMULAS - Use Unicode subscripts/superscripts:
   ✓ H₂O, CO₂, O₂, N₂, H₂SO₄, HNO₃
   ✓ CH₄, C₂H₅OH, C₆H₁₂O₆, C₁₂H₂₂O₁₁
   ✓ NAD⁺, NADH, FADH₂, ATP, ADP
   ✓ Ca²⁺, Mg²⁺, Fe²⁺, Fe³⁺, Na⁺, K⁺, Cl⁻
   ✓ NH₃, NH₄⁺, NO₃⁻, SO₄²⁻, PO₄³⁻
   ✗ NEVER: H2O, CO2, NAD+, Ca2+, SO4-2

2. MATHEMATICAL EQUATIONS - Use Unicode:
   ✓ Arrows: → ← ↔ ⇌ ⇒
   ✓ Subscripts: x₁, x₂, aₙ, P₁, P₂
   ✓ Superscripts: x², x³, xⁿ, 10⁻⁵
   ✓ Symbols: ± × ÷ ≈ ≠ ≤ ≥ ∞ √
   ✗ NEVER: ->, <->, x^2, x^n, +/-

3. GREEK LETTERS - Use Unicode:
   ✓ α (alpha), β (beta), γ (gamma), δ (delta)
   ✓ Δ (Delta), Σ (Sigma), Π (Pi), Ω (Omega)
   ✓ λ (lambda), μ (mu), π (pi), θ (theta)
   ✗ NEVER: delta, alpha, beta, sigma

4. PHYSICS UNITS - Use proper symbols:
   ✓ °C, °F, K (temperature)
   ✓ m/s, km/h, m/s² (velocity, acceleration)
   ✓ J, kJ, kcal (energy)
   ✓ mol, mmol, μmol (amount)
   ✓ Å, nm, μm, mm (length)

5. SPELLING - Fix ALL English spelling errors

REQUIREMENTS:
- Fix EVERY symbol error
- Preserve structure (headings, bullets)
- Do NOT add new content
- Do NOT remove content
- Output ONLY corrected text

EXAMPLES:
Input: "H2O and CO2 react at 25C"
Output: "H₂O and CO₂ react at 25°C"

Input: "delta G = -RT ln K"
Output: "ΔG = -RT ln K"

Input: "Ca2+ + 2e- -> Ca"
Output: "Ca²⁺ + 2e⁻ → Ca"

Input: "x^2 + y^2 = r^2"
Output: "x² + y² = r²"

Correct the text now:"""
        
        try:
            response = self.model_text.generate_content(prompt)
            corrected_text = response.text.strip()
            
            logger.info(f"Text corrected, length: {len(corrected_text)}")
            return corrected_text
            
        except Exception as e:
            logger.error(f"Error correcting text: {e}")
            raise


class TelegramBot:
    """Main Telegram Bot handler with AI chat"""
    
    def __init__(self):
        self.gemini = GeminiProcessor()
        self.pdf_gen = PDFGenerator()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """مرحباً! 👋 أنا بوتك الذكي لإنشاء ملفات PDF الاحترافية.

🤖 **يمكنني:**
✅ التحدث معك والإجابة على أسئلتك
✅ استخراج النص من الصور وملفات PDF
✅ تصحيح جميع الأخطاء الإملائية
✅ معالجة جميع الرموز بشكل صحيح:
   • كيميائية: H₂O، CO₂، NAD⁺، FADH₂، Ca²⁺
   • رياضية: x², →, ≤, ≥, ∞, √, ∑
   • فيزيائية: °C, m/s², ΔG, λ, μ
✅ إنشاء PDF منسق بألوان احترافية

💬 **كيف تستخدمني:**
• تحدث معي عن أي شيء - سأفهمك وأساعدك
• أرسل لي صورة أو PDF - سأعالجه وأنشئ لك ملف منسق
• اطلب مني أي شيء - سأنفذ أوامرك

جرب الآن! أرسل لي رسالة أو ملف 📄"""
        
        await update.message.reply_text(welcome_message)
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with AI chat"""
        
        user_id = update.message.from_user.id
        user_message = update.message.text
        
        # Get AI response
        response = await self.gemini.chat(user_id, user_message)
        
        await update.message.reply_text(response)
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle PDF documents"""
        
        await update.message.reply_text("📄 جاري معالجة الملف...")
        
        try:
            # Download the file
            file = await update.message.document.get_file()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                await file.download_to_drive(temp_pdf.name)
                temp_pdf_path = temp_pdf.name
            
            # Convert PDF to images
            await update.message.reply_text("🔄 جاري تحويل PDF إلى صور...")
            images = convert_from_path(temp_pdf_path, dpi=300)
            
            # Extract text from all pages
            all_text = []
            for i, image in enumerate(images):
                await update.message.reply_text(f"📖 جاري قراءة الصفحة {i+1}/{len(images)}...")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_img:
                    image.save(temp_img.name, 'PNG')
                    temp_img_path = temp_img.name
                
                text = await self.gemini.extract_text_from_image(temp_img_path)
                all_text.append(text)
                
                os.unlink(temp_img_path)
            
            combined_text = '\n\n'.join(all_text)
            
            # Correct and format
            await update.message.reply_text("✍️ جاري تصحيح جميع الأخطاء والرموز...")
            corrected_text = await self.gemini.correct_and_format_text(combined_text)
            
            # Generate PDF
            await update.message.reply_text("📝 جاري إنشاء ملف PDF المنسق...")
            output_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            self.pdf_gen.create_pdf(corrected_text, output_pdf.name)
            
            # Send the PDF
            await update.message.reply_document(
                document=open(output_pdf.name, 'rb'),
                filename='formatted_document.pdf',
                caption="✅ تم إنشاء الملف بنجاح!\n\n✨ تم تصحيح جميع الأخطاء والرموز (كيميائية، رياضية، فيزيائية) بشكل صحيح."
            )
            
            # Cleanup
            os.unlink(temp_pdf_path)
            os.unlink(output_pdf.name)
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الملف:\n{str(e)}")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages"""
        
        await update.message.reply_text("🖼️ جاري معالجة الصورة...")
        
        try:
            # Download the photo
            photo = update.message.photo[-1]  # Get highest resolution
            file = await photo.get_file()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_img:
                await file.download_to_drive(temp_img.name)
                temp_img_path = temp_img.name
            
            # Extract text
            await update.message.reply_text("📖 جاري استخراج النص...")
            extracted_text = await self.gemini.extract_text_from_image(temp_img_path)
            
            # Correct and format
            await update.message.reply_text("✍️ جاري تصحيح جميع الأخطاء والرموز...")
            corrected_text = await self.gemini.correct_and_format_text(extracted_text)
            
            # Generate PDF
            await update.message.reply_text("📝 جاري إنشاء ملف PDF المنسق...")
            output_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            self.pdf_gen.create_pdf(corrected_text, output_pdf.name)
            
            # Send the PDF
            await update.message.reply_document(
                document=open(output_pdf.name, 'rb'),
                filename='formatted_document.pdf',
                caption="✅ تم إنشاء الملف بنجاح!\n\n✨ تم تصحيح جميع الأخطاء والرموز (كيميائية، رياضية، فيزيائية) بشكل صحيح."
            )
            
            # Cleanup
            os.unlink(temp_img_path)
            os.unlink(output_pdf.name)
            
        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            await update.message.reply_text(f"❌ حدث خطأ أثناء معالجة الصورة:\n{str(e)}")


def main():
    """Start the bot"""
    
    # Create bot instance
    bot = TelegramBot()
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.IMAGE, bot.handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text_message))
    
    # Start the bot
    logger.info("Bot v2 started successfully with AI chat!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
