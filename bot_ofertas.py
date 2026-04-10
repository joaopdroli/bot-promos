import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ===================== CONFIGURAÇÕES =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CANAL = "@promoscasaeconstrucao"

# ===================== ESTADOS DA CONVERSA =====================
AGUARDANDO_LINK, AGUARDANDO_PRECO, AGUARDANDO_PRECO_ORIGINAL, AGUARDANDO_DESCRICAO, AGUARDANDO_CONFIRMACAO = range(5)

oferta_temp = {}

logging.basicConfig(level=logging.INFO)

# ===================== INÍCIO =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👷 Olá! Bem-vindo ao bot de ofertas.\n\n"
        "Use /novaoferta para postar um produto no canal.\n"
        "Use /cancelar para cancelar a qualquer momento."
    )

# ===================== NOVA OFERTA =====================
async def nova_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp.clear()
    await update.message.reply_text("🔗 Me manda o *link do produto* (seu link de afiliado):", parse_mode="Markdown")
    return AGUARDANDO_LINK

async def receber_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["link"] = update.message.text.strip()
    await update.message.reply_text("💰 Qual o *preço atual* do produto? (ex: 149,90):", parse_mode="Markdown")
    return AGUARDANDO_PRECO

async def receber_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["preco"] = update.message.text.strip()
    await update.message.reply_text("🏷️ Qual o *preço original* (antes do desconto)? Digite /pular se não souber:", parse_mode="Markdown")
    return AGUARDANDO_PRECO_ORIGINAL

async def receber_preco_original(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    oferta_temp["preco_original"] = None if texto.lower() == "/pular" else texto
    await update.message.reply_text("📝 Me manda uma *descrição curta* do produto (ex: Furadeira de Impacto 700W Bosch):", parse_mode="Markdown")
    return AGUARDANDO_DESCRICAO

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp["descricao"] = update.message.text.strip()

    # Monta preview
    preview = formatar_mensagem(oferta_temp)

    keyboard = [
        [InlineKeyboardButton("✅ Postar no canal", callback_data="confirmar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📋 *Preview da oferta:*\n\n{preview}\n\n_Deseja postar no canal?_",
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=False
    )
    return AGUARDANDO_CONFIRMACAO

async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar":
        mensagem = formatar_mensagem(oferta_temp)
        await context.bot.send_message(
            chat_id=CANAL,
            text=mensagem,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        await query.edit_message_text("✅ Oferta postada no canal com sucesso!")
    else:
        await query.edit_message_text("❌ Oferta cancelada.")

    oferta_temp.clear()
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oferta_temp.clear()
    await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END

# ===================== FORMATAR MENSAGEM =====================
def formatar_mensagem(oferta):
    descricao = oferta.get("descricao", "Produto")
    preco = oferta.get("preco", "")
    preco_original = oferta.get("preco_original")
    link = oferta.get("link", "")

    linhas = [f"🏠 *{descricao}*\n"]

    if preco_original:
        linhas.append(f"~~R$ {preco_original}~~")

    linhas.append(f"💥 *R$ {preco}*")
    linhas.append(f"\n🛒 [Comprar agora]({link})")
    linhas.append("\n📦 Frete grátis disponível!")
    linhas.append("⚡️ Aproveite enquanto dura!")

    return "\n".join(linhas)

# ===================== MAIN =====================
if __name__ == "__main__":
    from telegram.ext import CallbackQueryHandler

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("novaoferta", nova_oferta)],
        states={
            AGUARDANDO_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_link)],
            AGUARDANDO_PRECO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_preco)],
            AGUARDANDO_PRECO_ORIGINAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_preco_original),
                CommandHandler("pular", receber_preco_original)
            ],
            AGUARDANDO_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            AGUARDANDO_CONFIRMACAO: [CallbackQueryHandler(confirmar)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("🤖 Bot rodando...")
    app.run_polling()
